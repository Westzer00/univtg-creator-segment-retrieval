"""CSV-driven adapter for the existing UniVTG Colab preview pipeline.

Run this file after the original common UniVTG cells have defined
``run_experiment`` and the feature/model functions.  The three functions
``validate_config``, ``build_runtime_paths`` and ``prepare_media`` deliberately
reuse the same names as the original notebook functions so executing this file
in the notebook replaces them with CSV-aware versions.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Optional

import pandas as pd

QUERY_COUNT = 6

CATEGORY_ALIASES = {
    "game": "game",
    "gaming": "game",
    "게임": "game",
    "drama": "drama",
    "드라마": "drama",
    "movie": "movie_review",
    "movie_review": "movie_review",
    "movie review": "movie_review",
    "영화": "movie_review",
    "영화리뷰": "movie_review",
    "podcast": "podcast",
    "interview": "podcast",
    "팟캐스트": "podcast",
    "인터뷰": "podcast",
}

# 장르별 후처리 설정. Query 종류(fixed/individual)는 이 값에 영향을 주지 않습니다.
DEFAULT_CATEGORY_RUNTIME_CONFIG: dict[str, dict[str, Any]] = {
    "game": {
        "analysis_clip_len_sec": 2.0,
        "context_before_sec": 1.0,
        "context_after_sec": 1.0,
        "num_scenes": 10,
        "min_scene_gap_sec": 2.0,
        "drive_result_folder": "univtg_zero_shot_result_game",
    },
    "drama": {
        "analysis_clip_len_sec": 2.0,
        "context_before_sec": 4.0,
        "context_after_sec": 6.0,
        "num_scenes": 5,
        "min_scene_gap_sec": 4.0,
        "drive_result_folder": "univtg_zero_shot_result_drama",
    },
    "movie_review": {
        "analysis_clip_len_sec": 2.0,
        "context_before_sec": 5.0,
        "context_after_sec": 10.0,
        "num_scenes": 4,
        "min_scene_gap_sec": 5.0,
        "drive_result_folder": "univtg_zero_shot_result_movie_review",
    },
    "podcast": {
        "analysis_clip_len_sec": 2.0,
        "context_before_sec": 5.0,
        "context_after_sec": 10.0,
        "num_scenes": 4,
        "min_scene_gap_sec": 5.0,
        "drive_result_folder": "univtg_zero_shot_result_podcast",
    },
}


def _nfc(value: Any) -> str:
    """Normalize text used as a join key without changing the stored path."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return unicodedata.normalize("NFC", str(value).strip())


def _canonical_category(value: Any) -> str:
    key = _nfc(value).lower().replace("-", "_")
    return CATEGORY_ALIASES.get(key, key)


def _read_csv(path: str | Path, *, label: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"{label} CSV를 찾지 못했습니다: {csv_path}")
    frame = pd.read_csv(csv_path, encoding="utf-8-sig")
    frame.columns = [str(column).strip() for column in frame.columns]
    if frame.empty:
        raise ValueError(f"{label} CSV가 비어 있습니다: {csv_path}")
    return frame


def _required_columns(frame: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} CSV 필수 컬럼 누락: {missing}")


def _query_columns(prefix: str) -> list[str]:
    return [f"{prefix}_{index}" for index in range(1, QUERY_COUNT + 1)]


def _extract_queries(row: Mapping[str, Any], prefix: str) -> list[str]:
    queries: list[str] = []
    missing: list[str] = []
    for column in _query_columns(prefix):
        value = row.get(column)
        if value is None or (isinstance(value, float) and math.isnan(value)):
            missing.append(column)
            continue
        text = str(value).strip()
        if not text:
            missing.append(column)
            continue
        queries.append(text)
    if missing:
        raise ValueError(
            f"video/category row에 Query가 비어 있습니다. prefix={prefix}, missing={missing}"
        )
    return queries


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "nan"}:
        return None
    return float(text)


def _parse_review_flag(value: Any) -> bool:
    """Parse CSV bool values without treating the text 'False' as true."""
    if value is None or pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"", "false", "0", "no", "n", "off"}:
        return False
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    raise ValueError(f"flag_review must be true/false, got {value!r}")


def _derive_category_queries(video_frame: pd.DataFrame) -> pd.DataFrame:
    fixed_columns = _query_columns("fixed_query")
    _required_columns(video_frame, ["category", *fixed_columns], "영상 Query")

    records: list[dict[str, Any]] = []
    for category, group in video_frame.groupby("_category_key", sort=True):
        unique_rows = group[fixed_columns].fillna("").astype(str).drop_duplicates()
        if len(unique_rows) != 1:
            raise ValueError(
                f"category={category}의 fixed Query가 영상마다 다릅니다. "
                "고정 Query CSV를 별도로 전달하거나 값을 통일하세요."
            )
        record: dict[str, Any] = {"category": category, "_category_key": category}
        record.update(unique_rows.iloc[0].to_dict())
        records.append(record)
    return pd.DataFrame(records)


def load_pipeline_tables(
    *,
    video_query_csv: str | Path,
    timing_csv: str | Path,
    category_query_csv: str | Path | None = None,
    skip_flagged_rows: bool = True,
) -> dict[str, pd.DataFrame]:
    """Load and validate Query/timing CSVs, then merge them by ``video_id``.

    Supported layouts
    -----------------
    1. Current combined file: video rows contain fixed_query_1~6 and
       indiv_query_1~6.
    2. Future split files: category_query_csv contains one row per category and
       video_query_csv contains indiv_query_1~6 per video.
    """
    video_frame = _read_csv(video_query_csv, label="영상 Query")
    _required_columns(
        video_frame,
        ["video_id", "video_path", "title", "category", *_query_columns("indiv_query")],
        "영상 Query",
    )

    video_frame = video_frame.copy()
    video_frame["_video_key"] = video_frame["video_id"].map(_nfc)
    video_frame["_category_key"] = video_frame["category"].map(_canonical_category)

    duplicated = video_frame[video_frame["_video_key"].duplicated(keep=False)]
    if not duplicated.empty:
        ids = duplicated["video_id"].astype(str).tolist()
        raise ValueError(f"영상 Query CSV에 중복 video_id가 있습니다: {ids}")

    if skip_flagged_rows and "flag_review" in video_frame.columns:
        flagged = video_frame["flag_review"].map(_parse_review_flag)
        if flagged.any():
            print(f"flag_review=True인 {int(flagged.sum())}개 행을 제외합니다.")
            video_frame = video_frame.loc[~flagged].copy()

    if category_query_csv is None:
        category_frame = _derive_category_queries(video_frame)
        category_source = "video_query_csv 내부 fixed_query 컬럼"
    else:
        category_frame = _read_csv(category_query_csv, label="카테고리 Query")
        _required_columns(category_frame, ["category"], "카테고리 Query")

        # query_1~6 형식도 fixed_query_1~6으로 자동 변환합니다.
        for index in range(1, QUERY_COUNT + 1):
            generic = f"query_{index}"
            fixed = f"fixed_query_{index}"
            if fixed not in category_frame.columns and generic in category_frame.columns:
                category_frame = category_frame.rename(columns={generic: fixed})

        _required_columns(
            category_frame,
            ["category", *_query_columns("fixed_query")],
            "카테고리 Query",
        )
        category_frame = category_frame.copy()
        category_frame["_category_key"] = category_frame["category"].map(
            _canonical_category
        )
        if category_frame["_category_key"].duplicated().any():
            duplicates = category_frame.loc[
                category_frame["_category_key"].duplicated(keep=False), "category"
            ].tolist()
            raise ValueError(f"카테고리 Query CSV에 중복 category가 있습니다: {duplicates}")
        category_source = str(category_query_csv)

    timing_frame = _read_csv(timing_csv, label="인트로 시간")
    _required_columns(
        timing_frame,
        ["video_id", "intro_end_sec", "video_end_sec"],
        "인트로 시간",
    )
    timing_frame = timing_frame.copy()
    timing_frame["_video_key"] = timing_frame["video_id"].map(_nfc)

    if timing_frame["_video_key"].duplicated().any():
        duplicates = timing_frame.loc[
            timing_frame["_video_key"].duplicated(keep=False), "video_id"
        ].tolist()
        raise ValueError(f"인트로 시간 CSV에 중복 video_id가 있습니다: {duplicates}")

    if "intro_start_sec" not in timing_frame.columns:
        timing_frame["intro_start_sec"] = 0.0

    # 팀 파일에서 branding_end_sec, brand_end_sec, logo_end_sec 중 어느 이름을
    # 쓰더라도 처리합니다. 값이 비어 있으면 intro_end_sec를 본문 시작으로 사용합니다.
    branding_column = next(
        (
            column
            for column in [
                "branding_end_sec",
                "brand_end_sec",
                "logo_end_sec",
                "body_start_sec",
            ]
            if column in timing_frame.columns
        ),
        None,
    )
    if branding_column is None:
        timing_frame["branding_end_sec"] = timing_frame["intro_end_sec"]
    else:
        timing_frame["branding_end_sec"] = timing_frame[branding_column]
        timing_frame["branding_end_sec"] = timing_frame[
            "branding_end_sec"
        ].where(timing_frame["branding_end_sec"].notna(), timing_frame["intro_end_sec"])

    numeric_columns = [
        "intro_start_sec",
        "intro_end_sec",
        "branding_end_sec",
        "video_end_sec",
    ]
    for column in numeric_columns:
        timing_frame[column] = pd.to_numeric(timing_frame[column], errors="coerce")

    if timing_frame[["intro_start_sec", "intro_end_sec", "branding_end_sec"]].isna().any().any():
        bad = timing_frame.loc[
            timing_frame[["intro_start_sec", "intro_end_sec", "branding_end_sec"]]
            .isna()
            .any(axis=1),
            "video_id",
        ].tolist()
        raise ValueError(f"인트로 시간 값이 숫자가 아닌 행이 있습니다: {bad}")

    invalid_order = timing_frame[
        (timing_frame["intro_end_sec"] < timing_frame["intro_start_sec"])
        | (timing_frame["branding_end_sec"] < timing_frame["intro_end_sec"])
    ]
    if not invalid_order.empty:
        raise ValueError(
            "시간 순서는 intro_start_sec <= intro_end_sec <= branding_end_sec여야 합니다. "
            f"문제 video_id={invalid_order['video_id'].tolist()}"
        )

    merged = video_frame.merge(
        timing_frame.drop(columns=["video_id"], errors="ignore"),
        on="_video_key",
        how="left",
        validate="one_to_one",
        suffixes=("", "_timing"),
    )

    missing_timing = merged[merged["intro_end_sec"].isna()]["video_id"].tolist()
    if missing_timing:
        raise ValueError(
            "인트로 시간 CSV에 없는 video_id가 있습니다: " + ", ".join(map(str, missing_timing))
        )

    missing_category = sorted(
        set(merged["_category_key"]) - set(category_frame["_category_key"])
    )
    if missing_category:
        raise ValueError(
            f"카테고리 Query가 없는 category가 있습니다: {missing_category}"
        )

    print(f"영상 Query: {len(video_frame)}개")
    print(f"카테고리 Query: {len(category_frame)}개 ({category_source})")
    print(f"인트로 시간: {len(timing_frame)}개")
    print("병합 검증 완료")

    return {
        "video_queries": video_frame.reset_index(drop=True),
        "category_queries": category_frame.reset_index(drop=True),
        "timings": timing_frame.reset_index(drop=True),
        "merged": merged.reset_index(drop=True),
    }


def _safe_slug(value: Any) -> str:
    text = _nfc(value)
    text = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "video"


def build_experiment_config_from_csv(
    *,
    tables: Mapping[str, pd.DataFrame],
    video_id: str,
    query_type: str,
    category_runtime_config: Mapping[str, Mapping[str, Any]] | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one existing-pipeline config from CSV rows.

    ``query_type`` may be ``fixed``, ``individual`` or ``combined``.
    """
    query_type = str(query_type).strip().lower()
    if query_type not in {"fixed", "individual", "combined"}:
        raise ValueError("query_type은 fixed, individual, combined 중 하나여야 합니다.")

    video_key = _nfc(video_id)
    merged = tables["merged"]
    matched = merged.loc[merged["_video_key"] == video_key]
    if len(matched) != 1:
        available = merged["video_id"].astype(str).tolist()
        raise KeyError(f"video_id={video_id!r}를 찾지 못했습니다. available={available}")
    row = matched.iloc[0]

    category_key = str(row["_category_key"])
    category_rows = tables["category_queries"].loc[
        tables["category_queries"]["_category_key"] == category_key
    ]
    if len(category_rows) != 1:
        raise ValueError(f"category={category_key}의 고정 Query 행이 정확히 1개가 아닙니다.")

    fixed_queries = _extract_queries(category_rows.iloc[0], "fixed_query")
    individual_queries = _extract_queries(row, "indiv_query")

    if query_type == "fixed":
        queries = fixed_queries
    elif query_type == "individual":
        queries = individual_queries
    else:
        queries = list(dict.fromkeys([*fixed_queries, *individual_queries]))

    runtime_table = dict(DEFAULT_CATEGORY_RUNTIME_CONFIG)
    if category_runtime_config is not None:
        runtime_table.update(
            {str(key): dict(value) for key, value in category_runtime_config.items()}
        )
    if category_key not in runtime_table:
        raise KeyError(
            f"category={category_key}의 runtime 설정이 없습니다. "
            "DEFAULT_CATEGORY_RUNTIME_CONFIG 또는 category_runtime_config에 추가하세요."
        )
    runtime = dict(runtime_table[category_key])

    experiment_id = f"{category_key}_{_safe_slug(row['video_id'])}"
    result_base = runtime.pop(
        "drive_result_folder", f"univtg_zero_shot_result_{category_key}"
    )

    config: dict[str, Any] = {
        "experiment_id": experiment_id,
        "video_id": str(row["video_id"]),
        "title": str(row["title"]),
        "category": category_key,
        "video_path": Path(str(row["video_path"])),
        "intro_start_sec": float(row["intro_start_sec"]),
        "intro_end_sec": float(row["intro_end_sec"]),
        "body_start_sec": float(row["branding_end_sec"]),
        "video_end_sec": _to_optional_float(row.get("video_end_sec")),
        "query_type": query_type,
        "queries": queries,
        "saliency_weight": 0.75,
        "foreground_weight": 0.25,
        "drive_result_folder": f"{result_base}_{query_type}",
        "force_rebuild_media": False,
        "force_reextract_features": False,
        "show_videos": True,
        **runtime,
    }

    if overrides:
        config.update(dict(overrides))

    return config


def describe_config(config: Mapping[str, Any]) -> pd.DataFrame:
    """Return a compact table for checking a generated config before running."""
    scene_duration = float(config["context_before_sec"]) + float(
        config["context_after_sec"]
    )
    rows = [
        ("video_id", config.get("video_id")),
        ("category", config.get("category")),
        ("query_type", config.get("query_type")),
        ("query_count", len(config.get("queries", []))),
        ("intro", f"{config['intro_start_sec']}~{config['intro_end_sec']} sec"),
        ("body_start_sec", config["body_start_sec"]),
        ("video_end_sec", config.get("video_end_sec")),
        ("analysis_clip_len_sec", config["analysis_clip_len_sec"]),
        ("scene_duration_sec", scene_duration),
        ("num_scenes", config["num_scenes"]),
        ("expected_preview_sec", scene_duration * int(config["num_scenes"])),
        ("drive_result_folder", config["drive_result_folder"]),
    ]
    return pd.DataFrame(rows, columns=["item", "value"])


def _probe_video_duration(video_path: str | Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def _run_command(command: Iterable[Any]) -> None:
    command_list = [str(value) for value in command]
    print(" ".join(command_list))
    subprocess.run(command_list, check=True)


# ---------------------------------------------------------------------------
# 아래 3개는 기존 노트북의 동일 이름 함수를 덮어쓰는 CSV-aware 버전입니다.
# ---------------------------------------------------------------------------

def validate_config(config: MutableMapping[str, Any]) -> None:
    """Validate config and clamp optional CSV video_end_sec to real duration."""
    video_path = Path(config["video_path"])
    if not video_path.exists():
        raise FileNotFoundError(f"원본 영상을 찾지 못했습니다:\n{video_path}")

    actual_duration = _probe_video_duration(video_path)
    requested_end = _to_optional_float(config.get("video_end_sec"))
    effective_end = actual_duration if requested_end is None else min(requested_end, actual_duration)

    config["_actual_video_duration_sec"] = actual_duration
    config["_effective_video_end_sec"] = effective_end

    intro_start = float(config["intro_start_sec"])
    intro_end = float(config["intro_end_sec"])
    body_start = float(config["body_start_sec"])

    if intro_start < 0 or intro_end <= intro_start:
        raise ValueError("인트로는 0초 이상이며 intro_end_sec > intro_start_sec여야 합니다.")
    if body_start < intro_end:
        raise ValueError("body_start_sec는 intro_end_sec 이상이어야 합니다.")
    if body_start >= effective_end:
        raise ValueError(
            f"body_start_sec={body_start}가 유효 영상 끝={effective_end:.3f}보다 작아야 합니다."
        )
    if intro_end > actual_duration:
        raise ValueError(
            f"intro_end_sec={intro_end}가 실제 영상 길이={actual_duration:.3f}를 초과합니다."
        )
    if not config.get("queries"):
        raise ValueError("Query를 최소 1개 입력해야 합니다.")

    scene_duration = float(config["context_before_sec"]) + float(
        config["context_after_sec"]
    )
    if scene_duration <= 0:
        raise ValueError("최종 장면 길이는 0초보다 커야 합니다.")
    if int(config["num_scenes"]) <= 0:
        raise ValueError("선택 장면 수는 1개 이상이어야 합니다.")

    weight_sum = float(config["saliency_weight"]) + float(
        config["foreground_weight"]
    )
    if weight_sum <= 0:
        raise ValueError("점수 가중치 합은 0보다 커야 합니다.")

    if requested_end is not None and requested_end > actual_duration:
        print(
            f"CSV video_end_sec={requested_end:.3f}가 실제 길이보다 큽니다. "
            f"실제 길이 {actual_duration:.3f}초로 자동 보정합니다."
        )


def build_runtime_paths(config: Mapping[str, Any]) -> dict[str, Path]:
    """Separate media/feature cache from query-specific result folders."""
    video_path = Path(config["video_path"])
    stat = video_path.stat()

    effective_end = config.get("_effective_video_end_sec", config.get("video_end_sec"))
    media_signature_text = json.dumps(
        {
            "path": str(video_path.resolve()),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "body_start_sec": float(config["body_start_sec"]),
            "video_end_sec": effective_end,
            "analysis_clip_len_sec": float(config["analysis_clip_len_sec"]),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    media_signature = hashlib.sha1(media_signature_text.encode("utf-8")).hexdigest()[:12]

    query_signature_text = json.dumps(
        {
            "query_type": config.get("query_type", "manual"),
            "queries": list(config["queries"]),
            "context_before_sec": float(config["context_before_sec"]),
            "context_after_sec": float(config["context_after_sec"]),
            "num_scenes": int(config["num_scenes"]),
            "min_scene_gap_sec": float(config["min_scene_gap_sec"]),
            "saliency_weight": float(config["saliency_weight"]),
            "foreground_weight": float(config["foreground_weight"]),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    query_signature = hashlib.sha1(query_signature_text.encode("utf-8")).hexdigest()[:10]

    cache_root = (
        Path("/content/univtg_cache")
        / f"{_safe_slug(config.get('video_id', config['experiment_id']))}_{media_signature}"
    )
    run_root = (
        Path("/content/univtg_runs")
        / (
            f"{_safe_slug(config['experiment_id'])}_"
            f"{_safe_slug(config.get('query_type', 'manual'))}_"
            f"{query_signature}"
        )
    )
    cache_root.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)

    scene_duration = float(config["context_before_sec"]) + float(
        config["context_after_sec"]
    )
    expected_preview_sec = scene_duration * int(config["num_scenes"])

    paths = {
        "root": run_root,
        "media_cache_root": cache_root,
        "intro_video": cache_root / "creator_intro.mp4",
        "body_video": cache_root / "body_for_model_360p.mp4",
        "body_check_video": cache_root / "body_first_20s_check.mp4",
        "feature_dir": cache_root / "features",
        "feature_npz": cache_root / "features" / "vid.npz",
        "score_csv": run_root / "all_clip_scores.csv",
        "segments_csv": run_root / "selected_segments.csv",
        "output_video": run_root
        / (
            f"univtg_{_safe_slug(config['experiment_id'])}_"
            f"{_safe_slug(config.get('query_type', 'manual'))}_"
            f"{int(round(expected_preview_sec))}s.mp4"
        ),
        "config_json": run_root / "experiment_config.json",
        "drive_result_dir": video_path.parent / str(config["drive_result_folder"]),
    }
    paths["feature_dir"].mkdir(parents=True, exist_ok=True)
    return paths


def prepare_media(config: Mapping[str, Any], paths: Mapping[str, Path]) -> None:
    """Cut intro/body using CSV times and optional video_end_sec."""
    rebuild = bool(config["force_rebuild_media"])
    effective_end = float(
        config.get("_effective_video_end_sec")
        or config.get("video_end_sec")
        or _probe_video_duration(config["video_path"])
    )
    body_duration = effective_end - float(config["body_start_sec"])

    if rebuild or not paths["intro_video"].exists():
        _run_command(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(config["intro_start_sec"]),
                "-i",
                config["video_path"],
                "-t",
                str(float(config["intro_end_sec"]) - float(config["intro_start_sec"])),
                "-vf",
                "scale=-2:360,fps=30",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "24",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                paths["intro_video"],
            ]
        )
    else:
        print("기존 인트로 캐시 재사용:", paths["intro_video"])

    if rebuild or not paths["body_video"].exists():
        _run_command(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(config["body_start_sec"]),
                "-i",
                config["video_path"],
                "-t",
                f"{body_duration:.3f}",
                "-vf",
                "scale=-2:360,fps=30",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "25",
                "-an",
                "-movflags",
                "+faststart",
                paths["body_video"],
            ]
        )
    else:
        print("기존 본문/영상 특징용 캐시 재사용:", paths["body_video"])

    if rebuild or not paths["body_check_video"].exists():
        _run_command(
            [
                "ffmpeg",
                "-y",
                "-i",
                paths["body_video"],
                "-t",
                "20",
                "-c",
                "copy",
                paths["body_check_video"],
            ]
        )


def build_batch_plan(
    *,
    tables: Mapping[str, pd.DataFrame],
    query_type: str,
    categories: Optional[Iterable[str]] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """Create a reviewable batch plan before running hundreds of videos."""
    frame = tables["merged"].copy()
    if categories is not None:
        category_keys = {_canonical_category(value) for value in categories}
        frame = frame[frame["_category_key"].isin(category_keys)]
    if limit is not None:
        frame = frame.head(int(limit))

    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        records.append(
            {
                "video_id": row["video_id"],
                "category": row["_category_key"],
                "query_type": query_type,
                "video_path": row["video_path"],
                "intro_end_sec": row["intro_end_sec"],
                "body_start_sec": row["branding_end_sec"],
                "video_end_sec": row["video_end_sec"],
            }
        )
    return pd.DataFrame(records)

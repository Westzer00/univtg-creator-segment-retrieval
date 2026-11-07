"""Synthetic boundary checks for the published UniVTG CSV adapter (no real videos)."""
from pathlib import Path
import pandas as pd
import pytest
import src.univtg_csv_adapter as adapter

def _fixtures(tmp_path, empty_query=False):
    row = {
        "video_id": "synthetic-001",
        "video_path": str(tmp_path / "synthetic.mp4"),
        "title": "Synthetic clip", "category": "game", "flag_review": False,
    }
    for i in range(1, 7):
        row[f"fixed_query_{i}"] = f"fixed query {i}"
        row[f"indiv_query_{i}"] = f"individual query {i}"
    if empty_query:
        row["indiv_query_3"] = ""
    q, t = tmp_path / "q.csv", tmp_path / "t.csv"
    pd.DataFrame([row]).to_csv(q, index=False)
    pd.DataFrame([{"video_id": "synthetic-001", "intro_start_sec": 0.,
        "intro_end_sec": 5., "branding_end_sec": 7., "video_end_sec": 120.}]).to_csv(t, index=False)
    return q, t

def _config(tmp_path):
    q, t = _fixtures(tmp_path)
    tables = adapter.load_pipeline_tables(video_query_csv=q, timing_csv=t)
    return adapter.build_experiment_config_from_csv(
        tables=tables, video_id="synthetic-001", query_type="combined")

def test_combined_queries_unique_and_ordered(tmp_path):
    cfg = _config(tmp_path)
    assert len(cfg["queries"]) == len(set(cfg["queries"])) == 12
    assert cfg["queries"][0] == "fixed query 1"
    assert cfg["queries"][-1] == "individual query 6"
    assert cfg["body_start_sec"] == 7.
    assert cfg["video_end_sec"] == 120.

def test_invalid_query_mode(tmp_path):
    q, t = _fixtures(tmp_path)
    tables = adapter.load_pipeline_tables(video_query_csv=q, timing_csv=t)
    with pytest.raises(ValueError, match="query_type"):
        adapter.build_experiment_config_from_csv(
            tables=tables, video_id="synthetic-001", query_type="wrong")

def test_missing_individual_query_rejected(tmp_path):
    q, t = _fixtures(tmp_path, empty_query=True)
    tables = adapter.load_pipeline_tables(video_query_csv=q, timing_csv=t)
    with pytest.raises(ValueError, match="indiv_query"):
        adapter.build_experiment_config_from_csv(
            tables=tables, video_id="synthetic-001", query_type="individual")

def test_reversed_intro_times_rejected(tmp_path):
    q, t = _fixtures(tmp_path)
    timing = pd.read_csv(t)
    timing.loc[0, "intro_start_sec"] = 15.
    timing.to_csv(t, index=False)
    with pytest.raises(ValueError, match="시간 순서"):
        adapter.load_pipeline_tables(video_query_csv=q, timing_csv=t)

def test_unknown_video_rejected(tmp_path):
    q, t = _fixtures(tmp_path)
    tables = adapter.load_pipeline_tables(video_query_csv=q, timing_csv=t)
    with pytest.raises(KeyError, match="video_id"):
        adapter.build_experiment_config_from_csv(
            tables=tables, video_id="missing", query_type="fixed")

def test_duration_clamped_without_decoding(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    (tmp_path / "synthetic.mp4").write_bytes(b"placeholder only")
    monkeypatch.setattr(adapter, "_probe_video_duration", lambda _: 90.)
    adapter.validate_config(cfg)
    assert cfg["_actual_video_duration_sec"] == 90.
    assert cfg["_effective_video_end_sec"] == 90.

@pytest.mark.parametrize("field,value,error", [
    ("intro_start_sec", -1., "인트로"),
    ("body_start_sec", 3., "body_start_sec"),
    ("num_scenes", 0, "선택 장면 수"),
    ("queries", [], "Query"),
])
def test_invalid_config_rejected(tmp_path, monkeypatch, field, value, error):
    cfg = _config(tmp_path)
    (tmp_path / "synthetic.mp4").write_bytes(b"placeholder only")
    monkeypatch.setattr(adapter, "_probe_video_duration", lambda _: 90.)
    cfg[field] = value
    with pytest.raises(ValueError, match=error):
        adapter.validate_config(cfg)

def test_media_commands_without_ffmpeg(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    cfg["_effective_video_end_sec"] = 90.
    commands = []
    monkeypatch.setattr(adapter, "_run_command", lambda cmd: commands.append([str(x) for x in cmd]))
    paths = {key: tmp_path / f"{key}.mp4"
             for key in ("intro_video", "body_video", "body_check_video")}
    adapter.prepare_media(cfg, paths)
    assert len(commands) == 3
    assert all(cmd[0] == "ffmpeg" for cmd in commands)
    assert "83.000" in commands[1]  # body from second 7 to second 90

def test_batch_plan_category_filter(tmp_path):
    q, t = _fixtures(tmp_path)
    tables = adapter.load_pipeline_tables(video_query_csv=q, timing_csv=t)
    plan = adapter.build_batch_plan(tables=tables, query_type="fixed", categories=["game"], limit=1)
    assert len(plan) == 1
    assert plan["video_id"].iloc[0] == "synthetic-001"
    assert adapter.build_batch_plan(tables=tables, query_type="fixed", categories=["drama"]).empty

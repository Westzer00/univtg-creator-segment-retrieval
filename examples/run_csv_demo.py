"""CSV 입력과 조회 설정만 확인하는 예제. 영상·모델 추론은 하지 않습니다."""
from pathlib import Path
from src.univtg_csv_adapter import load_pipeline_tables, build_experiment_config_from_csv


DATA = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    tables = load_pipeline_tables(
        video_query_csv=DATA / "sample_queries.csv",
        timing_csv=DATA / "sample_timings.csv",
        category_query_csv=DATA / "sample_category_queries.csv",
    )
    for video_id in tables["merged"]["video_id"]:
        config = build_experiment_config_from_csv(
            tables=tables, video_id=str(video_id), query_type="individual"
        )
        print(f"{video_id}: {len(config['queries'])} queries, category={config['category']}")
    print("CSV 검증 완료. 실제 영상·UniVTG 추론은 이 예제에서 수행하지 않습니다.")


if __name__ == "__main__":
    main()

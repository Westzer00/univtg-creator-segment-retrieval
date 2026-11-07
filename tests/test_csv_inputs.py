from pathlib import Path
import pandas as pd
import pytest
from src.univtg_csv_adapter import (
    _parse_review_flag, load_pipeline_tables, build_experiment_config_from_csv,
)


DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.mark.parametrize("value,expected", [
    ("False", False), ("false", False), (0, False), (None, False),
    ("True", True), (1, True), ("yes", True), ("0", False)
])
def test_flag_parser(value, expected):
    assert _parse_review_flag(value) is expected


def test_bad_flag_rejected():
    with pytest.raises(ValueError):
        _parse_review_flag("maybe")


def test_synthetic_query_and_timing_merge():
    tables = load_pipeline_tables(
        video_query_csv=DATA / "sample_queries.csv",
        timing_csv=DATA / "sample_timings.csv",
        category_query_csv=DATA / "sample_category_queries.csv",
    )
    assert len(tables["merged"]) == 2
    config = build_experiment_config_from_csv(
        tables=tables,
        video_id=str(tables["merged"]["video_id"].iloc[0]),
        query_type="individual",
    )
    assert config["category"] == "game"
    assert len(config["queries"]) == 6


def test_string_false_flag_does_not_drop_row(tmp_path):
    data=pd.read_csv(DATA / "sample_queries.csv",dtype={"flag_review":"string"})
    data["flag_review"]=["False","True"]
    p=tmp_path / "queries.csv"
    data.to_csv(p,index=False)
    tables=load_pipeline_tables(
        video_query_csv=p,
        timing_csv=DATA / "sample_timings.csv",
        category_query_csv=DATA / "sample_category_queries.csv",
    )
    assert len(tables["merged"]) == 1

"""Tests for Streamlit helper functions."""

from __future__ import annotations

from datetime import date

import pytest

pd = pytest.importorskip("pandas")
from app.streamlit_app import apply_date_range_filter, apply_min_numeric_filter


def test_apply_min_numeric_filter_filters_rows() -> None:
    df = pd.DataFrame({"confidence_score": [0.2, 0.8, 0.5], "pitcher_name": ["A", "B", "C"]})
    out = apply_min_numeric_filter(df, "confidence_score", 0.6)
    assert out["pitcher_name"].tolist() == ["B"]


def test_apply_min_numeric_filter_no_column_returns_input_rows() -> None:
    df = pd.DataFrame({"pitcher_name": ["A", "B"]})
    out = apply_min_numeric_filter(df, "confidence_score", 0.6)
    assert out["pitcher_name"].tolist() == ["A", "B"]


def test_apply_date_range_filter_filters_dates() -> None:
    df = pd.DataFrame(
        {
            "game_date": ["2024-04-01", "2024-04-15", "2024-05-01"],
            "pitcher_name": ["A", "B", "C"],
        }
    )
    out = apply_date_range_filter(df, "game_date", date(2024, 4, 10), date(2024, 4, 30))
    assert out["pitcher_name"].tolist() == ["B"]

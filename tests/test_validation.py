"""Tests for shared validation utilities."""

import math
from datetime import datetime

import pytest

from diamond_gems.validation import ensure_datetime_column, safe_divide, validate_required_columns


class FakeDataFrame:
    """Minimal DataFrame-like object for tests in constrained environments."""

    def __init__(self, data: dict[str, list]) -> None:
        self._data = {key: list(value) for key, value in data.items()}

    @property
    def columns(self) -> list[str]:
        return list(self._data.keys())

    def copy(self, deep: bool = True):
        copied = {key: list(value) for key, value in self._data.items()} if deep else dict(self._data)
        return FakeDataFrame(copied)

    def __getitem__(self, key: str):
        return self._data[key]

    def __setitem__(self, key: str, value):
        self._data[key] = list(value)


def test_validate_required_columns_raises_on_missing_columns() -> None:
    """Validation should raise when required columns are missing."""
    df = FakeDataFrame({"a": [1], "b": [2]})

    with pytest.raises(ValueError, match="missing required columns: c"):
        validate_required_columns(df, ["a", "c"], df_name="pitch_events")


def test_validate_required_columns_passes_when_columns_present() -> None:
    """Validation should pass when required columns exist."""
    df = FakeDataFrame({"a": [1], "b": [2]})

    validate_required_columns(df, {"a", "b"})


def test_safe_divide_returns_nan_for_zero_or_null_denominator() -> None:
    """Safe divide should return NaN where denominator is invalid."""
    result = safe_divide([10.0, 20.0, 30.0], [2.0, 0.0, None])

    assert result[0] == 5.0
    assert math.isnan(result[1])
    assert math.isnan(result[2])


def test_ensure_datetime_column_does_not_mutate_input() -> None:
    """Datetime conversion should return a new object and keep input unchanged."""
    df = FakeDataFrame({"game_date": ["2024-01-01", "2024-01-02"], "value": [1, 2]})

    result = ensure_datetime_column(df, "game_date")

    assert isinstance(result["game_date"][0], datetime)
    assert isinstance(result["game_date"][1], datetime)
    assert isinstance(df["game_date"][0], str)
    assert df is not result

"""Shared validation and utility helpers for data processing."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None


def _is_scalar(value) -> bool:
    if pd is not None:
        return pd.api.types.is_scalar(value)
    return not isinstance(value, (list, tuple, dict, set))


def _is_na(value) -> bool:
    if pd is not None:
        return bool(pd.isna(value))
    return value is None


def validate_required_columns(
    df,
    required_columns: list[str] | set[str],
    df_name: str = "DataFrame",
) -> None:
    """Validate that a DataFrame-like object contains required columns."""
    required_set = set(required_columns)
    missing_columns = sorted(required_set.difference(df.columns))

    if missing_columns:
        missing_display = ", ".join(missing_columns)
        raise ValueError(f"{df_name} is missing required columns: {missing_display}")


def safe_divide(numerator, denominator):
    """Safely divide values, returning NaN when denominator is zero/null."""
    if _is_scalar(numerator) and _is_scalar(denominator):
        if _is_na(denominator) or denominator == 0:
            return float("nan")
        return numerator / denominator

    if isinstance(numerator, (list, tuple)) and isinstance(denominator, (list, tuple)):
        output = []
        for num_value, den_value in zip(numerator, denominator):
            output.append(safe_divide(num_value, den_value))
        return output

    result = numerator / denominator
    invalid_denominator = (_is_na(denominator) or denominator == 0)

    if hasattr(result, "where"):
        return result.where(~invalid_denominator, float("nan"))

    return float("nan") if invalid_denominator else result


def ensure_datetime_column(df, column: str):
    """Return a copy with the selected column converted to datetime."""
    validate_required_columns(df, [column])

    if pd is not None:
        df_copy = df.copy(deep=True)
        df_copy[column] = pd.to_datetime(df_copy[column])
        return df_copy

    df_copy = deepcopy(df)
    df_copy[column] = [datetime.fromisoformat(value) for value in df_copy[column]]
    return df_copy

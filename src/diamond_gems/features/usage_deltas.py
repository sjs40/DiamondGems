"""Usage delta feature engineering for pitcher pitch-type trends."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from diamond_gems.constants import MAJOR_USAGE_SPIKE_THRESHOLD, USAGE_SPIKE_THRESHOLD
from diamond_gems.validation import validate_required_columns

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None

REQUIRED_COLUMNS = ["appearance_id", "pitcher_id", "pitch_type", "game_date", "usage_rate", "pitch_count"]


def _to_records(df) -> list[dict]:
    if pd is not None and isinstance(df, pd.DataFrame):
        return df.to_dict("records")
    if hasattr(df, "to_dict"):
        return df.to_dict("records")
    return deepcopy(df)


def _from_records(records: list[dict], template):
    if pd is not None and isinstance(template, pd.DataFrame):
        return pd.DataFrame.from_records(records)
    frame_cls = template.__class__
    if hasattr(frame_cls, "from_records"):
        return frame_cls.from_records(records)
    return records


def _to_date(value) -> datetime.date:
    if value is None:
        return datetime.min.date()
    if hasattr(value, "date") and not isinstance(value, str):
        return value.date() if hasattr(value, "hour") else value
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return datetime.min.date()


def _sort_key(row: dict) -> tuple:
    return (
        str(row.get("pitcher_id") if row.get("pitcher_id") is not None else ""),
        str(row.get("pitch_type") if row.get("pitch_type") is not None else ""),
        _to_date(row.get("game_date")),
        str(row.get("appearance_id") if row.get("appearance_id") is not None else ""),
    )


def _mean(values: list[float]):
    if not values:
        return float("nan")
    return sum(values) / len(values)


def build_pitcher_usage_deltas(pitch_type_summary):
    """Build usage deltas at one-row-per-appearance_id+pitch_type grain."""
    validate_required_columns(pitch_type_summary, REQUIRED_COLUMNS, df_name="pitch_type_summary")

    rows = _to_records(pitch_type_summary)
    rows_sorted = sorted(
        [deepcopy(row) for row in rows],
        key=_sort_key,
    )

    history: dict[tuple, list[dict]] = {}
    output_rows: list[dict] = []

    for row in rows_sorted:
        key = (row.get("pitcher_id"), row.get("pitch_type"))
        prior_rows = history.get(key, [])

        current_date = _to_date(row.get("game_date"))
        current_usage_rate = row.get("usage_rate")
        pitch_count_current = row.get("pitch_count")

        previous_row = prior_rows[-1] if prior_rows else None
        previous_usage = previous_row.get("usage_rate") if previous_row else float("nan")
        previous_pitch_count = previous_row.get("pitch_count") if previous_row else float("nan")

        delta_last_start = (
            current_usage_rate - previous_usage if previous_row else float("nan")
        )

        rows_30d = []
        for prior in prior_rows:
            prior_date = _to_date(prior.get("game_date"))
            days_diff = (current_date - prior_date).days
            if 0 < days_diff <= 30:
                rows_30d.append(prior)

        usage_30d_baseline = _mean([r.get("usage_rate") for r in rows_30d])
        delta_usage_30d = current_usage_rate - usage_30d_baseline

        rolling_3_rows = prior_rows[-3:]
        rolling_3_baseline = _mean([r.get("usage_rate") for r in rolling_3_rows])
        delta_rolling_3 = current_usage_rate - rolling_3_baseline

        first_row = prior_rows[0] if prior_rows else row
        first_start_usage = first_row.get("usage_rate")
        delta_season_start = current_usage_rate - first_start_usage

        current_season = row.get("season")
        season_prior = [r for r in prior_rows if r.get("season") == current_season]
        season_avg_before = _mean([r.get("usage_rate") for r in season_prior])
        delta_season_avg = current_usage_rate - season_avg_before

        output_row = deepcopy(row)
        output_row.update(
            {
                "current_usage_rate": current_usage_rate,
                "previous_start_usage_rate": previous_usage,
                "delta_usage_last_start": delta_last_start,
                "usage_30d_baseline": usage_30d_baseline,
                "delta_usage_30d": delta_usage_30d,
                "rolling_3_start_usage_baseline": rolling_3_baseline,
                "delta_usage_rolling_3_start": delta_rolling_3,
                "first_start_usage_rate": first_start_usage,
                "delta_usage_season_start": delta_season_start,
                "season_avg_usage_before_start": season_avg_before,
                "delta_usage_season_avg": delta_season_avg,
                "pitch_count_current": pitch_count_current,
                "pitch_count_previous_start": previous_pitch_count,
                "pitch_count_30d_baseline": sum(r.get("pitch_count") for r in rows_30d),
                "starts_in_30d_baseline": len(rows_30d),
                "low_sample_flag": bool(row.get("low_sample_flag", False)),
                "usage_spike_flag": delta_last_start >= USAGE_SPIKE_THRESHOLD if delta_last_start == delta_last_start else False,
                "major_usage_spike_flag": delta_last_start >= MAJOR_USAGE_SPIKE_THRESHOLD if delta_last_start == delta_last_start else False,
                "usage_drop_flag": delta_last_start <= -USAGE_SPIKE_THRESHOLD if delta_last_start == delta_last_start else False,
                "major_usage_drop_flag": delta_last_start <= -MAJOR_USAGE_SPIKE_THRESHOLD if delta_last_start == delta_last_start else False,
            }
        )

        output_rows.append(output_row)
        history.setdefault(key, []).append(deepcopy(row))

    return _from_records(output_rows, pitch_type_summary)

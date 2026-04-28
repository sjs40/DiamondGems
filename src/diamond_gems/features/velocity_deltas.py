"""Velocity delta feature engineering for pitcher pitch-type trends."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from diamond_gems.constants import STRONG_VELO_SPIKE_THRESHOLD, VELO_SPIKE_THRESHOLD
from diamond_gems.validation import safe_divide, validate_required_columns

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None

REQUIRED_COLUMNS = ["appearance_id", "pitcher_id", "pitch_type", "game_date", "avg_velocity", "pitch_count"]


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
    if hasattr(value, "date") and not isinstance(value, str):
        return value.date() if hasattr(value, "hour") else value
    return datetime.fromisoformat(str(value)).date()


def _mean(values: list[float]):
    if not values:
        return float("nan")
    return sum(values) / len(values)


def build_pitcher_velocity_deltas(pitch_type_summary):
    """Build velocity deltas at one-row-per-appearance_id+pitch_type grain."""
    validate_required_columns(pitch_type_summary, REQUIRED_COLUMNS, df_name="pitch_type_summary")

    rows = _to_records(pitch_type_summary)
    rows_sorted = sorted(
        [deepcopy(row) for row in rows],
        key=lambda r: (r.get("pitcher_id"), r.get("pitch_type"), _to_date(r.get("game_date")), r.get("appearance_id")),
    )

    history: dict[tuple, list[dict]] = {}
    output_rows: list[dict] = []

    for row in rows_sorted:
        key = (row.get("pitcher_id"), row.get("pitch_type"))
        prior_rows = history.get(key, [])

        current_date = _to_date(row.get("game_date"))
        current_avg_velocity = row.get("avg_velocity")
        current_pitches = row.get("pitch_count")

        previous_row = prior_rows[-1] if prior_rows else None
        previous_avg_velocity = previous_row.get("avg_velocity") if previous_row else float("nan")
        previous_pitches = previous_row.get("pitch_count") if previous_row else float("nan")
        last_start_date = previous_row.get("game_date") if previous_row else None

        if previous_row:
            delta_last_start = current_avg_velocity - previous_avg_velocity
        else:
            delta_last_start = float("nan")

        rows_30d = []
        for prior in prior_rows:
            prior_date = _to_date(prior.get("game_date"))
            days_diff = (current_date - prior_date).days
            if 0 < days_diff <= 30:
                rows_30d.append(prior)

        avg_velocity_30d_baseline = _mean([r.get("avg_velocity") for r in rows_30d])
        delta_velo_30d = current_avg_velocity - avg_velocity_30d_baseline

        rolling_3_rows = prior_rows[-3:]
        rolling_3_baseline = _mean([r.get("avg_velocity") for r in rolling_3_rows])
        delta_rolling_3 = current_avg_velocity - rolling_3_baseline

        first_row = prior_rows[0] if prior_rows else row
        first_start_avg_velocity = first_row.get("avg_velocity")
        first_start_date = first_row.get("game_date")
        delta_season_start = current_avg_velocity - first_start_avg_velocity

        current_season = row.get("season")
        season_prior = [r for r in prior_rows if r.get("season") == current_season]
        season_avg_before_start = _mean([r.get("avg_velocity") for r in season_prior])
        delta_season_avg = current_avg_velocity - season_avg_before_start

        starts_in_30d = len(rows_30d)
        pitches_30d = sum(r.get("pitch_count") for r in rows_30d)

        output_row = deepcopy(row)
        output_row.update(
            {
                "current_avg_velocity": current_avg_velocity,
                "previous_start_avg_velocity": previous_avg_velocity,
                "delta_velo_last_start": delta_last_start,
                "avg_velocity_30d_baseline": avg_velocity_30d_baseline,
                "delta_velo_30d": delta_velo_30d,
                "rolling_3_start_avg_velocity_baseline": rolling_3_baseline,
                "delta_velo_rolling_3_start": delta_rolling_3,
                "first_start_avg_velocity": first_start_avg_velocity,
                "delta_velo_season_start": delta_season_start,
                "season_avg_velocity_before_start": season_avg_before_start,
                "delta_velo_season_avg": delta_season_avg,
                "last_start_date": last_start_date,
                "first_start_date": first_start_date,
                "starts_in_30d_baseline": starts_in_30d,
                "pitches_current": current_pitches,
                "pitches_previous_start": previous_pitches,
                "pitches_30d_baseline": pitches_30d,
                "low_sample_flag": bool(row.get("low_sample_flag", False)),
                "velo_spike_flag": delta_last_start >= VELO_SPIKE_THRESHOLD if delta_last_start == delta_last_start else False,
                "strong_velo_spike_flag": delta_last_start >= STRONG_VELO_SPIKE_THRESHOLD if delta_last_start == delta_last_start else False,
                "velo_drop_flag": delta_last_start <= -VELO_SPIKE_THRESHOLD if delta_last_start == delta_last_start else False,
                "strong_velo_drop_flag": delta_last_start <= -STRONG_VELO_SPIKE_THRESHOLD if delta_last_start == delta_last_start else False,
            }
        )
        output_rows.append(output_row)

        history.setdefault(key, []).append(deepcopy(row))

    return _from_records(output_rows, pitch_type_summary)

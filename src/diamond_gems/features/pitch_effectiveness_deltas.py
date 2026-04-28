"""Pitch effectiveness delta features by pitcher and pitch type."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from diamond_gems.validation import validate_required_columns

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None

METRICS = [
    "whiff_rate",
    "csw_rate",
    "xwoba_allowed",
    "woba_allowed",
    "hard_hit_rate_allowed",
]
HIGHER_IS_BETTER = {"whiff_rate", "csw_rate"}
LOWER_IS_BETTER = {"xwoba_allowed", "woba_allowed", "hard_hit_rate_allowed"}
REQUIRED_COLUMNS = ["appearance_id", "pitcher_id", "pitch_type", "game_date", "pitch_count", *METRICS]


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


def _is_valid(value) -> bool:
    return value is not None and value == value


def _mean(values: list[float]):
    clean = [float(v) for v in values if _is_valid(v)]
    if not clean:
        return float("nan")
    return sum(clean) / len(clean)


def _delta(current, baseline):
    if not _is_valid(current) or not _is_valid(baseline):
        return float("nan")
    return current - baseline


def build_pitch_effectiveness_deltas(pitch_type_summary):
    """Build effectiveness delta features for each appearance and pitch type."""
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

        output_row = deepcopy(row)
        output_row["pitch_count_current"] = row.get("pitch_count")
        output_row["low_sample_flag"] = bool(row.get("low_sample_flag", False))

        improved_count = 0
        declined_count = 0

        for metric in METRICS:
            current_value = row.get(metric)
            prev_value = prior_rows[-1].get(metric) if prior_rows else float("nan")

            rolling_3_rows = prior_rows[-3:]
            rolling_baseline = _mean([r.get(metric) for r in rolling_3_rows])

            rows_30d = []
            for prior in prior_rows:
                prior_date = _to_date(prior.get("game_date"))
                days_diff = (current_date - prior_date).days
                if 0 < days_diff <= 30:
                    rows_30d.append(prior)
            baseline_30d = _mean([r.get(metric) for r in rows_30d])

            current_season = row.get("season")
            season_prior = [r for r in prior_rows if r.get("season") == current_season]
            season_avg_before = _mean([r.get(metric) for r in season_prior])

            delta_last = _delta(current_value, prev_value)
            delta_roll3 = _delta(current_value, rolling_baseline)
            delta_30d = _delta(current_value, baseline_30d)
            delta_season = _delta(current_value, season_avg_before)

            output_row[f"current_{metric}"] = current_value
            output_row[f"previous_start_{metric}"] = prev_value
            output_row[f"delta_{metric}_last_start"] = delta_last
            output_row[f"rolling_3_start_{metric}_baseline"] = rolling_baseline
            output_row[f"delta_{metric}_rolling_3_start"] = delta_roll3
            output_row[f"{metric}_30d_baseline"] = baseline_30d
            output_row[f"delta_{metric}_30d"] = delta_30d
            output_row[f"season_avg_{metric}_before_start"] = season_avg_before
            output_row[f"delta_{metric}_season_avg"] = delta_season

            if _is_valid(delta_roll3):
                if metric in HIGHER_IS_BETTER:
                    if delta_roll3 > 0:
                        improved_count += 1
                    elif delta_roll3 < 0:
                        declined_count += 1
                elif metric in LOWER_IS_BETTER:
                    if delta_roll3 < 0:
                        improved_count += 1
                    elif delta_roll3 > 0:
                        declined_count += 1

        output_row["effectiveness_improved_flag"] = improved_count >= 2
        output_row["effectiveness_declined_flag"] = declined_count >= 2

        output_rows.append(output_row)
        history.setdefault(key, []).append(deepcopy(row))

    return _from_records(output_rows, pitch_type_summary)

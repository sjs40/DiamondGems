"""Build per-appearance pitch-type summaries."""

from __future__ import annotations

from copy import deepcopy

from diamond_gems.constants import MIN_PITCH_TYPE_COUNT
from diamond_gems.validation import safe_divide, validate_required_columns

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None

IDENTITY_COLUMNS = [
    "appearance_id",
    "pitcher_id",
    "pitcher_name",
    "game_id",
    "game_date",
    "season",
    "opponent_team_id",
]


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


def _is_not_null(value) -> bool:
    if pd is not None:
        return bool(pd.notna(value))
    return value is not None


def _mean(values: list[float]):
    clean_values = [float(value) for value in values if _is_not_null(value)]
    if not clean_values:
        return float("nan")
    return sum(clean_values) / len(clean_values)


def _max(values: list[float]):
    clean_values = [float(value) for value in values if _is_not_null(value)]
    if not clean_values:
        return float("nan")
    return max(clean_values)


def _first_non_null(values: list):
    for value in values:
        if _is_not_null(value):
            return value
    return None


def build_pitcher_pitch_type_summary(pitch_events, appearances):
    """Build one-row-per-appearance-and-pitch-type summary metrics."""
    validate_required_columns(appearances, ["appearance_id"], df_name="appearances")
    validate_required_columns(pitch_events, ["appearance_id", "pitch_type"], df_name="pitch_events")

    appearance_rows = _to_records(appearances)
    pitch_event_rows = _to_records(pitch_events)

    rows_by_appearance: dict[str, list[dict]] = {}
    for row in pitch_event_rows:
        rows_by_appearance.setdefault(row.get("appearance_id"), []).append(deepcopy(row))

    output_rows: list[dict] = []

    for appearance in appearance_rows:
        appearance_id = appearance.get("appearance_id")
        appearance_events = rows_by_appearance.get(appearance_id, [])
        total_pitches = len(appearance_events)

        by_pitch_type: dict[str, list[dict]] = {}
        for row in appearance_events:
            by_pitch_type.setdefault(row.get("pitch_type"), []).append(row)

        for pitch_type, rows in by_pitch_type.items():
            pitch_count = len(rows)
            swings = sum(1 for row in rows if bool(row.get("swing_flag")))
            whiffs = sum(1 for row in rows if bool(row.get("whiff_flag")))
            called_strikes = sum(1 for row in rows if bool(row.get("called_strike_flag")))
            in_zone = sum(1 for row in rows if bool(row.get("in_zone_flag")))
            chases = sum(1 for row in rows if bool(row.get("chase_flag")))
            contacts = max(swings - whiffs, 0)
            out_of_zone = pitch_count - in_zone

            batted_ball_rows = [row for row in rows if bool(row.get("batted_ball_flag"))]
            batted_ball_count = len(batted_ball_rows)

            summary_row = {
                "appearance_id": appearance_id,
                "pitch_type": pitch_type,
                "pitch_name": _first_non_null([row.get("pitch_name") for row in rows]),
                "pitch_count": pitch_count,
                "usage_rate": safe_divide(pitch_count, total_pitches),
                "avg_velocity": _mean([row.get("release_speed") for row in rows]),
                "max_velocity": _max([row.get("release_speed") for row in rows]),
                "avg_spin_rate": _mean([row.get("release_spin_rate") for row in rows]),
                "avg_extension": _mean([row.get("release_extension") for row in rows]),
                "avg_pfx_x": _mean([row.get("pfx_x") for row in rows]),
                "avg_pfx_z": _mean([row.get("pfx_z") for row in rows]),
                "swing_rate": safe_divide(swings, pitch_count),
                "whiff_rate": safe_divide(whiffs, swings),
                "csw_rate": safe_divide(called_strikes + whiffs, pitch_count),
                "zone_rate": safe_divide(in_zone, pitch_count),
                "chase_rate": safe_divide(chases, out_of_zone),
                "called_strike_rate": safe_divide(called_strikes, pitch_count),
                "contact_rate": safe_divide(contacts, swings),
                "batted_ball_count": batted_ball_count,
                "avg_exit_velocity_allowed": _mean([row.get("launch_speed") for row in batted_ball_rows]),
                "hard_hit_rate_allowed": safe_divide(
                    sum(1 for row in batted_ball_rows if bool(row.get("hard_hit_flag"))),
                    batted_ball_count,
                ),
                "xwoba_allowed": _mean(
                    [row.get("estimated_woba_using_speedangle") for row in rows if _is_not_null(row.get("estimated_woba_using_speedangle"))]
                ),
                "woba_allowed": _mean([row.get("woba_value") for row in rows if _is_not_null(row.get("woba_value"))]),
                "low_sample_flag": pitch_count < MIN_PITCH_TYPE_COUNT,
            }

            for column in IDENTITY_COLUMNS:
                if column in appearance:
                    summary_row[column] = appearance.get(column)

            output_rows.append(summary_row)

    return _from_records(output_rows, appearances)

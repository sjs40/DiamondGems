"""Build pitcher start-level summary metrics from pitch events."""

from __future__ import annotations

from copy import deepcopy

from diamond_gems.constants import FASTBALL_PITCH_TYPES
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
    "role",
    "start_number_season",
    "pitches_thrown",
    "batters_faced",
    "innings_pitched",
    "runs_allowed",
    "earned_runs",
]

HIT_EVENTS = {"single", "double", "triple", "home_run"}


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


def build_pitcher_start_summary(pitch_events, appearances):
    """Build one-row-per-appearance summary metrics."""
    validate_required_columns(appearances, ["appearance_id"], df_name="appearances")
    validate_required_columns(pitch_events, ["appearance_id"], df_name="pitch_events")

    appearance_rows = _to_records(appearances)
    pitch_event_rows = _to_records(pitch_events)

    grouped_events: dict[str, list[dict]] = {}
    for row in pitch_event_rows:
        appearance_id = row.get("appearance_id")
        grouped_events.setdefault(appearance_id, []).append(deepcopy(row))

    summary_rows: list[dict] = []

    for appearance in appearance_rows:
        appearance_id = appearance.get("appearance_id")
        rows = grouped_events.get(appearance_id, [])

        pitches = len(rows)
        swings = sum(1 for row in rows if bool(row.get("swing_flag")))
        whiffs = sum(1 for row in rows if bool(row.get("whiff_flag")))
        called_strikes = sum(1 for row in rows if bool(row.get("called_strike_flag")))
        in_zone = sum(1 for row in rows if bool(row.get("in_zone_flag")))
        chases = sum(1 for row in rows if bool(row.get("chase_flag")))
        contacts = max(swings - whiffs, 0)

        batted_ball_rows = [row for row in rows if bool(row.get("batted_ball_flag"))]
        batted_balls_allowed = len(batted_ball_rows)

        hits_allowed = sum(1 for row in rows if row.get("events") in HIT_EVENTS)
        walks = sum(1 for row in rows if bool(row.get("walk_flag")))
        strikeouts = sum(1 for row in rows if bool(row.get("strikeout_flag")))
        home_runs_allowed = sum(1 for row in rows if row.get("events") == "home_run")

        batters_faced = appearance.get("batters_faced", 0)
        out_of_zone = pitches - in_zone

        first_pitch_strike_rate = float("nan")
        if rows and "first_pitch_strike_flag" in rows[0]:
            first_pitch_rows = [row for row in rows if _is_not_null(row.get("first_pitch_strike_flag"))]
            if first_pitch_rows:
                first_pitch_strikes = sum(1 for row in first_pitch_rows if bool(row.get("first_pitch_strike_flag")))
                first_pitch_strike_rate = safe_divide(first_pitch_strikes, len(first_pitch_rows))

        barrel_rate_allowed = float("nan")
        if rows and "barrel_flag" in rows[0]:
            barrel_count = sum(1 for row in batted_ball_rows if bool(row.get("barrel_flag")))
            barrel_rate_allowed = safe_divide(barrel_count, batted_balls_allowed)

        xwoba_rows = [
            row
            for row in rows
            if (bool(row.get("batted_ball_flag")) or bool(row.get("pa_terminal_flag")))
            and _is_not_null(row.get("estimated_woba_using_speedangle"))
        ]
        xwoba_allowed = _mean([row.get("estimated_woba_using_speedangle") for row in xwoba_rows])

        woba_rows = [row for row in rows if _is_not_null(row.get("woba_value"))]
        woba_allowed = _mean([row.get("woba_value") for row in woba_rows])

        fastball_velos = [
            row.get("release_speed")
            for row in rows
            if row.get("pitch_type") in FASTBALL_PITCH_TYPES and _is_not_null(row.get("release_speed"))
        ]
        all_velos = [row.get("release_speed") for row in rows if _is_not_null(row.get("release_speed"))]

        summary_row = {
            "appearance_id": appearance_id,
            "hits_allowed": hits_allowed,
            "walks": walks,
            "strikeouts": strikeouts,
            "home_runs_allowed": home_runs_allowed,
            "k_rate": safe_divide(strikeouts, batters_faced),
            "bb_rate": safe_divide(walks, batters_faced),
            "k_minus_bb_rate": safe_divide(strikeouts, batters_faced)
            - safe_divide(walks, batters_faced),
            "swing_rate": safe_divide(swings, pitches),
            "whiff_rate": safe_divide(whiffs, swings),
            "called_strike_rate": safe_divide(called_strikes, pitches),
            "csw_rate": safe_divide(called_strikes + whiffs, pitches),
            "zone_rate": safe_divide(in_zone, pitches),
            "chase_rate": safe_divide(chases, out_of_zone),
            "contact_rate": safe_divide(contacts, swings),
            "first_pitch_strike_rate": first_pitch_strike_rate,
            "batted_balls_allowed": batted_balls_allowed,
            "avg_exit_velocity_allowed": _mean([row.get("launch_speed") for row in batted_ball_rows]),
            "max_exit_velocity_allowed": _max([row.get("launch_speed") for row in batted_ball_rows]),
            "hard_hit_rate_allowed": safe_divide(
                sum(1 for row in batted_ball_rows if bool(row.get("hard_hit_flag"))),
                batted_balls_allowed,
            ),
            "barrel_rate_allowed": barrel_rate_allowed,
            "avg_launch_angle_allowed": _mean([row.get("launch_angle") for row in batted_ball_rows]),
            "xwoba_allowed": xwoba_allowed,
            "woba_allowed": woba_allowed,
            "xwoba_minus_woba_allowed": xwoba_allowed - woba_allowed,
            "avg_fastball_velo": _mean(fastball_velos),
            "max_fastball_velo": _max(fastball_velos),
            "avg_pitch_velo": _mean(all_velos),
            "max_pitch_velo": _max(all_velos),
        }

        for column in IDENTITY_COLUMNS:
            if column in appearance:
                summary_row[column] = appearance.get(column)

        summary_rows.append(summary_row)

    return _from_records(summary_rows, appearances)

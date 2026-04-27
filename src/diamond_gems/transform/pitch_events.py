"""Pitch event cleaning for MVP pitch_events schema."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from diamond_gems.constants import REQUIRED_RAW_STATCAST_COLUMNS
from diamond_gems.validation import validate_required_columns

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None

SWING_DESCRIPTIONS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "foul_bunt",
    "hit_into_play",
    "hit_into_play_no_out",
    "hit_into_play_score",
}

WHIFF_DESCRIPTIONS = {"swinging_strike", "swinging_strike_blocked", "foul_tip"}
WALK_EVENTS = {"walk", "intent_walk", "hit_by_pitch"}
STRIKEOUT_EVENTS = {"strikeout", "strikeout_double_play"}


# Preserve these source columns if present after normalization.
KEEP_COLUMNS = [
    "release_speed",
    "release_spin_rate",
    "release_extension",
    "pfx_x",
    "pfx_z",
    "plate_x",
    "plate_z",
    "zone",
    "description",
    "events",
    "launch_speed",
    "launch_angle",
    "estimated_woba_using_speedangle",
    "woba_value",
    "balls",
    "strikes",
    "outs_when_up",
    "inning",
    "inning_topbot",
    "pitcher_throws",
    "home_team",
    "away_team",
    "post_home_score",
    "post_away_score",
]


def _to_records(df) -> list[dict]:
    if pd is not None and isinstance(df, pd.DataFrame):
        return df.to_dict("records")
    if hasattr(df, "to_dict"):
        return df.to_dict("records")
    if isinstance(df, list):
        return deepcopy(df)
    raise TypeError("clean_pitch_events expects a DataFrame-like input.")


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


def _to_season(game_date_value) -> int | None:
    if game_date_value is None:
        return None
    if hasattr(game_date_value, "year"):
        return int(game_date_value.year)
    game_date_str = str(game_date_value)
    return int(game_date_str[:4]) if len(game_date_str) >= 4 else None


def _in_zone(zone_value) -> bool:
    if zone_value is None:
        return False
    try:
        zone_num = int(float(zone_value))
    except (TypeError, ValueError):
        return False
    return 1 <= zone_num <= 9


def clean_pitch_events(df):
    """Clean raw Statcast pitch-level rows into MVP pitch_events schema."""
    validate_required_columns(df, REQUIRED_RAW_STATCAST_COLUMNS, df_name="raw_statcast")

    records = _to_records(df)
    cleaned_records: list[dict] = []
    game_pitch_counter: dict = {}
    pulled_at_default = datetime.now(timezone.utc).isoformat()

    source_has_pitch_id = "pitch_id" in getattr(df, "columns", [])
    source_has_data_source = "data_source" in getattr(df, "columns", [])
    source_has_pulled_at = "pulled_at" in getattr(df, "columns", [])

    for row in records:
        raw_row = deepcopy(row)
        game_key = raw_row.get("game_pk")
        game_pitch_counter[game_key] = game_pitch_counter.get(game_key, 0) + 1
        pitch_sequence = game_pitch_counter[game_key]

        cleaned_row = {
            "pitch_id": raw_row.get("pitch_id"),
            "game_id": raw_row.get("game_pk"),
            "game_date": raw_row.get("game_date"),
            "season": _to_season(raw_row.get("game_date")),
            "pitcher_id": raw_row.get("pitcher"),
            "batter_id": raw_row.get("batter"),
            "player_name": raw_row.get("player_name"),
            "data_source": raw_row.get("data_source") if source_has_data_source else "statcast",
            "pulled_at": raw_row.get("pulled_at") if source_has_pulled_at else pulled_at_default,
        }

        if not source_has_pitch_id or not _is_not_null(cleaned_row["pitch_id"]):
            cleaned_row["pitch_id"] = (
                f"{raw_row.get('game_pk')}_{raw_row.get('pitcher')}_{raw_row.get('batter')}_"
                f"{raw_row.get('inning')}_{raw_row.get('inning_topbot')}_"
                f"{raw_row.get('balls')}-{raw_row.get('strikes')}_{pitch_sequence}"
            )

        if not _is_not_null(cleaned_row["data_source"]):
            cleaned_row["data_source"] = "statcast"
        if not _is_not_null(cleaned_row["pulled_at"]):
            cleaned_row["pulled_at"] = pulled_at_default

        for column in KEEP_COLUMNS:
            if column in raw_row:
                cleaned_row[column] = raw_row.get(column)

        description = (cleaned_row.get("description") or "").strip()
        events = cleaned_row.get("events")
        launch_speed = cleaned_row.get("launch_speed")

        swing_flag = description in SWING_DESCRIPTIONS
        whiff_flag = description in WHIFF_DESCRIPTIONS
        called_strike_flag = description == "called_strike"
        csw_flag = called_strike_flag or whiff_flag
        in_zone_flag = _in_zone(cleaned_row.get("zone"))
        chase_flag = swing_flag and not in_zone_flag
        batted_ball_flag = (
            (_is_not_null(events) and _is_not_null(launch_speed))
            or description.startswith("hit_into_play")
        )
        hard_hit_flag = _is_not_null(launch_speed) and float(launch_speed) >= 95
        pa_terminal_flag = _is_not_null(events)
        strikeout_flag = events in STRIKEOUT_EVENTS
        walk_flag = events in WALK_EVENTS
        home_run_flag = events == "home_run"

        cleaned_row.update(
            {
                "swing_flag": swing_flag,
                "whiff_flag": whiff_flag,
                "called_strike_flag": called_strike_flag,
                "csw_flag": csw_flag,
                "in_zone_flag": in_zone_flag,
                "chase_flag": chase_flag,
                "batted_ball_flag": batted_ball_flag,
                "hard_hit_flag": hard_hit_flag,
                "pa_terminal_flag": pa_terminal_flag,
                "strikeout_flag": strikeout_flag,
                "walk_flag": walk_flag,
                "home_run_flag": home_run_flag,
            }
        )

        cleaned_records.append(cleaned_row)

    return _from_records(cleaned_records, df)

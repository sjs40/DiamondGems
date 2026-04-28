"""Lightweight sequencing and order-effects summaries."""

from __future__ import annotations

from copy import deepcopy

from diamond_gems.constants import FASTBALL_PITCH_TYPES
from diamond_gems.validation import safe_divide, validate_required_columns

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None

BREAKING_BALL_TYPES = {"SL", "ST", "CU", "KC", "SV"}
REQUIRED_COLUMNS = ["game_id", "pitcher_id", "pitch_type"]


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


def _mode(values: list[str]):
    if not values:
        return None
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[0][0]


def _whiff_flag(row: dict) -> bool:
    if "whiff_flag" in row:
        return bool(row.get("whiff_flag"))
    return (row.get("description") or "") in {"swinging_strike", "swinging_strike_blocked", "foul_tip"}


def _called_strike_flag(row: dict) -> bool:
    if "called_strike_flag" in row:
        return bool(row.get("called_strike_flag"))
    return (row.get("description") or "") == "called_strike"


def build_pitch_sequencing_summary(pitch_events):
    """Build sequencing summary at appearance_id + pitch_type grain."""
    validate_required_columns(pitch_events, REQUIRED_COLUMNS, df_name="pitch_events")

    rows = _to_records(pitch_events)
    indexed_rows = []
    for idx, row in enumerate(rows):
        row_copy = deepcopy(row)
        if not row_copy.get("appearance_id"):
            row_copy["appearance_id"] = f"{row_copy.get('game_id')}_{row_copy.get('pitcher_id')}"
        row_copy["_row_order"] = idx
        indexed_rows.append(row_copy)

    by_game_pitcher: dict[tuple, list[dict]] = {}
    for row in indexed_rows:
        key = (row.get("game_id"), row.get("pitcher_id"))
        by_game_pitcher.setdefault(key, []).append(row)

    with_previous: list[dict] = []
    for _, group_rows in by_game_pitcher.items():
        sorted_group = sorted(group_rows, key=lambda r: r.get("_row_order"))
        prev_pitch_type = None
        for row in sorted_group:
            row["previous_pitch_type"] = prev_pitch_type
            prev_pitch_type = row.get("pitch_type")
            row["csw_flag"] = _whiff_flag(row) or _called_strike_flag(row)
            row["whiff_flag"] = _whiff_flag(row)
            with_previous.append(row)

    by_appearance_pitch: dict[tuple, list[dict]] = {}
    for row in with_previous:
        key = (row.get("appearance_id"), row.get("pitch_type"))
        by_appearance_pitch.setdefault(key, []).append(row)

    output_rows: list[dict] = []
    for (appearance_id, pitch_type), group_rows in by_appearance_pitch.items():
        previous_values = [row.get("previous_pitch_type") for row in group_rows if row.get("previous_pitch_type")]

        after_fastball = [row for row in group_rows if row.get("previous_pitch_type") in FASTBALL_PITCH_TYPES]
        after_breaking = [row for row in group_rows if row.get("previous_pitch_type") in BREAKING_BALL_TYPES]

        row0 = group_rows[0]
        output_rows.append(
            {
                "appearance_id": appearance_id,
                "pitcher_id": row0.get("pitcher_id"),
                "pitcher_name": row0.get("pitcher_name"),
                "game_date": row0.get("game_date"),
                "season": row0.get("season"),
                "pitch_type": pitch_type,
                "pitch_name": row0.get("pitch_name"),
                "pitch_count": len(group_rows),
                "previous_pitch_type": _mode(previous_values),
                "pitches_after_fastball": len(after_fastball),
                "whiffs_after_fastball": sum(1 for row in after_fastball if row.get("whiff_flag")),
                "whiff_rate_after_fastball": safe_divide(
                    sum(1 for row in after_fastball if row.get("whiff_flag")), len(after_fastball)
                ),
                "csw_rate_after_fastball": safe_divide(
                    sum(1 for row in after_fastball if row.get("csw_flag")), len(after_fastball)
                ),
                "pitches_after_breaking_ball": len(after_breaking),
                "whiffs_after_breaking_ball": sum(1 for row in after_breaking if row.get("whiff_flag")),
                "whiff_rate_after_breaking_ball": safe_divide(
                    sum(1 for row in after_breaking if row.get("whiff_flag")), len(after_breaking)
                ),
                "csw_rate_after_breaking_ball": safe_divide(
                    sum(1 for row in after_breaking if row.get("csw_flag")), len(after_breaking)
                ),
            }
        )

    return _from_records(output_rows, pitch_events)

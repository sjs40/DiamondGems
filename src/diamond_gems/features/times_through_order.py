"""Times-through-the-order split features and penalty summaries."""

from __future__ import annotations

from copy import deepcopy

from diamond_gems.validation import safe_divide, validate_required_columns

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None

REQUIRED_COLUMNS = ["game_id", "pitcher_id", "pa_terminal_flag"]


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


def _is_valid(value) -> bool:
    return value is not None and value == value


def _mean(values: list[float]):
    valid = [float(v) for v in values if _is_valid(v)]
    if not valid:
        return float("nan")
    return sum(valid) / len(valid)


def _time_through_order(pa_number: int) -> int:
    if pa_number <= 9:
        return 1
    if pa_number <= 18:
        return 2
    if pa_number <= 27:
        return 3
    return 4


def build_times_through_order_splits(pitch_events):
    """Build one-row-per-appearance and time-through-order split summary."""
    validate_required_columns(pitch_events, REQUIRED_COLUMNS, df_name="pitch_events")

    rows = _to_records(pitch_events)
    indexed_rows = []
    for idx, row in enumerate(rows):
        row_copy = deepcopy(row)
        if not row_copy.get("appearance_id"):
            row_copy["appearance_id"] = f"{row_copy.get('game_id')}_{row_copy.get('pitcher_id')}"
        row_copy["_row_order"] = idx
        indexed_rows.append(row_copy)

    by_appearance: dict[str, list[dict]] = {}
    for row in indexed_rows:
        by_appearance.setdefault(row.get("appearance_id"), []).append(row)

    tagged_rows: list[dict] = []
    for _, appearance_rows in by_appearance.items():
        sorted_rows = sorted(appearance_rows, key=lambda r: r.get("_row_order"))
        pa_number = 1
        for row in sorted_rows:
            row["pa_number"] = pa_number
            row["time_through_order"] = _time_through_order(pa_number)
            tagged_rows.append(row)
            if bool(row.get("pa_terminal_flag")):
                pa_number += 1

    by_split: dict[tuple, list[dict]] = {}
    for row in tagged_rows:
        key = (row.get("appearance_id"), row.get("time_through_order"))
        by_split.setdefault(key, []).append(row)

    output_rows: list[dict] = []
    for (appearance_id, tto), split_rows in by_split.items():
        row0 = split_rows[0]
        batter_numbers_terminal = {
            row.get("pa_number") for row in split_rows if bool(row.get("pa_terminal_flag"))
        }
        batters_faced = len(batter_numbers_terminal)

        swings = sum(1 for row in split_rows if bool(row.get("swing_flag")))
        whiffs = sum(1 for row in split_rows if bool(row.get("whiff_flag")))
        called_strikes = sum(1 for row in split_rows if bool(row.get("called_strike_flag")))
        contacts = max(swings - whiffs, 0)

        batted_rows = [row for row in split_rows if bool(row.get("batted_ball_flag"))]

        output_rows.append(
            {
                "appearance_id": appearance_id,
                "pitcher_id": row0.get("pitcher_id"),
                "pitcher_name": row0.get("pitcher_name"),
                "game_date": row0.get("game_date"),
                "season": row0.get("season"),
                "time_through_order": tto,
                "batters_faced": batters_faced,
                "pitches_thrown": len(split_rows),
                "k_rate": safe_divide(
                    sum(1 for row in split_rows if bool(row.get("strikeout_flag"))),
                    batters_faced,
                ),
                "bb_rate": safe_divide(
                    sum(1 for row in split_rows if bool(row.get("walk_flag"))),
                    batters_faced,
                ),
                "whiff_rate": safe_divide(whiffs, swings),
                "csw_rate": safe_divide(called_strikes + whiffs, len(split_rows)),
                "contact_rate": safe_divide(contacts, swings),
                "woba_allowed": _mean([row.get("woba_value") for row in split_rows]),
                "xwoba_allowed": _mean([row.get("estimated_woba_using_speedangle") for row in split_rows]),
                "hard_hit_rate_allowed": safe_divide(
                    sum(1 for row in batted_rows if bool(row.get("hard_hit_flag"))),
                    len(batted_rows),
                ),
            }
        )

    return _from_records(output_rows, pitch_events)


def build_tto_penalty_summary(tto_splits):
    """Build one-row-per-appearance TTO penalty summary from split table."""
    rows = _to_records(tto_splits)

    by_appearance: dict[str, list[dict]] = {}
    for row in rows:
        by_appearance.setdefault(row.get("appearance_id"), []).append(deepcopy(row))

    output_rows: list[dict] = []
    for appearance_id, appearance_rows in by_appearance.items():
        tto1 = next((row for row in appearance_rows if row.get("time_through_order") == 1), None)
        tto3 = next((row for row in appearance_rows if row.get("time_through_order") == 3), None)

        if not tto1 or not tto3:
            whiff_penalty = float("nan")
            csw_penalty = float("nan")
            xwoba_penalty = float("nan")
            note = "TTO 3 unavailable"
        else:
            whiff_penalty = tto3.get("whiff_rate") - tto1.get("whiff_rate")
            csw_penalty = tto3.get("csw_rate") - tto1.get("csw_rate")
            xwoba_penalty = tto3.get("xwoba_allowed") - tto1.get("xwoba_allowed")
            note = "TTO penalty calculated"

        output_rows.append(
            {
                "appearance_id": appearance_id,
                "tto_penalty_whiff": whiff_penalty,
                "tto_penalty_csw": csw_penalty,
                "tto_penalty_xwoba": xwoba_penalty,
                "tto_penalty_note": note,
            }
        )

    return _from_records(output_rows, tto_splits)

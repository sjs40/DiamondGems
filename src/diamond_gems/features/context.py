"""Basic park factor and game-state context placeholders for MVP."""

from __future__ import annotations

from copy import deepcopy

from diamond_gems.validation import validate_required_columns

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None


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


def add_basic_park_context(pitcher_start_summary):
    """Add placeholder park factor fields for MVP when factors are unavailable."""
    rows = _to_records(pitcher_start_summary)
    output_rows = []
    for row in rows:
        row_copy = deepcopy(row)
        row_copy["park_factor_runs"] = row_copy.get("park_factor_runs")
        row_copy["park_factor_hr"] = row_copy.get("park_factor_hr")
        row_copy["park_factor_hits"] = row_copy.get("park_factor_hits")
        row_copy["park_context_note"] = "park factor unavailable in MVP"
        output_rows.append(row_copy)
    return _from_records(output_rows, pitcher_start_summary)


def build_game_state_context(pitch_events):
    """Build one-row-per-appearance game-state proxy context."""
    validate_required_columns(pitch_events, ["pitcher_id"], df_name="pitch_events")

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

    base_state_available = all(
        any(column in row for row in indexed_rows) for column in ["on_1b", "on_2b", "on_3b"]
    )

    output_rows: list[dict] = []
    for appearance_id, appearance_rows in by_appearance.items():
        row0 = appearance_rows[0]

        margins = []
        for row in appearance_rows:
            if _is_valid(row.get("post_home_score")) and _is_valid(row.get("post_away_score")):
                margins.append(abs(row.get("post_home_score") - row.get("post_away_score")))

        avg_margin = sum(margins) / len(margins) if margins else float("nan")

        high_leverage = 0
        low_leverage = 0
        for row in appearance_rows:
            inning_val = row.get("inning")
            margin = None
            if _is_valid(row.get("post_home_score")) and _is_valid(row.get("post_away_score")):
                margin = abs(row.get("post_home_score") - row.get("post_away_score"))

            if margin is not None and _is_valid(inning_val):
                if inning_val >= 7 and margin <= 2:
                    high_leverage += 1
                if margin >= 6:
                    low_leverage += 1

        if base_state_available:
            bases_empty = sum(
                1
                for row in appearance_rows
                if not _is_valid(row.get("on_1b"))
                and not _is_valid(row.get("on_2b"))
                and not _is_valid(row.get("on_3b"))
            )
            runners_on = len(appearance_rows) - bases_empty
            note = "base-state context included"
        else:
            bases_empty = float("nan")
            runners_on = float("nan")
            note = "base-state columns unavailable in MVP"

        output_rows.append(
            {
                "appearance_id": appearance_id,
                "pitcher_id": row0.get("pitcher_id"),
                "pitcher_name": row0.get("pitcher_name"),
                "game_date": row0.get("game_date"),
                "season": row0.get("season"),
                "pitches_with_bases_empty": bases_empty,
                "pitches_with_runners_on": runners_on,
                "high_leverage_proxy_pitches": high_leverage,
                "low_leverage_proxy_pitches": low_leverage,
                "avg_score_margin_when_pitching": avg_margin,
                "game_state_context_note": note,
            }
        )

    return _from_records(output_rows, pitch_events)

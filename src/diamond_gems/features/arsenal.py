"""Arsenal concentration and pitch-mix volatility feature builders."""

from __future__ import annotations

from copy import deepcopy

from diamond_gems.validation import validate_required_columns

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None


REQUIRED_ARSENAL_COLUMNS = [
    "appearance_id",
    "pitcher_id",
    "pitcher_name",
    "game_date",
    "season",
    "pitch_type",
    "usage_rate",
]

REQUIRED_VOL_COLUMNS = [
    "appearance_id",
    "pitcher_id",
    "pitcher_name",
    "game_date",
    "delta_usage_last_start",
    "delta_usage_rolling_3_start",
    "delta_usage_30d",
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


def _is_valid_number(value) -> bool:
    return value is not None and value == value


def build_arsenal_concentration(pitch_type_summary):
    """Build one-row-per-appearance arsenal concentration features."""
    validate_required_columns(pitch_type_summary, REQUIRED_ARSENAL_COLUMNS, df_name="pitch_type_summary")

    rows = _to_records(pitch_type_summary)
    by_appearance: dict[str, list[dict]] = {}
    for row in rows:
        by_appearance.setdefault(row.get("appearance_id"), []).append(deepcopy(row))

    output_rows: list[dict] = []
    for appearance_id, appearance_rows in by_appearance.items():
        sorted_rows = sorted(
            appearance_rows,
            key=lambda r: (r.get("usage_rate") if _is_valid_number(r.get("usage_rate")) else -1),
            reverse=True,
        )

        top_1 = sorted_rows[:1]
        top_2 = sorted_rows[:2]
        top_3 = sorted_rows[:3]

        top_1_pitch_type = top_1[0].get("pitch_type") if top_1 else None
        top_1_pitch_usage = top_1[0].get("usage_rate") if top_1 else float("nan")

        top_2_pitch_types = [row.get("pitch_type") for row in top_2]
        top_2_pitch_usage = sum(row.get("usage_rate") for row in top_2 if _is_valid_number(row.get("usage_rate")))

        top_3_pitch_types = [row.get("pitch_type") for row in top_3]
        top_3_pitch_usage = sum(row.get("usage_rate") for row in top_3 if _is_valid_number(row.get("usage_rate")))

        first_row = sorted_rows[0]
        output_rows.append(
            {
                "appearance_id": appearance_id,
                "pitcher_id": first_row.get("pitcher_id"),
                "pitcher_name": first_row.get("pitcher_name"),
                "game_date": first_row.get("game_date"),
                "season": first_row.get("season"),
                "pitch_type_count": len(sorted_rows),
                "top_1_pitch_type": top_1_pitch_type,
                "top_1_pitch_usage": top_1_pitch_usage,
                "top_2_pitch_types": top_2_pitch_types,
                "top_2_pitch_usage": top_2_pitch_usage,
                "top_3_pitch_types": top_3_pitch_types,
                "top_3_pitch_usage": top_3_pitch_usage,
                "arsenal_concentration_score": top_2_pitch_usage,
            }
        )

    return _from_records(output_rows, pitch_type_summary)


def build_pitch_mix_volatility(usage_deltas):
    """Build one-row-per-appearance pitch-mix volatility features."""
    validate_required_columns(usage_deltas, REQUIRED_VOL_COLUMNS, df_name="usage_deltas")

    rows = _to_records(usage_deltas)
    by_appearance: dict[str, list[dict]] = {}
    for row in rows:
        by_appearance.setdefault(row.get("appearance_id"), []).append(deepcopy(row))

    output_rows: list[dict] = []
    for appearance_id, appearance_rows in by_appearance.items():
        first_row = appearance_rows[0]

        volatility_last = sum(
            abs(row.get("delta_usage_last_start"))
            for row in appearance_rows
            if _is_valid_number(row.get("delta_usage_last_start"))
        )
        volatility_roll3 = sum(
            abs(row.get("delta_usage_rolling_3_start"))
            for row in appearance_rows
            if _is_valid_number(row.get("delta_usage_rolling_3_start"))
        )
        volatility_30d = sum(
            abs(row.get("delta_usage_30d"))
            for row in appearance_rows
            if _is_valid_number(row.get("delta_usage_30d"))
        )

        output_rows.append(
            {
                "appearance_id": appearance_id,
                "pitcher_id": first_row.get("pitcher_id"),
                "pitcher_name": first_row.get("pitcher_name"),
                "game_date": first_row.get("game_date"),
                "pitch_mix_volatility_last_start": volatility_last,
                "pitch_mix_volatility_rolling_3_start": volatility_roll3,
                "pitch_mix_volatility_30d": volatility_30d,
                "major_mix_change_flag": volatility_last >= 0.25,
            }
        )

    return _from_records(output_rows, usage_deltas)

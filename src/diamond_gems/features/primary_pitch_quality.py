"""Primary pitch quality versus results gap features."""

from __future__ import annotations

from copy import deepcopy

from diamond_gems.validation import validate_required_columns

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None

REQUIRED_COLUMNS = [
    "appearance_id",
    "pitcher_id",
    "pitcher_name",
    "game_date",
    "season",
    "pitch_type",
    "pitch_name",
    "usage_rate",
    "avg_velocity",
    "whiff_rate",
    "csw_rate",
    "xwoba_allowed",
    "woba_allowed",
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


def _is_valid(value) -> bool:
    return value is not None and value == value


def build_primary_pitch_quality_gap(pitch_type_summary):
    """Build one-row-per-appearance primary pitch quality gap summary."""
    validate_required_columns(pitch_type_summary, REQUIRED_COLUMNS, df_name="pitch_type_summary")

    rows = _to_records(pitch_type_summary)
    by_appearance: dict[str, list[dict]] = {}
    for row in rows:
        by_appearance.setdefault(row.get("appearance_id"), []).append(deepcopy(row))

    output_rows: list[dict] = []
    for appearance_id, appearance_rows in by_appearance.items():
        primary_row = sorted(
            appearance_rows,
            key=lambda r: (
                r.get("usage_rate") if _is_valid(r.get("usage_rate")) else -1,
                str(r.get("pitch_type")),
            ),
            reverse=True,
        )[0]

        xwoba = primary_row.get("xwoba_allowed")
        woba = primary_row.get("woba_allowed")
        damage_gap = woba - xwoba if _is_valid(woba) and _is_valid(xwoba) else float("nan")

        good_process_bad_results = bool(
            _is_valid(xwoba)
            and _is_valid(damage_gap)
            and xwoba <= 0.300
            and damage_gap >= 0.050
        )
        bad_process_good_results = bool(
            _is_valid(xwoba)
            and _is_valid(damage_gap)
            and xwoba >= 0.375
            and damage_gap <= -0.050
        )

        output_rows.append(
            {
                "appearance_id": appearance_id,
                "pitcher_id": primary_row.get("pitcher_id"),
                "pitcher_name": primary_row.get("pitcher_name"),
                "game_date": primary_row.get("game_date"),
                "season": primary_row.get("season"),
                "primary_pitch_type": primary_row.get("pitch_type"),
                "primary_pitch_name": primary_row.get("pitch_name"),
                "primary_pitch_usage_rate": primary_row.get("usage_rate"),
                "primary_pitch_avg_velocity": primary_row.get("avg_velocity"),
                "primary_pitch_whiff_rate": primary_row.get("whiff_rate"),
                "primary_pitch_csw_rate": primary_row.get("csw_rate"),
                "primary_pitch_xwoba_allowed": xwoba,
                "primary_pitch_woba_allowed": woba,
                "primary_pitch_damage_gap": damage_gap,
                "primary_pitch_good_process_bad_results_flag": good_process_bad_results,
                "primary_pitch_bad_process_good_results_flag": bad_process_good_results,
            }
        )

    return _from_records(output_rows, pitch_type_summary)

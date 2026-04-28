"""Stability and consistency scoring for pitcher-level appearance signals."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

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


def _to_date(value):
    if value is None:
        return datetime.min.date()
    if hasattr(value, "date") and not isinstance(value, str):
        return value.date() if hasattr(value, "hour") else value
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return datetime.min.date()


def _appearance_sort_key(row: dict) -> tuple:
    return (
        _to_date(row.get("game_date")),
        str(row.get("appearance_id") if row.get("appearance_id") is not None else ""),
    )


def _score_from_streak(streak: int) -> float:
    if streak <= 0:
        return 0.0
    return min(streak / 3.0, 1.0)


def _mean_available(values: list[float]):
    clean = [value for value in values if value == value]
    if not clean:
        return float("nan")
    return sum(clean) / len(clean)


def _stability_note(overall_score: float) -> str:
    if overall_score != overall_score:
        return "Insufficient stability data"
    if overall_score >= 0.67:
        return "High stability"
    if overall_score >= 0.34:
        return "Moderate stability"
    return "Low stability"


def build_stability_scores(velocity_deltas, usage_deltas, pitch_effectiveness_deltas):
    """Build one-row-per-appearance stability scores using consecutive-start signals."""
    velocity_rows = _to_records(velocity_deltas)
    usage_rows = _to_records(usage_deltas)
    effectiveness_rows = _to_records(pitch_effectiveness_deltas)

    appearances: dict[str, dict] = {}

    def ensure_base(row: dict) -> dict:
        appearance_id = row.get("appearance_id")
        if appearance_id not in appearances:
            appearances[appearance_id] = {
                "appearance_id": appearance_id,
                "pitcher_id": row.get("pitcher_id"),
                "pitcher_name": row.get("pitcher_name"),
                "game_date": row.get("game_date"),
                "velo_signal": False,
                "usage_signal": False,
                "effect_signal": False,
                "velo_available": False,
                "usage_available": False,
                "effect_available": False,
            }
        base = appearances[appearance_id]
        if base.get("pitcher_id") is None:
            base["pitcher_id"] = row.get("pitcher_id")
        if base.get("pitcher_name") is None:
            base["pitcher_name"] = row.get("pitcher_name")
        if base.get("game_date") is None:
            base["game_date"] = row.get("game_date")
        return base

    for row in velocity_rows:
        base = ensure_base(row)
        base["velo_available"] = True
        base["velo_signal"] = base["velo_signal"] or bool(row.get("strong_velo_spike_flag"))

    for row in usage_rows:
        base = ensure_base(row)
        base["usage_available"] = True
        base["usage_signal"] = base["usage_signal"] or bool(row.get("major_usage_spike_flag")) or bool(row.get("major_usage_drop_flag"))

    for row in effectiveness_rows:
        base = ensure_base(row)
        base["effect_available"] = True
        base["effect_signal"] = base["effect_signal"] or bool(row.get("effectiveness_improved_flag"))

    by_pitcher: dict[str, list[dict]] = {}
    for appearance in appearances.values():
        by_pitcher.setdefault(appearance.get("pitcher_id"), []).append(appearance)

    output_rows: list[dict] = []
    for pitcher_id, pitcher_rows in by_pitcher.items():
        sorted_rows = sorted(pitcher_rows, key=_appearance_sort_key)

        velo_streak = 0
        usage_streak = 0
        effect_streak = 0

        for row in sorted_rows:
            velo_streak = velo_streak + 1 if row.get("velo_signal") else 0
            usage_streak = usage_streak + 1 if row.get("usage_signal") else 0
            effect_streak = effect_streak + 1 if row.get("effect_signal") else 0

            velo_score = _score_from_streak(velo_streak) if row.get("velo_available") else float("nan")
            usage_score = _score_from_streak(usage_streak) if row.get("usage_available") else float("nan")
            effect_score = _score_from_streak(effect_streak) if row.get("effect_available") else float("nan")
            overall_score = _mean_available([velo_score, usage_score, effect_score])

            output_rows.append(
                {
                    "appearance_id": row.get("appearance_id"),
                    "pitcher_id": pitcher_id,
                    "pitcher_name": row.get("pitcher_name"),
                    "game_date": row.get("game_date"),
                    "velo_stability_score": velo_score,
                    "usage_stability_score": usage_score,
                    "effectiveness_stability_score": effect_score,
                    "overall_stability_score": overall_score,
                    "consecutive_velo_spike_starts": velo_streak,
                    "consecutive_major_usage_change_starts": usage_streak,
                    "consecutive_effectiveness_improvement_starts": effect_streak,
                    "stability_note": _stability_note(overall_score),
                }
            )

    template = velocity_deltas if velocity_rows else (usage_deltas if usage_rows else pitch_effectiveness_deltas)
    return _from_records(output_rows, template)

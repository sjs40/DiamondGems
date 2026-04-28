"""Confidence scoring for appearance-level analytics outputs."""

from __future__ import annotations

from copy import deepcopy

from diamond_gems.constants import MIN_PITCH_TYPE_COUNT

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None


def _to_records(df) -> list[dict]:
    if df is None:
        return []
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


def _score_linear(value, acceptable: float, strong: float) -> float:
    if value is None or value != value:
        return float("nan")
    if value <= 0:
        return 0.0
    if value <= acceptable:
        return max(0.0, min(0.5, (value / acceptable) * 0.5))
    if value >= strong:
        return 1.0
    span = strong - acceptable
    return 0.5 + ((value - acceptable) / span) * 0.5


def _mean_available(values: list[float]):
    clean = [v for v in values if v == v]
    if not clean:
        return float("nan")
    return sum(clean) / len(clean)


def _tier(score: float) -> str:
    if score != score:
        return "low"
    if score >= 0.75:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"


def build_confidence_scores(
    appearances,
    pitcher_start_summary,
    pitch_type_summary,
    opponent_adjusted_metrics=None,
):
    """Build one-row-per-appearance confidence scores."""
    appearance_rows = _to_records(appearances)
    start_rows = _to_records(pitcher_start_summary)
    pitch_type_rows = _to_records(pitch_type_summary)
    opp_rows = _to_records(opponent_adjusted_metrics)

    start_lookup = {row.get("appearance_id"): row for row in start_rows}
    opp_lookup = {row.get("appearance_id"): row for row in opp_rows}

    pitch_types_by_appearance: dict[str, list[dict]] = {}
    for row in pitch_type_rows:
        pitch_types_by_appearance.setdefault(row.get("appearance_id"), []).append(row)

    output_rows = []
    for app in appearance_rows:
        appearance_id = app.get("appearance_id")
        start = start_lookup.get(appearance_id, {})
        opp = opp_lookup.get(appearance_id, {})
        pt_rows = pitch_types_by_appearance.get(appearance_id, [])

        pitches_thrown = start.get("pitches_thrown")
        batters_faced = start.get("batters_faced")

        pitch_volume_score = _score_linear(pitches_thrown, acceptable=50, strong=90)
        batter_volume_score = _score_linear(batters_faced, acceptable=18, strong=25)

        if pt_rows:
            qualified = sum(1 for row in pt_rows if (row.get("pitch_count") or 0) >= MIN_PITCH_TYPE_COUNT)
            pitch_type_sample_score = qualified / len(pt_rows)
        else:
            pitch_type_sample_score = float("nan")

        opponent_context_score = _score_linear(opp.get("opponent_qualified_pa"), acceptable=80, strong=150)

        baseline_depth_score = float("nan")

        overall = _mean_available(
            [
                pitch_volume_score,
                batter_volume_score,
                pitch_type_sample_score,
                opponent_context_score,
                baseline_depth_score,
            ]
        )

        tier = _tier(overall)
        note = "confidence calculated" if overall == overall else "insufficient confidence inputs"

        output_rows.append(
            {
                "appearance_id": appearance_id,
                "pitcher_id": app.get("pitcher_id"),
                "pitcher_name": app.get("pitcher_name"),
                "game_date": app.get("game_date"),
                "pitch_volume_score": pitch_volume_score,
                "batter_volume_score": batter_volume_score,
                "pitch_type_sample_score": pitch_type_sample_score,
                "opponent_context_score": opponent_context_score,
                "baseline_depth_score": baseline_depth_score,
                "overall_confidence_score": overall,
                "confidence_tier": tier,
                "confidence_note": note,
            }
        )

    return _from_records(output_rows, appearances)

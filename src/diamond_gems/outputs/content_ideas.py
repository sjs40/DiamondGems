"""Content idea generation from pitcher signal flags."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "extreme": 4}


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


def _confidence_label(score) -> str:
    if score is None or score != score:
        return "low"
    if score >= 0.75:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"


def build_content_ideas(flags):
    """Build one-row-per-content-idea table from high-priority flags."""
    rows = _to_records(flags)

    grouped: dict[tuple, list[dict]] = {}
    for row in rows:
        grouped.setdefault((row.get("pitcher_id"), row.get("appearance_id")), []).append(deepcopy(row))

    created_date = datetime.now(timezone.utc).date().isoformat()
    ideas = []

    for (pitcher_id, appearance_id), group_rows in grouped.items():
        high_rows = [r for r in group_rows if SEVERITY_RANK.get(str(r.get("severity", "low")).lower(), 1) >= 3]
        if not high_rows:
            continue

        strongest = sorted(
            high_rows,
            key=lambda r: (
                SEVERITY_RANK.get(str(r.get("severity", "low")).lower(), 1),
                r.get("percentile_score") if r.get("percentile_score") is not None else -1,
                r.get("confidence_score") if r.get("confidence_score") is not None else -1,
            ),
            reverse=True,
        )[0]

        pitcher_name = strongest.get("pitcher_name") or "Pitcher"
        signal_name = strongest.get("signal_name") or "notable signal"
        category = strongest.get("signal_category") or "signal"
        confidence_score = strongest.get("confidence_score")

        ideas.append(
            {
                "content_id": f"{appearance_id}_{signal_name}".replace(" ", "_").lower(),
                "created_date": created_date,
                "pitcher_id": pitcher_id,
                "pitcher_name": pitcher_name,
                "team_id": strongest.get("team_id") or strongest.get("opponent_team_id"),
                "appearance_id": appearance_id,
                "primary_signal_category": category,
                "primary_signal_name": signal_name,
                "headline_angle": f"{pitcher_name}: {signal_name.title()}", 
                "thesis": f"{pitcher_name} showed a {signal_name} signal that may indicate a meaningful performance shift.",
                "supporting_metric_1": "raw_value",
                "supporting_metric_1_value": strongest.get("raw_value"),
                "supporting_metric_2": "delta_value",
                "supporting_metric_2_value": strongest.get("delta_value"),
                "supporting_metric_3": "percentile_score",
                "supporting_metric_3_value": strongest.get("percentile_score"),
                "opponent_context": strongest.get("context_note"),
                "confidence": _confidence_label(confidence_score),
                "content_format": "short_form_video",
                "status": "new",
                "notes": strongest.get("auto_generated_angle"),
            }
        )

    return _from_records(ideas, flags)

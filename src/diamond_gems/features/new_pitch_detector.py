"""Detection of new pitches, reintroductions, and pitch-mix spikes."""

from __future__ import annotations

from copy import deepcopy

from diamond_gems.constants import (
    MAJOR_USAGE_SPIKE_THRESHOLD,
    NEW_PITCH_CURRENT_USAGE_MIN,
    NEW_PITCH_MIN_COUNT,
    NEW_PITCH_PREVIOUS_USAGE_MAX,
)
from diamond_gems.validation import validate_required_columns

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None

USAGE_REQUIRED = [
    "appearance_id",
    "pitcher_id",
    "pitch_type",
    "game_date",
    "current_usage_rate",
    "previous_start_usage_rate",
    "delta_usage_last_start",
    "pitch_count_current",
    "pitch_count_previous_start",
    "first_start_usage_rate",
]

SUMMARY_REQUIRED = [
    "appearance_id",
    "pitcher_id",
    "pitch_type",
    "pitch_name",
    "whiff_rate",
    "csw_rate",
    "xwoba_allowed",
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


def _confidence_score(current_usage: float, current_count: float, confirmed: bool) -> float:
    usage_component = min(max(current_usage, 0.0), 1.0) * 0.6
    count_component = min(max(current_count, 0.0) / 20.0, 1.0) * 0.3
    confirm_component = 0.1 if confirmed else 0.0
    return min(1.0, max(0.0, usage_component + count_component + confirm_component))


def build_new_pitch_detector(usage_deltas, pitch_type_summary):
    """Build one-row-per-detected-event pitch detection table."""
    validate_required_columns(usage_deltas, USAGE_REQUIRED, df_name="usage_deltas")
    validate_required_columns(pitch_type_summary, SUMMARY_REQUIRED, df_name="pitch_type_summary")

    usage_rows = _to_records(usage_deltas)
    summary_rows = _to_records(pitch_type_summary)

    summary_lookup = {
        (row.get("appearance_id"), row.get("pitcher_id"), row.get("pitch_type")): row
        for row in summary_rows
    }

    by_key: dict[tuple, list[dict]] = {}
    for row in usage_rows:
        key = (row.get("pitcher_id"), row.get("pitch_type"))
        by_key.setdefault(key, []).append(deepcopy(row))

    detections: list[dict] = []

    for (pitcher_id, pitch_type), rows in by_key.items():
        rows_sorted = sorted(rows, key=lambda r: (str(r.get("game_date")), str(r.get("appearance_id"))))

        for idx, row in enumerate(rows_sorted):
            prev_usage = row.get("previous_start_usage_rate")
            current_usage = row.get("current_usage_rate")
            delta_usage = row.get("delta_usage_last_start")
            current_count = row.get("pitch_count_current")
            previous_count = row.get("pitch_count_previous_start")

            history_before = rows_sorted[:idx]
            ever_dropped_below_reintro = any(
                _is_valid(prior.get("current_usage_rate")) and prior.get("current_usage_rate") < 0.03
                for prior in history_before
            )

            is_new_pitch = bool(
                _is_valid(prev_usage)
                and _is_valid(current_usage)
                and _is_valid(current_count)
                and prev_usage < NEW_PITCH_PREVIOUS_USAGE_MAX
                and current_usage >= NEW_PITCH_CURRENT_USAGE_MIN
                and current_count >= NEW_PITCH_MIN_COUNT
            )
            is_reintro = bool(
                _is_valid(row.get("first_start_usage_rate"))
                and _is_valid(current_usage)
                and row.get("first_start_usage_rate") >= 0.05
                and ever_dropped_below_reintro
                and current_usage >= 0.12
            )
            is_spike = bool(
                _is_valid(prev_usage)
                and _is_valid(delta_usage)
                and prev_usage >= NEW_PITCH_PREVIOUS_USAGE_MAX
                and delta_usage >= MAJOR_USAGE_SPIKE_THRESHOLD
            )

            detection_candidates = []
            if is_new_pitch:
                detection_candidates.append(("new_pitch", lambda r: r.get("current_usage_rate") >= NEW_PITCH_CURRENT_USAGE_MIN))
            if is_reintro:
                detection_candidates.append(("pitch_reintroduction", lambda r: r.get("current_usage_rate") >= 0.12))
            if is_spike:
                detection_candidates.append(("pitch_mix_spike", lambda r: r.get("delta_usage_last_start") >= MAJOR_USAGE_SPIKE_THRESHOLD))

            for detection_type, threshold_fn in detection_candidates:
                streak = 0
                for prior in reversed(rows_sorted[: idx + 1]):
                    if threshold_fn(prior):
                        streak += 1
                    else:
                        break

                confirmed = streak >= 2
                summary_row = summary_lookup.get((row.get("appearance_id"), pitcher_id, pitch_type), {})

                detections.append(
                    {
                        "detection_id": f"{row.get('appearance_id')}_{pitcher_id}_{pitch_type}_{detection_type}",
                        "pitcher_id": pitcher_id,
                        "pitcher_name": row.get("pitcher_name") or summary_row.get("pitcher_name"),
                        "pitch_type": pitch_type,
                        "pitch_name": summary_row.get("pitch_name"),
                        "first_detected_date": row.get("game_date"),
                        "appearance_id_detected": row.get("appearance_id"),
                        "previous_usage_rate": prev_usage,
                        "current_usage_rate": current_usage,
                        "delta_usage": delta_usage,
                        "previous_pitch_count": previous_count,
                        "current_pitch_count": current_count,
                        "consecutive_starts_above_threshold": streak,
                        "detection_type": detection_type,
                        "confirmed_flag": confirmed,
                        "confidence_score": _confidence_score(current_usage or 0.0, current_count or 0.0, confirmed),
                        "whiff_rate_current_start": summary_row.get("whiff_rate"),
                        "csw_rate_current_start": summary_row.get("csw_rate"),
                        "xwoba_allowed_current_start": summary_row.get("xwoba_allowed"),
                    }
                )

    template = usage_deltas if usage_rows else pitch_type_summary
    return _from_records(detections, template)

"""Pitcher signal flag generation for downstream content workflows."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

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


def _is_valid(v) -> bool:
    return v is not None and v == v


def build_pitcher_flags(
    pitcher_start_summary,
    velocity_deltas,
    usage_deltas,
    pitch_effectiveness_deltas,
    new_pitch_detections,
    opponent_adjusted_metrics,
    trend_scores,
    confidence_scores,
    stability_scores,
    primary_pitch_quality_gap,
):
    """Build one-row-per-signal pitcher flags table."""
    starts = _to_records(pitcher_start_summary)
    velos = _to_records(velocity_deltas)
    usages = _to_records(usage_deltas)
    effs = _to_records(pitch_effectiveness_deltas)
    new_pitch = _to_records(new_pitch_detections)
    opp_adj = _to_records(opponent_adjusted_metrics)
    trends = _to_records(trend_scores)
    confs = _to_records(confidence_scores)
    stabs = _to_records(stability_scores)
    primary = _to_records(primary_pitch_quality_gap)

    base_lookup = {row.get("appearance_id"): row for row in starts}
    for dataset in [opp_adj, trends, confs, stabs, primary]:
        for row in dataset:
            base_lookup.setdefault(row.get("appearance_id"), row)

    flags = []
    seen = set()
    created_at = datetime.now(timezone.utc).isoformat()

    def add_flag(appearance_id, signal_name, signal_category, direction, raw_value, baseline, delta, percentile, conf, severity, note, angle):
        base = base_lookup.get(appearance_id, {})
        key = (base.get("pitcher_id"), appearance_id, signal_name)
        if key in seen:
            return
        seen.add(key)

        flags.append(
            {
                "flag_id": f"{appearance_id}_{signal_name}".replace(" ", "_"),
                "pitcher_id": base.get("pitcher_id"),
                "pitcher_name": base.get("pitcher_name"),
                "appearance_id": appearance_id,
                "game_date": base.get("game_date"),
                "opponent_team_id": base.get("opponent_team_id"),
                "signal_category": signal_category,
                "signal_name": signal_name,
                "signal_direction": direction,
                "raw_value": raw_value,
                "baseline_value": baseline,
                "delta_value": delta,
                "percentile_score": percentile,
                "confidence_score": conf,
                "severity": severity,
                "sample_warning_flag": bool(base.get("sample_warning_flag", False)),
                "context_note": note,
                "auto_generated_angle": angle,
                "reviewed_flag": False,
                "dismissed_flag": False,
                "created_at": created_at,
            }
        )

    # velocity flags
    by_app_velo = {}
    for r in velos:
        by_app_velo.setdefault(r.get("appearance_id"), []).append(r)
    for app, rows in by_app_velo.items():
        if any(bool(r.get("strong_velo_spike_flag")) for r in rows):
            best = max((r.get("delta_velo_last_start") for r in rows if _is_valid(r.get("delta_velo_last_start"))), default=float("nan"))
            add_flag(app, "strong velocity spike", "velocity", "up", best, None, best, None, None, "high", "Fastball or arsenal velocity jumped materially.", "Velocity surge could signal a stuff jump.")
        if any(bool(r.get("strong_velo_drop_flag")) for r in rows):
            worst = min((r.get("delta_velo_last_start") for r in rows if _is_valid(r.get("delta_velo_last_start"))), default=float("nan"))
            add_flag(app, "strong velocity drop", "velocity", "down", worst, None, worst, None, None, "high", "Material velocity drop detected.", "Potential fatigue/injury risk angle.")

    # usage flags
    by_app_usage = {}
    for r in usages:
        by_app_usage.setdefault(r.get("appearance_id"), []).append(r)
    for app, rows in by_app_usage.items():
        if any(bool(r.get("major_usage_spike_flag")) for r in rows):
            best = max((r.get("delta_usage_last_start") for r in rows if _is_valid(r.get("delta_usage_last_start"))), default=float("nan"))
            add_flag(app, "major pitch usage spike", "usage", "up", best, None, best, None, None, "medium", "A pitch usage share jumped sharply.", "Pitch-mix shift may indicate a new plan.")
        if any(bool(r.get("major_usage_drop_flag")) for r in rows):
            worst = min((r.get("delta_usage_last_start") for r in rows if _is_valid(r.get("delta_usage_last_start"))), default=float("nan"))
            add_flag(app, "major pitch usage drop", "usage", "down", worst, None, worst, None, None, "medium", "A pitch usage share dropped sharply.", "Pitch-mix deprioritization to monitor.")

    # effectiveness flags
    by_app_eff = {}
    for r in effs:
        by_app_eff.setdefault(r.get("appearance_id"), []).append(r)
    for app, rows in by_app_eff.items():
        if any(bool(r.get("effectiveness_improved_flag")) for r in rows):
            add_flag(app, "pitch effectiveness improvement", "effectiveness", "up", 1, 0, 1, None, None, "medium", "Multiple pitch effectiveness metrics improved.", "Command/stuff combo trending up.")

    # new pitch detections
    for r in new_pitch:
        app = r.get("appearance_id_detected")
        dtype = r.get("detection_type")
        if dtype == "new_pitch":
            add_flag(app, "new pitch detected", "arsenal", "up", r.get("current_usage_rate"), r.get("previous_usage_rate"), r.get("delta_usage"), None, r.get("confidence_score"), "high", "A new pitch crossed adoption thresholds.", "New weapon may change matchup profile.")
        if dtype == "pitch_mix_spike":
            add_flag(app, "pitch mix spike", "usage", "up", r.get("current_usage_rate"), r.get("previous_usage_rate"), r.get("delta_usage"), None, r.get("confidence_score"), "medium", "Pitch mix spike detection triggered.", "Sudden tactical pitch-mix shift.")

    # opponent adjusted
    for r in opp_adj:
        if _is_valid(r.get("adjusted_whiff_rate_diff")) and r.get("adjusted_whiff_rate_diff") >= 0.08:
            add_flag(r.get("appearance_id"), "adjusted whiff surge", "opponent_adjusted", "up", r.get("raw_whiff_rate"), r.get("opponent_whiff_rate_baseline"), r.get("adjusted_whiff_rate_diff"), None, r.get("opponent_adjustment_confidence"), "medium", "Whiff performance exceeded opponent baseline by a notable margin.", "Whiff over-performance even after opponent adjustment.")

    # primary pitch quality
    for r in primary:
        app = r.get("appearance_id")
        gap = r.get("primary_pitch_damage_gap")
        if bool(r.get("primary_pitch_good_process_bad_results_flag")):
            add_flag(app, "bad results / good process", "process_results_gap", "mixed", r.get("primary_pitch_woba_allowed"), r.get("primary_pitch_xwoba_allowed"), gap, None, None, "medium", "Process looks strong but outcomes lagged.", "Potential buy-low if process persists.")
        if bool(r.get("primary_pitch_bad_process_good_results_flag")):
            add_flag(app, "good results / bad process", "process_results_gap", "mixed", r.get("primary_pitch_woba_allowed"), r.get("primary_pitch_xwoba_allowed"), gap, None, None, "medium", "Outcomes beat underlying process.", "Possible regression warning.")
        if _is_valid(gap) and abs(gap) >= 0.05:
            sev = "high" if abs(gap) >= 0.1 else "medium"
            add_flag(app, "primary pitch damage gap", "process_results_gap", "up" if gap > 0 else "down", gap, 0.0, gap, None, None, sev, "Primary pitch xwOBA/wOBA gap exceeded threshold.", "Primary pitch quality/result gap story.")

    # trend and confidence flags
    for r in trends:
        if _is_valid(r.get("pitcher_change_score_percentile")) and r.get("pitcher_change_score_percentile") >= 0.9:
            sev = "extreme" if r.get("pitcher_change_score_percentile") >= 0.97 else "high"
            add_flag(r.get("appearance_id"), "high pitcher change score", "composite", "up", r.get("pitcher_change_score_raw"), None, None, r.get("pitcher_change_score_percentile"), r.get("trend_confidence_score"), sev, "Composite trend score is in the top range.", "Broad multi-signal change detected.")

    for r in confs:
        if (_is_valid(r.get("overall_confidence_score")) and r.get("overall_confidence_score") < 0.5) or r.get("confidence_tier") == "low":
            add_flag(r.get("appearance_id"), "low confidence warning", "confidence", "down", r.get("overall_confidence_score"), 0.5, (r.get("overall_confidence_score") or 0) - 0.5, None, r.get("overall_confidence_score"), "low", "Signal confidence is limited by sample/context.", "Treat other flags as exploratory.")

    return _from_records(flags, pitcher_start_summary)

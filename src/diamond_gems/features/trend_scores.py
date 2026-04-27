"""Pitcher trend scoring from appearance-level and derived feature inputs."""

from __future__ import annotations

from copy import deepcopy

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None

# Placeholder weights for MVP. These are intentionally explicit and easy to adjust/learn later.
PITCHER_TREND_SCORE_WEIGHTS = {
    "velo": 0.15,
    "usage": 0.15,
    "whiff": 0.15,
    "csw": 0.10,
    "kbb": 0.10,
    "opponent_adjusted_whiff": 0.10,
    "pitch_effectiveness": 0.10,
    "pitch_mix_volatility": 0.05,
    "stability": 0.05,
    "confidence": 0.05,
}


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


def _mean(values: list[float]):
    vals = [float(v) for v in values if _is_valid(v)]
    if not vals:
        return float("nan")
    return sum(vals) / len(vals)


def _aggregate_mean_by_appearance(rows: list[dict], field: str) -> dict:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(row.get("appearance_id"), []).append(row.get(field))
    return {k: _mean(v) for k, v in grouped.items()}


def _compute_percentiles(values_by_id: dict[str, float]) -> dict[str, float]:
    valid_items = [(k, v) for k, v in values_by_id.items() if _is_valid(v)]
    if not valid_items:
        return {k: float("nan") for k in values_by_id}

    sorted_items = sorted(valid_items, key=lambda kv: kv[1])
    n = len(sorted_items)
    percentiles = {}
    for idx, (appearance_id, _) in enumerate(sorted_items):
        percentiles[appearance_id] = 1.0 if n == 1 else idx / (n - 1)
    for appearance_id in values_by_id:
        percentiles.setdefault(appearance_id, float("nan"))
    return percentiles


def build_pitcher_trend_scores(
    pitcher_start_summary,
    velocity_deltas,
    usage_deltas,
    pitch_effectiveness_deltas,
    opponent_adjusted_metrics,
    arsenal_concentration,
    pitch_mix_volatility,
    stability_scores,
    confidence_scores,
):
    """Build one-row-per-appearance pitcher trend scores with percentiles."""
    start_rows = _to_records(pitcher_start_summary)
    velo_rows = _to_records(velocity_deltas)
    usage_rows = _to_records(usage_deltas)
    eff_rows = _to_records(pitch_effectiveness_deltas)
    opp_rows = _to_records(opponent_adjusted_metrics)
    arsenal_rows = _to_records(arsenal_concentration)
    mix_rows = _to_records(pitch_mix_volatility)
    stability_rows = _to_records(stability_scores)
    confidence_rows = _to_records(confidence_scores)

    base_lookup = {row.get("appearance_id"): deepcopy(row) for row in start_rows}

    all_ids = set(base_lookup.keys())
    for dataset in [velo_rows, usage_rows, eff_rows, opp_rows, arsenal_rows, mix_rows, stability_rows, confidence_rows]:
        all_ids.update(row.get("appearance_id") for row in dataset)

    velo_raw = _aggregate_mean_by_appearance(velo_rows, "delta_velo_rolling_3_start")
    usage_raw = _aggregate_mean_by_appearance(usage_rows, "delta_usage_rolling_3_start")
    whiff_raw = _aggregate_mean_by_appearance(eff_rows, "delta_whiff_rate_rolling_3_start")
    csw_raw = _aggregate_mean_by_appearance(eff_rows, "delta_csw_rate_rolling_3_start")
    opp_whiff_raw = _aggregate_mean_by_appearance(opp_rows, "adjusted_whiff_rate_diff")
    pitch_effectiveness_raw = {
        k: -v if _is_valid(v) else float("nan")
        for k, v in _aggregate_mean_by_appearance(eff_rows, "delta_xwoba_allowed_rolling_3_start").items()
    }
    pitch_mix_raw = {
        k: -v if _is_valid(v) else float("nan")
        for k, v in _aggregate_mean_by_appearance(mix_rows, "pitch_mix_volatility_last_start").items()
    }
    arsenal_raw = _aggregate_mean_by_appearance(arsenal_rows, "arsenal_concentration_score")
    stability_raw = _aggregate_mean_by_appearance(stability_rows, "overall_stability_score")
    confidence_raw = _aggregate_mean_by_appearance(confidence_rows, "overall_confidence_score")

    kbb_raw = {row.get("appearance_id"): row.get("k_minus_bb_rate") for row in start_rows}
    contact_quality_raw = {
        row.get("appearance_id"): -row.get("xwoba_allowed") if _is_valid(row.get("xwoba_allowed")) else float("nan")
        for row in start_rows
    }

    # ensure keys exist for all ids
    def fill_ids(d: dict):
        for aid in all_ids:
            d.setdefault(aid, float("nan"))

    for d in [
        velo_raw,
        usage_raw,
        whiff_raw,
        csw_raw,
        kbb_raw,
        contact_quality_raw,
        opp_whiff_raw,
        pitch_effectiveness_raw,
        pitch_mix_raw,
        arsenal_raw,
        stability_raw,
        confidence_raw,
    ]:
        fill_ids(d)

    p_velo = _compute_percentiles(velo_raw)
    p_usage = _compute_percentiles(usage_raw)
    p_whiff = _compute_percentiles(whiff_raw)
    p_csw = _compute_percentiles(csw_raw)
    p_kbb = _compute_percentiles(kbb_raw)
    p_contact = _compute_percentiles(contact_quality_raw)
    p_opp_whiff = _compute_percentiles(opp_whiff_raw)
    p_pitch_eff = _compute_percentiles(pitch_effectiveness_raw)
    p_mix = _compute_percentiles(pitch_mix_raw)
    p_arsenal = _compute_percentiles(arsenal_raw)
    p_stability = _compute_percentiles(stability_raw)
    p_conf = _compute_percentiles(confidence_raw)

    output_rows = []
    for appearance_id in sorted(all_ids):
        base = base_lookup.get(appearance_id, {})

        weighted_components = [
            (PITCHER_TREND_SCORE_WEIGHTS["velo"], p_velo.get(appearance_id)),
            (PITCHER_TREND_SCORE_WEIGHTS["usage"], p_usage.get(appearance_id)),
            (PITCHER_TREND_SCORE_WEIGHTS["whiff"], p_whiff.get(appearance_id)),
            (PITCHER_TREND_SCORE_WEIGHTS["csw"], p_csw.get(appearance_id)),
            (PITCHER_TREND_SCORE_WEIGHTS["kbb"], p_kbb.get(appearance_id)),
            (PITCHER_TREND_SCORE_WEIGHTS["opponent_adjusted_whiff"], p_opp_whiff.get(appearance_id)),
            (PITCHER_TREND_SCORE_WEIGHTS["pitch_effectiveness"], p_pitch_eff.get(appearance_id)),
            (PITCHER_TREND_SCORE_WEIGHTS["pitch_mix_volatility"], p_mix.get(appearance_id)),
            (PITCHER_TREND_SCORE_WEIGHTS["stability"], p_stability.get(appearance_id)),
            (PITCHER_TREND_SCORE_WEIGHTS["confidence"], p_conf.get(appearance_id)),
        ]
        valid_weighted = [(w, v) for w, v in weighted_components if _is_valid(v)]
        if valid_weighted:
            total_w = sum(w for w, _ in valid_weighted)
            composite_raw = sum(w * v for w, v in valid_weighted) / total_w
        else:
            composite_raw = float("nan")

        trend_conf = _mean([p_conf.get(appearance_id), p_stability.get(appearance_id)])

        output_rows.append(
            {
                "appearance_id": appearance_id,
                "pitcher_id": base.get("pitcher_id"),
                "pitcher_name": base.get("pitcher_name"),
                "game_date": base.get("game_date"),
                "season": base.get("season"),
                "opponent_team_id": base.get("opponent_team_id"),
                "velo_trend_score_raw": velo_raw.get(appearance_id),
                "usage_trend_score_raw": usage_raw.get(appearance_id),
                "whiff_trend_score_raw": whiff_raw.get(appearance_id),
                "csw_trend_score_raw": csw_raw.get(appearance_id),
                "kbb_trend_score_raw": kbb_raw.get(appearance_id),
                "contact_quality_trend_score_raw": contact_quality_raw.get(appearance_id),
                "opponent_adjusted_whiff_score_raw": opp_whiff_raw.get(appearance_id),
                "pitch_effectiveness_score_raw": pitch_effectiveness_raw.get(appearance_id),
                "pitch_mix_volatility_score_raw": pitch_mix_raw.get(appearance_id),
                "arsenal_concentration_score_raw": arsenal_raw.get(appearance_id),
                "stability_score_raw": stability_raw.get(appearance_id),
                "confidence_score_raw": confidence_raw.get(appearance_id),
                "velo_trend_percentile": p_velo.get(appearance_id),
                "usage_trend_percentile": p_usage.get(appearance_id),
                "whiff_trend_percentile": p_whiff.get(appearance_id),
                "csw_trend_percentile": p_csw.get(appearance_id),
                "kbb_trend_percentile": p_kbb.get(appearance_id),
                "contact_quality_trend_percentile": p_contact.get(appearance_id),
                "opponent_adjusted_whiff_percentile": p_opp_whiff.get(appearance_id),
                "pitch_effectiveness_percentile": p_pitch_eff.get(appearance_id),
                "pitch_mix_volatility_percentile": p_mix.get(appearance_id),
                "arsenal_concentration_percentile": p_arsenal.get(appearance_id),
                "stability_percentile": p_stability.get(appearance_id),
                "confidence_percentile": p_conf.get(appearance_id),
                "pitcher_change_score_raw": composite_raw,
                "pitcher_change_score_percentile": float("nan"),
                "trend_confidence_score": trend_conf,
                "sample_warning_flag": bool(_is_valid(confidence_raw.get(appearance_id)) and confidence_raw.get(appearance_id) < 0.5),
            }
        )

    # percentile for composite
    composite_map = {row["appearance_id"]: row["pitcher_change_score_raw"] for row in output_rows}
    composite_pct = _compute_percentiles(composite_map)
    for row in output_rows:
        row["pitcher_change_score_percentile"] = composite_pct.get(row["appearance_id"])

    return _from_records(output_rows, pitcher_start_summary)

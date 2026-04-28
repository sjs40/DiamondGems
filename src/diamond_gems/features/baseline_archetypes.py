"""Baseline/recent comparisons, archetypes, and daily change summaries.

Data contract:
- Required columns for appearance-level comparisons:
  pitcher_name, game_date
- Optional columns used when present:
  team_id/pitcher_team_id, opponent_team_id, pitch_count/pitches_thrown, innings_pitched,
  avg_fastball_velo, avg_pitch_velo, whiff_rate, csw_rate, chase_rate, zone_rate,
  called_strike_rate, k_rate, bb_rate, k_minus_bb_rate, strike_rate, earned_runs,
  hard_hit_rate_allowed, barrel_rate_allowed, xwoba_allowed
- Optional pitch-type-level columns for usage/velocity shifts:
  pitch_type, usage_rate, avg_velocity
Fallback behavior: missing optional columns produce NaN/blank outputs; required columns raise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REQ_COLS = ["pitcher_name", "game_date"]


def _normalize_pct(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        return numeric
    if numeric.dropna().quantile(0.95) > 1.5:
        return numeric / 100.0
    return numeric


def calculate_pitcher_baselines(starts_df: pd.DataFrame) -> pd.DataFrame:
    for c in REQ_COLS:
        if c not in starts_df.columns:
            raise ValueError(f"Missing required column: {c}")
    df = starts_df.copy()
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    df = df.sort_values(["pitcher_name", "game_date"]).reset_index(drop=True)
    metrics = [c for c in ["avg_fastball_velo", "avg_pitch_velo", "whiff_rate", "csw_rate", "chase_rate", "zone_rate", "called_strike_rate", "k_rate", "bb_rate", "k_minus_bb_rate", "strike_rate", "pitches_thrown", "innings_pitched", "earned_runs", "hard_hit_rate_allowed", "barrel_rate_allowed", "xwoba_allowed"] if c in df.columns]
    for c in ["whiff_rate", "csw_rate", "chase_rate", "zone_rate", "called_strike_rate", "k_rate", "bb_rate", "k_minus_bb_rate", "strike_rate", "usage_rate"]:
        if c in df.columns:
            df[c] = _normalize_pct(df[c])

    g = df.groupby("pitcher_name", dropna=False)
    df["season_baseline_games"] = g.cumcount()
    for m in metrics:
        df[f"{m}_season_baseline"] = g[m].transform(lambda s: s.shift(1).expanding().mean())
    return df


def calculate_recent_windows(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    g = out.groupby("pitcher_name", dropna=False)
    out["last3_games"] = g.cumcount().clip(upper=3)
    out["last5_games"] = g.cumcount().clip(upper=5)
    metric_cols = [c for c in out.columns if c.endswith("_season_baseline")]
    for m in metric_cols:
        source = m.replace("_season_baseline", "")
        if source in out.columns:
            out[f"{source}_last3_baseline"] = g[source].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
            out[f"{source}_last5_baseline"] = g[source].transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    return out


def calculate_delta_metrics(df: pd.DataFrame, pitch_type_df: pd.DataFrame | None = None) -> pd.DataFrame:
    out = df.copy()
    pairs = {
        "velo": "avg_fastball_velo",
        "whiff": "whiff_rate",
        "csw": "csw_rate",
        "kbb": "k_minus_bb_rate",
    }
    for short, base_col in pairs.items():
        if base_col in out.columns:
            out[f"{short}_delta_vs_season"] = out[base_col] - out.get(f"{base_col}_season_baseline")
            out[f"{short}_delta_vs_last3"] = out[base_col] - out.get(f"{base_col}_last3_baseline")

    if pitch_type_df is not None and not pitch_type_df.empty and {"pitcher_name", "game_date", "pitch_type", "usage_rate"}.issubset(set(pitch_type_df.columns)):
        p = pitch_type_df.copy()
        p["game_date"] = pd.to_datetime(p["game_date"], errors="coerce")
        p["usage_rate"] = _normalize_pct(p["usage_rate"])
        p = p.sort_values(["pitcher_name", "pitch_type", "game_date"])
        p["usage_season_baseline"] = p.groupby(["pitcher_name", "pitch_type"], dropna=False)["usage_rate"].transform(lambda s: s.shift(1).expanding().mean())
        p["usage_last3_baseline"] = p.groupby(["pitcher_name", "pitch_type"], dropna=False)["usage_rate"].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
        p["usage_delta_vs_season"] = p["usage_rate"] - p["usage_season_baseline"]
        p["usage_delta_vs_last3"] = p["usage_rate"] - p["usage_last3_baseline"]
        usage_shift = p.sort_values("game_date").groupby(["pitcher_name", "game_date"], dropna=False)["usage_delta_vs_season"].apply(lambda s: s.abs().max()).rename("usage_delta_vs_season")
        usage_shift_l3 = p.sort_values("game_date").groupby(["pitcher_name", "game_date"], dropna=False)["usage_delta_vs_last3"].apply(lambda s: s.abs().max()).rename("usage_delta_vs_last3")
        out = out.merge(usage_shift.reset_index(), on=["pitcher_name", "game_date"], how="left")
        out = out.merge(usage_shift_l3.reset_index(), on=["pitcher_name", "game_date"], how="left")
    return out


def add_baseline_recent_features(starts_df: pd.DataFrame, pitch_type_df: pd.DataFrame | None = None) -> pd.DataFrame:
    base = calculate_pitcher_baselines(starts_df)
    recent = calculate_recent_windows(base)
    out = calculate_delta_metrics(recent, pitch_type_df)
    out["current_pitch_count"] = pd.to_numeric(out.get("pitches_thrown"), errors="coerce")
    out["baseline_pitch_count"] = out.get("pitches_thrown_season_baseline")
    conditions = [
        out["season_baseline_games"].fillna(0) <= 0,
        out["season_baseline_games"].fillna(0) < 3,
        out["last3_games"].fillna(0) < 3,
        out["last5_games"].fillna(0) < 5,
    ]
    values = ["INSUFFICIENT_DATA", "LIMITED_SEASON_SAMPLE", "LIMITED_LAST3_SAMPLE", "LIMITED_LAST5_SAMPLE"]
    out["baseline_sample_warning"] = np.select(conditions, values, default="OK")
    out["baseline_recent_summary"] = out.apply(_build_summary_text, axis=1)
    return out


def _build_summary_text(row: pd.Series) -> str:
    parts = []
    if pd.notna(row.get("velo_delta_vs_season")):
        parts.append(f"Fastball velocity is {row['velo_delta_vs_season']:+.1f} mph vs season baseline")
    if pd.notna(row.get("usage_delta_vs_last3")):
        parts.append(f"pitch usage shifted {row['usage_delta_vs_last3']*100:+.1f} pts vs last 3")
    if pd.notna(row.get("whiff_delta_vs_season")):
        parts.append(f"whiff rate is {row['whiff_delta_vs_season']*100:+.1f} pts vs season")
    return " and ".join(parts) + "." if parts else "No baseline deltas available."


def assign_pitcher_archetypes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    primary, secondary, reason, conf = [], [], [], []
    for _, r in out.iterrows():
        tags = []
        reasons = []
        v = r.get("velo_delta_vs_season")
        u = r.get("usage_delta_vs_season")
        w = r.get("whiff_delta_vs_season")
        c = r.get("csw_delta_vs_season")
        kbb = r.get("kbb_delta_vs_season")
        if pd.notna(v) and v >= 1.0:
            tags.append("VELOCITY_RISER"); reasons.append(f"Velocity +{v:.1f} mph")
        if pd.notna(v) and v <= -1.0:
            tags.append("VELOCITY_DROPPER"); reasons.append(f"Velocity {v:.1f} mph")
        if pd.notna(u) and abs(u) >= 0.08:
            tags.append("PITCH_MIX_CHANGER"); reasons.append(f"Usage change {u*100:+.1f} pts")
            if u > 0.12: tags.append("USAGE_SPIKE")
        if pd.notna(w) and w >= 0.05:
            tags.append("WHIFF_GAINER"); reasons.append(f"Whiff +{w*100:.1f} pts")
        if pd.notna(w) and pd.notna(c) and pd.notna(kbb) and w > 0 and c > 0 and kbb > 0:
            tags.append("BAT_MISSING_BREAKOUT")
        if pd.notna(v) and v < -1.0 and ((pd.notna(r.get("bb_rate")) and pd.notna(r.get("bb_rate_season_baseline")) and r.get("bb_rate") > r.get("bb_rate_season_baseline"))):
            tags.append("POSSIBLE_FATIGUE")
        if not tags:
            tags = ["NO_CLEAR_ARCHETYPE"]
            reasons = ["No meaningful baseline signal"]
        p = tags[0]
        warning = r.get("baseline_sample_warning", "OK")
        score = max(abs(x) for x in [v if pd.notna(v) else 0, u*10 if pd.notna(u) else 0, w*10 if pd.notna(w) else 0])
        cval = "HIGH" if score >= 1.5 and warning == "OK" else "MEDIUM" if score >= 1.0 else "LOW"
        if warning != "OK" and cval == "HIGH":
            cval = "MEDIUM"
        primary.append(p); secondary.append("; ".join(tags[1:])); reason.append("; ".join(reasons)); conf.append(cval)
    out["primary_archetype"] = primary
    out["secondary_archetypes"] = secondary
    out["archetype_reason"] = reason
    out["archetype_confidence"] = conf
    return out


def build_what_changed_today_summary(enriched_df: pd.DataFrame, content_ideas: pd.DataFrame | None = None) -> tuple[pd.DataFrame, str]:
    req = ["pitcher_name", "game_date"]
    for c in req:
        if c not in enriched_df.columns:
            raise ValueError(f"Missing required column: {c}")
    rows = []
    latest = pd.to_datetime(enriched_df["game_date"], errors="coerce").max()
    day_df = enriched_df[pd.to_datetime(enriched_df["game_date"], errors="coerce") == latest].copy()

    def add_section(section: str, metric_col: str, positive: bool = True, n: int = 10):
        if metric_col not in day_df.columns:
            return
        d = day_df.copy()
        d = d[d[metric_col].notna()]
        d = d.sort_values(metric_col, ascending=not positive)
        if not positive:
            d = d.head(n)
        else:
            d = d.head(n)
        for i, (_, r) in enumerate(d.iterrows(), start=1):
            rows.append({"summary_section": section, "rank": i, "pitcher": r.get("pitcher_name"), "team": r.get("team_id", r.get("pitcher_team_id", "")), "opponent": r.get("opponent_team_id", ""), "date": r.get("game_date"), "pitch_type": "", "metric": metric_col, "current_value": r.get(metric_col.replace("_delta_vs_season", ""), np.nan), "baseline_value": r.get(metric_col.replace("_delta_vs_season", "") + "_season_baseline", np.nan), "delta": r.get(metric_col), "confidence": r.get("archetype_confidence", ""), "archetype": r.get("primary_archetype", ""), "explanation": r.get("baseline_recent_summary", ""), "content_angle": ""})

    add_section("Biggest Velocity Risers", "velo_delta_vs_season", positive=True)
    add_section("Biggest Velocity Fallers", "velo_delta_vs_season", positive=False)
    add_section("Biggest Usage Changes", "usage_delta_vs_season", positive=True)
    add_section("Biggest Whiff/CSW Gainers", "whiff_delta_vs_season", positive=True)

    hp = day_df[day_df.get("archetype_confidence", "").isin(["HIGH", "MEDIUM"])] if "archetype_confidence" in day_df.columns else day_df.iloc[0:0]
    for i, (_, r) in enumerate(hp.head(10).iterrows(), start=1):
        rows.append({"summary_section": "New High-Priority Archetypes", "rank": i, "pitcher": r.get("pitcher_name"), "team": r.get("team_id", ""), "opponent": r.get("opponent_team_id", ""), "date": r.get("game_date"), "pitch_type": "", "metric": "archetype", "current_value": np.nan, "baseline_value": np.nan, "delta": np.nan, "confidence": r.get("archetype_confidence", ""), "archetype": r.get("primary_archetype", ""), "explanation": r.get("archetype_reason", ""), "content_angle": ""})

    summary_df = pd.DataFrame(rows)
    top = summary_df.iloc[0] if not summary_df.empty else None
    text = "No strong change signals available today."
    if top is not None:
        text = f"Today's strongest signal is {top['pitcher']} with {top['metric']} at {top['delta']:+.3f} vs season baseline."
    return summary_df, text

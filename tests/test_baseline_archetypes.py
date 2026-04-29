from __future__ import annotations

import pandas as pd

from diamond_gems.features.baseline_archetypes import (
    add_baseline_recent_features,
    assign_pitcher_archetypes,
    build_what_changed_today_summary,
)


def _starts() -> pd.DataFrame:
    return pd.DataFrame([
        {"pitcher_name": "A", "game_date": "2024-04-01", "avg_fastball_velo": 95.0, "whiff_rate": 0.2, "csw_rate": 0.25, "k_minus_bb_rate": 0.12, "pitches_thrown": 80},
        {"pitcher_name": "A", "game_date": "2024-04-08", "avg_fastball_velo": 95.3, "whiff_rate": 0.23, "csw_rate": 0.27, "k_minus_bb_rate": 0.14, "pitches_thrown": 85},
        {"pitcher_name": "A", "game_date": "2024-04-15", "avg_fastball_velo": 97.0, "whiff_rate": 0.31, "csw_rate": 0.34, "k_minus_bb_rate": 0.20, "pitches_thrown": 90},
        {"pitcher_name": "B", "game_date": "2024-04-15", "avg_fastball_velo": 92.0, "whiff_rate": 0.15, "csw_rate": 0.22, "k_minus_bb_rate": 0.08, "pitches_thrown": 70},
    ])


def _ptype() -> pd.DataFrame:
    return pd.DataFrame([
        {"pitcher_name": "A", "game_date": "2024-04-01", "pitch_type": "SL", "usage_rate": 0.25},
        {"pitcher_name": "A", "game_date": "2024-04-08", "pitch_type": "SL", "usage_rate": 0.27},
        {"pitcher_name": "A", "game_date": "2024-04-15", "pitch_type": "SL", "usage_rate": 0.40},
    ])


def test_baseline_excludes_current():
    out = add_baseline_recent_features(_starts(), _ptype())
    row = out[(out.pitcher_name == "A") & (out.game_date == "2024-04-15")].iloc[0]
    assert round(row["avg_fastball_velo_season_baseline"], 2) == 95.15


def test_archetype_velocity_riser_and_no_clear():
    enriched = add_baseline_recent_features(_starts(), _ptype())
    tagged = assign_pitcher_archetypes(enriched)
    a = tagged[(tagged.pitcher_name == "A") & (tagged.game_date == "2024-04-15")].iloc[0]
    assert a["primary_archetype"] in ["VELOCITY_RISER", "PITCH_MIX_CHANGER"]
    b = tagged[(tagged.pitcher_name == "B")].iloc[0]
    assert b["primary_archetype"] == "NO_CLEAR_ARCHETYPE"


def test_what_changed_ranking_and_missing_cols_safe():
    tagged = assign_pitcher_archetypes(add_baseline_recent_features(_starts(), _ptype()))
    summary, text = build_what_changed_today_summary(tagged)
    assert not summary.empty
    assert "strongest signal" in text.lower() or "no strong" in text.lower()


def test_baseline_grouped_by_season_and_excludes_current_game() -> None:
    starts = pd.DataFrame([
        {"pitcher_id": 10, "pitcher_name": "A", "season": 2024, "game_date": "2024-04-01", "avg_fastball_velo": 95.0},
        {"pitcher_id": 10, "pitcher_name": "A", "season": 2024, "game_date": "2024-04-10", "avg_fastball_velo": 96.0},
        {"pitcher_id": 10, "pitcher_name": "A", "season": 2025, "game_date": "2025-04-01", "avg_fastball_velo": 94.0},
    ])
    out = add_baseline_recent_features(starts)
    row_2025 = out[out["season"] == 2025].iloc[0]
    assert pd.isna(row_2025["avg_fastball_velo_season_baseline"])
    row_2024_2 = out[(out["season"] == 2024) & (out["game_date"] == "2024-04-10")].iloc[0]
    assert row_2024_2["avg_fastball_velo_season_baseline"] == 95.0

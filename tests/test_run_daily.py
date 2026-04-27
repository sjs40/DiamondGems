"""Tests for daily pipeline runner."""

from pathlib import Path

import pytest

from diamond_gems.run_daily import main


RAW_HEADER = [
    "game_pk","game_date","pitcher","batter","player_name","pitcher_throws","pitch_type","pitch_name",
    "release_speed","release_spin_rate","release_extension","pfx_x","pfx_z","plate_x","plate_z","zone",
    "description","events","launch_speed","launch_angle","estimated_woba_using_speedangle","woba_value",
    "inning","inning_topbot","balls","strikes","outs_when_up","home_team","away_team","post_home_score","post_away_score",
]


def _write_small_csv(path: Path) -> None:
    rows = [
        [1,"2024-04-01",100,200,"Pitcher A","R","FF","Fastball",95,2300,6.1,0.1,1.1,0.0,2.5,5,"called_strike","","","","","",1,"Top",0,0,0,"NYY","BOS",0,0],
        [1,"2024-04-01",100,200,"Pitcher A","R","SL","Slider",85,2500,6.0,-0.1,0.9,0.1,2.4,11,"swinging_strike","strikeout","","","","",1,"Top",0,1,0,"NYY","BOS",0,0],
        [1,"2024-04-01",100,201,"Pitcher A","R","FF","Fastball",96,2310,6.2,0.1,1.2,0.0,2.6,5,"hit_into_play","single",98,15,0.5,0.7,2,"Top",0,0,1,"NYY","BOS",0,1],
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(RAW_HEADER) + "\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")


def test_run_daily_creates_expected_outputs_and_handles_empty_content(tmp_path: Path) -> None:
    raw_csv = tmp_path / "raw.csv"
    out_dir = tmp_path / "out"
    _write_small_csv(raw_csv)

    rc = main(["--input-file", str(raw_csv), "--output-dir", str(out_dir)])
    assert rc == 0

    expected = [
        "pitch_events.parquet",
        "pitcher_appearances.csv", "pitcher_appearances.parquet",
        "pitcher_start_summary.csv", "pitcher_start_summary.parquet",
        "pitcher_pitch_type_summary.csv", "pitcher_pitch_type_summary.parquet",
        "pitcher_velocity_deltas.csv", "pitcher_velocity_deltas.parquet",
        "pitcher_usage_deltas.csv", "pitcher_usage_deltas.parquet",
        "pitcher_trend_scores.csv", "pitcher_trend_scores.parquet",
        "pitcher_flags.csv",
        "content_ideas.csv",
        "baseball_content_dashboard.xlsx",
    ]
    for name in expected:
        assert (out_dir / name).exists()


def test_run_daily_rejects_input_file_and_download_date_together(tmp_path: Path) -> None:
    raw_csv = tmp_path / "raw.csv"
    _write_small_csv(raw_csv)

    with pytest.raises(ValueError):
        main(["--input-file", str(raw_csv), "--download-date", "2024-04-01"])

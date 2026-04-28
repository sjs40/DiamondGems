"""Tests for Excel dashboard export."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from diamond_gems.outputs import excel_export


def test_export_excel_dashboard_creates_workbook_and_expected_sheets(tmp_path: Path) -> None:
    excel_export.DATA_OUTPUTS_DIR = tmp_path
    tables = {
        "pitcher_start_summary": pd.DataFrame([{"pitcher_name": "A", "game_date": "2024-04-01"}]),
        "pitcher_pitch_type_summary": pd.DataFrame([{"pitcher_name": "A", "pitch_type": "FF"}]),
        "pitcher_velocity_deltas": pd.DataFrame([{"pitcher_name": "A", "velocity_delta": 1.2}]),
        "pitcher_usage_deltas": pd.DataFrame([{"pitcher_name": "A", "usage_delta": 0.1}]),
        "pitcher_trend_scores": pd.DataFrame([{"pitcher_name": "A", "pitcher_change_score_percentile": 0.9}]),
        "pitcher_flags": pd.DataFrame([{"pitcher_name": "A", "signal_category": "velo"}]),
        "content_ideas": pd.DataFrame([{"pitcher_name": "A", "headline": "Idea"}]),
    }

    output_path = excel_export.export_excel_dashboard(tables)
    assert output_path.exists()

    workbook = pd.ExcelFile(output_path)
    assert workbook.sheet_names == [
        "Daily Pitcher Board",
        "What Changed Today",
        "Pitcher Detail Views",
        "Start Summary",
        "Pitch Type Summary",
        "Velocity Deltas",
        "Usage Deltas",
        "Trend Scores",
        "Flags",
        "Content Ideas",
    ]


def test_export_excel_dashboard_does_not_mutate_input_tables(tmp_path: Path) -> None:
    excel_export.DATA_OUTPUTS_DIR = tmp_path
    tables = {
        "pitcher_start_summary": pd.DataFrame([{"pitcher_name": "A", "game_date": "2024-04-01"}]),
        "pitcher_flags": pd.DataFrame([{"pitcher_name": "A", "severity": "high"}]),
    }
    snapshots = {name: deepcopy(df.to_dict("records")) for name, df in tables.items()}

    excel_export.export_excel_dashboard(tables)

    for name, original_records in snapshots.items():
        assert tables[name].to_dict("records") == original_records

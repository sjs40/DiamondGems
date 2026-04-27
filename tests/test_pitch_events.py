"""Tests for pitch event cleaning transform."""

from copy import deepcopy

import pytest

from diamond_gems.constants import REQUIRED_RAW_STATCAST_COLUMNS
from diamond_gems.transform.pitch_events import clean_pitch_events


class FakeDataFrame:
    """Minimal DataFrame-like object used for tests without pandas."""

    def __init__(self, records: list[dict]) -> None:
        self._records = [dict(row) for row in records]

    @property
    def columns(self) -> list[str]:
        keys = set()
        for row in self._records:
            keys.update(row.keys())
        return sorted(keys)

    def to_dict(self, orient: str):
        if orient != "records":
            raise ValueError("Only records orient is supported")
        return [dict(row) for row in self._records]

    @classmethod
    def from_records(cls, records: list[dict]):
        return cls(records)


def _build_base_row() -> dict:
    row = {
        "game_pk": 1,
        "game_date": "2024-04-01",
        "pitcher": 100,
        "batter": 200,
        "player_name": "Pitcher One",
        "pitcher_throws": "R",
        "pitch_type": "FF",
        "pitch_name": "4-Seam Fastball",
        "release_speed": 96.0,
        "release_spin_rate": 2300.0,
        "release_extension": 6.2,
        "pfx_x": 0.1,
        "pfx_z": 1.1,
        "plate_x": 0.0,
        "plate_z": 2.8,
        "zone": 5,
        "description": "called_strike",
        "events": None,
        "launch_speed": None,
        "launch_angle": None,
        "estimated_woba_using_speedangle": None,
        "woba_value": None,
        "inning": 1,
        "inning_topbot": "Top",
        "balls": 0,
        "strikes": 1,
        "outs_when_up": 0,
        "home_team": "NYY",
        "away_team": "BOS",
        "post_home_score": 0,
        "post_away_score": 0,
    }

    missing_required = sorted(set(REQUIRED_RAW_STATCAST_COLUMNS).difference(row.keys()))
    assert not missing_required, f"Missing required test fields: {missing_required}"
    return row


def test_clean_pitch_events_adds_pitch_id_and_flags() -> None:
    """Cleaned rows should include generated IDs and correct flags."""
    row1 = _build_base_row()

    row2 = _build_base_row()
    row2.update(
        {
            "description": "swinging_strike",
            "events": "strikeout",
            "zone": 6,
            "strikes": 2,
        }
    )

    row3 = _build_base_row()
    row3.update(
        {
            "description": "hit_into_play_score",
            "events": "home_run",
            "zone": 11,
            "launch_speed": 101.2,
            "launch_angle": 29.0,
            "strikes": 0,
        }
    )

    row4 = _build_base_row()
    row4.update(
        {
            "description": "ball",
            "events": "walk",
            "zone": 12,
            "balls": 4,
            "strikes": 0,
        }

    )

    cleaned = clean_pitch_events(FakeDataFrame([row1, row2, row3, row4]))
    cleaned_rows = cleaned.to_dict("records")

    assert all("pitch_id" in row and row["pitch_id"] for row in cleaned_rows)
    assert cleaned_rows[0]["called_strike_flag"] is True
    assert cleaned_rows[1]["swing_flag"] is True
    assert cleaned_rows[1]["whiff_flag"] is True
    assert cleaned_rows[1]["strikeout_flag"] is True
    assert cleaned_rows[2]["home_run_flag"] is True
    assert cleaned_rows[2]["hard_hit_flag"] is True
    assert cleaned_rows[2]["chase_flag"] is True
    assert cleaned_rows[3]["walk_flag"] is True
    assert cleaned_rows[3]["pa_terminal_flag"] is True


def test_clean_pitch_events_does_not_mutate_input() -> None:
    """Input rows should remain unchanged after cleaning."""
    original_rows = [_build_base_row()]
    original_copy = deepcopy(original_rows)

    _ = clean_pitch_events(FakeDataFrame(original_rows))

    assert original_rows == original_copy


def test_clean_pitch_events_missing_required_columns_raises() -> None:
    """Missing required source columns should raise ValueError."""
    bad_row = _build_base_row()
    bad_row.pop("pitch_type")

    with pytest.raises(ValueError, match="missing required columns"):
        clean_pitch_events(FakeDataFrame([bad_row]))

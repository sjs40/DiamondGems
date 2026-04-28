"""Tests for pitcher start summary transform."""

import math

from diamond_gems.transform.pitcher_start_summary import build_pitcher_start_summary


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


def test_pitcher_start_summary_rates_and_velocity_metrics() -> None:
    """Summary rates should use the required denominators and velo filters."""
    appearances = FakeDataFrame(
        [
            {
                "appearance_id": "A1",
                "pitcher_id": 10,
                "pitcher_name": "Pitcher A",
                "game_id": 1001,
                "game_date": "2024-04-01",
                "season": 2024,
                "opponent_team_id": "BOS",
                "role": "SP",
                "start_number_season": 1,
                "pitches_thrown": 4,
                "batters_faced": 3,
                "innings_pitched": 1.0,
            },
            {
                "appearance_id": "A2",
                "pitcher_id": 11,
                "pitcher_name": "Pitcher B",
                "game_id": 1002,
                "game_date": "2024-04-02",
                "season": 2024,
                "opponent_team_id": "NYY",
                "role": "SP",
                "start_number_season": 1,
                "pitches_thrown": 0,
                "batters_faced": 0,
                "innings_pitched": 0.0,
            },
        ]
    )

    pitch_events = FakeDataFrame(
        [
            {
                "appearance_id": "A1",
                "pitch_type": "FF",
                "release_speed": 95.0,
                "swing_flag": True,
                "whiff_flag": True,
                "called_strike_flag": False,
                "in_zone_flag": True,
                "chase_flag": False,
                "batted_ball_flag": False,
                "hard_hit_flag": False,
                "pa_terminal_flag": False,
                "strikeout_flag": False,
                "walk_flag": False,
                "events": None,
                "launch_speed": None,
                "launch_angle": None,
                "estimated_woba_using_speedangle": None,
                "woba_value": None,
            },
            {
                "appearance_id": "A1",
                "pitch_type": "CU",
                "release_speed": 94.0,
                "swing_flag": False,
                "whiff_flag": False,
                "called_strike_flag": True,
                "in_zone_flag": True,
                "chase_flag": False,
                "batted_ball_flag": False,
                "hard_hit_flag": False,
                "pa_terminal_flag": False,
                "strikeout_flag": False,
                "walk_flag": False,
                "events": None,
                "launch_speed": None,
                "launch_angle": None,
                "estimated_woba_using_speedangle": None,
                "woba_value": None,
            },
            {
                "appearance_id": "A1",
                "pitch_type": "SI",
                "release_speed": 97.0,
                "swing_flag": True,
                "whiff_flag": False,
                "called_strike_flag": False,
                "in_zone_flag": False,
                "chase_flag": True,
                "batted_ball_flag": True,
                "hard_hit_flag": True,
                "pa_terminal_flag": True,
                "strikeout_flag": True,
                "walk_flag": False,
                "events": "home_run",
                "launch_speed": 100.0,
                "launch_angle": 30.0,
                "estimated_woba_using_speedangle": 0.9,
                "woba_value": 2.0,
            },
            {
                "appearance_id": "A1",
                "pitch_type": "CH",
                "release_speed": 85.0,
                "swing_flag": False,
                "whiff_flag": False,
                "called_strike_flag": False,
                "in_zone_flag": False,
                "chase_flag": False,
                "batted_ball_flag": False,
                "hard_hit_flag": False,
                "pa_terminal_flag": True,
                "strikeout_flag": False,
                "walk_flag": True,
                "events": "walk",
                "launch_speed": None,
                "launch_angle": None,
                "estimated_woba_using_speedangle": None,
                "woba_value": None,
            },
        ]
    )

    summary = build_pitcher_start_summary(pitch_events, appearances).to_dict("records")
    row_a1 = next(row for row in summary if row["appearance_id"] == "A1")
    row_a2 = next(row for row in summary if row["appearance_id"] == "A2")

    assert row_a1["whiff_rate"] == 0.5
    assert row_a1["csw_rate"] == 0.5
    assert row_a1["k_rate"] == (1 / 3)
    assert row_a1["swing_rate"] == 0.5
    assert row_a1["hits_allowed"] == 1
    assert row_a1["walks"] == 1
    assert row_a1["strikeouts"] == 1

    # Fastball velocity uses only FF/SI/FC.
    assert row_a1["avg_fastball_velo"] == 96.0
    assert row_a1["max_fastball_velo"] == 97.0

    # Zero denominators should return NaN.
    assert math.isnan(row_a2["k_rate"])
    assert math.isnan(row_a2["whiff_rate"])
    assert math.isnan(row_a2["swing_rate"])

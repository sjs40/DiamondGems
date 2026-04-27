"""Tests for times-through-the-order split features."""

import math

from diamond_gems.features.times_through_order import (
    build_times_through_order_splits,
    build_tto_penalty_summary,
)


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


def _build_pitch_rows(total_batters: int) -> list[dict]:
    rows = []
    for batter in range(1, total_batters + 1):
        if batter <= 9:
            whiff = batter <= 3
            called = batter == 4
            xwoba = 0.30
            hard_hit = False
        elif batter <= 18:
            whiff = batter == 10
            called = batter == 11
            xwoba = 0.40
            hard_hit = False
        else:
            whiff = False
            called = False
            xwoba = 0.60
            hard_hit = True

        rows.append(
            {
                "game_id": 1,
                "pitcher_id": 99,
                "pitcher_name": "Pitcher",
                "game_date": "2024-04-01",
                "season": 2024,
                "pa_terminal_flag": True,
                "swing_flag": True,
                "whiff_flag": whiff,
                "called_strike_flag": called,
                "strikeout_flag": False,
                "walk_flag": False,
                "woba_value": xwoba,
                "estimated_woba_using_speedangle": xwoba,
                "batted_ball_flag": True,
                "hard_hit_flag": hard_hit,
            }
        )
    return rows


def test_tto_pa_assignment_rates_and_penalty() -> None:
    """PA assignment, split rates, and TTO penalties should be correct."""
    splits = build_times_through_order_splits(FakeDataFrame(_build_pitch_rows(19))).to_dict("records")
    by_tto = {row["time_through_order"]: row for row in splits}

    # PA order assignment
    assert by_tto[1]["batters_faced"] == 9
    assert by_tto[2]["batters_faced"] == 9
    assert by_tto[3]["batters_faced"] == 1

    # rate checks
    assert abs(by_tto[1]["whiff_rate"] - (3 / 9)) < 1e-9
    assert abs(by_tto[2]["whiff_rate"] - (1 / 9)) < 1e-9

    penalties = build_tto_penalty_summary(FakeDataFrame(splits)).to_dict("records")[0]
    assert abs(penalties["tto_penalty_whiff"] - ((0 / 1) - (3 / 9))) < 1e-9
    assert abs(penalties["tto_penalty_xwoba"] - (0.60 - 0.30)) < 1e-9


def test_tto_penalty_missing_tto3_returns_nan() -> None:
    """Missing TTO 3 should return NaN penalties."""
    splits = build_times_through_order_splits(FakeDataFrame(_build_pitch_rows(18))).to_dict("records")
    penalties = build_tto_penalty_summary(FakeDataFrame(splits)).to_dict("records")[0]

    assert math.isnan(penalties["tto_penalty_whiff"])
    assert math.isnan(penalties["tto_penalty_csw"])
    assert math.isnan(penalties["tto_penalty_xwoba"])

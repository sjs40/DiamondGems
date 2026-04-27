"""Tests for pitcher usage delta features."""

from copy import deepcopy

from diamond_gems.features.usage_deltas import build_pitcher_usage_deltas


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


def test_usage_deltas_baselines_and_flags() -> None:
    """Usage deltas should use prior starts only and set flags correctly."""
    rows = [
        {"appearance_id": "a1", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-01", "season": 2024, "usage_rate": 0.40, "pitch_count": 20, "low_sample_flag": False},
        {"appearance_id": "a2", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-10", "season": 2024, "usage_rate": 0.50, "pitch_count": 25, "low_sample_flag": False},
        {"appearance_id": "a3", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-20", "season": 2024, "usage_rate": 0.35, "pitch_count": 18, "low_sample_flag": False},
        {"appearance_id": "a4", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-05-01", "season": 2024, "usage_rate": 0.60, "pitch_count": 30, "low_sample_flag": False},
        {"appearance_id": "a5", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-06-15", "season": 2024, "usage_rate": 0.20, "pitch_count": 10, "low_sample_flag": False},
    ]

    input_df = FakeDataFrame(rows)
    original_rows = deepcopy(rows)

    output_rows = build_pitcher_usage_deltas(input_df).to_dict("records")
    by_id = {row["appearance_id"]: row for row in output_rows}

    # season-start baseline
    assert by_id["a1"]["first_start_usage_rate"] == 0.40
    assert by_id["a1"]["delta_usage_season_start"] == 0.0

    # last-start deltas and flags
    assert by_id["a4"]["previous_start_usage_rate"] == 0.35
    assert abs(by_id["a4"]["delta_usage_last_start"] - 0.25) < 1e-9
    assert by_id["a4"]["usage_spike_flag"] is True
    assert by_id["a4"]["major_usage_spike_flag"] is True

    assert abs(by_id["a5"]["delta_usage_last_start"] + 0.40) < 1e-9
    assert by_id["a5"]["usage_drop_flag"] is True
    assert by_id["a5"]["major_usage_drop_flag"] is True

    # 30d and rolling baselines exclude current start
    assert abs(by_id["a4"]["usage_30d_baseline"] - 0.4166666667) < 1e-6
    assert abs(by_id["a4"]["rolling_3_start_usage_baseline"] - 0.4166666667) < 1e-6

    # input should not mutate
    assert input_df.to_dict("records") == original_rows

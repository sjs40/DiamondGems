"""Tests for pitcher velocity delta features."""

from copy import deepcopy

from diamond_gems.features.velocity_deltas import build_pitcher_velocity_deltas


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


def test_velocity_deltas_baselines_and_flags() -> None:
    """Velocity deltas should use prior starts only and set flags correctly."""
    rows = [
        {"appearance_id": "a1", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-01", "season": 2024, "avg_velocity": 95.0, "pitch_count": 10, "low_sample_flag": False},
        {"appearance_id": "a2", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-10", "season": 2024, "avg_velocity": 96.0, "pitch_count": 11, "low_sample_flag": False},
        {"appearance_id": "a3", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-20", "season": 2024, "avg_velocity": 94.0, "pitch_count": 9, "low_sample_flag": False},
        {"appearance_id": "a4", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-05-01", "season": 2024, "avg_velocity": 97.0, "pitch_count": 12, "low_sample_flag": False},
        {"appearance_id": "a5", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-06-15", "season": 2024, "avg_velocity": 93.0, "pitch_count": 8, "low_sample_flag": False},
    ]

    input_df = FakeDataFrame(rows)
    original_rows = deepcopy(rows)

    output_rows = build_pitcher_velocity_deltas(input_df).to_dict("records")
    by_id = {row["appearance_id"]: row for row in output_rows}

    # first start baseline
    assert by_id["a1"]["first_start_avg_velocity"] == 95.0
    assert by_id["a1"]["delta_velo_season_start"] == 0.0

    # previous start and flags
    assert by_id["a4"]["previous_start_avg_velocity"] == 94.0
    assert by_id["a4"]["delta_velo_last_start"] == 3.0
    assert by_id["a4"]["velo_spike_flag"] is True
    assert by_id["a4"]["strong_velo_spike_flag"] is True

    assert by_id["a5"]["delta_velo_last_start"] == -4.0
    assert by_id["a5"]["velo_drop_flag"] is True
    assert by_id["a5"]["strong_velo_drop_flag"] is True

    # 30d and rolling baselines exclude current start
    assert by_id["a4"]["avg_velocity_30d_baseline"] == 95.0
    assert by_id["a4"]["rolling_3_start_avg_velocity_baseline"] == 95.0

    # 30d window should be empty for a5
    assert by_id["a5"]["starts_in_30d_baseline"] == 0

    # input should not mutate
    assert input_df.to_dict("records") == original_rows


def test_velocity_deltas_handles_missing_appearance_id_without_sort_crash() -> None:
    rows = [
        {"appearance_id": None, "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-01", "season": 2024, "avg_velocity": 95.0, "pitch_count": 10, "low_sample_flag": False},
        {"appearance_id": "a2", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-01", "season": 2024, "avg_velocity": 96.0, "pitch_count": 11, "low_sample_flag": False},
    ]
    output_rows = build_pitcher_velocity_deltas(FakeDataFrame(rows)).to_dict("records")
    assert len(output_rows) == 2

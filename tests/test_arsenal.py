"""Tests for arsenal concentration and pitch-mix volatility features."""

from diamond_gems.features.arsenal import build_arsenal_concentration, build_pitch_mix_volatility


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


def test_arsenal_concentration_top_pitches_and_score() -> None:
    """Top pitch calculations and concentration score should be correct."""
    pitch_type_rows = [
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "Pitcher A", "game_date": "2024-04-01", "season": 2024, "pitch_type": "FF", "usage_rate": 0.50},
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "Pitcher A", "game_date": "2024-04-01", "season": 2024, "pitch_type": "SL", "usage_rate": 0.30},
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "Pitcher A", "game_date": "2024-04-01", "season": 2024, "pitch_type": "CH", "usage_rate": 0.20},
    ]

    row = build_arsenal_concentration(FakeDataFrame(pitch_type_rows)).to_dict("records")[0]

    assert row["top_1_pitch_type"] == "FF"
    assert abs(row["top_1_pitch_usage"] - 0.50) < 1e-9
    assert row["top_2_pitch_types"] == ["FF", "SL"]
    assert abs(row["top_2_pitch_usage"] - 0.80) < 1e-9
    assert abs(row["arsenal_concentration_score"] - 0.80) < 1e-9


def test_pitch_mix_volatility_sum_and_major_flag() -> None:
    """Volatility should sum absolute deltas and set major flag threshold."""
    usage_delta_rows = [
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "Pitcher A", "game_date": "2024-04-01", "delta_usage_last_start": 0.10, "delta_usage_rolling_3_start": 0.06, "delta_usage_30d": 0.07},
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "Pitcher A", "game_date": "2024-04-01", "delta_usage_last_start": -0.12, "delta_usage_rolling_3_start": -0.04, "delta_usage_30d": -0.02},
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "Pitcher A", "game_date": "2024-04-01", "delta_usage_last_start": 0.08, "delta_usage_rolling_3_start": 0.01, "delta_usage_30d": -0.03},
    ]

    row = build_pitch_mix_volatility(FakeDataFrame(usage_delta_rows)).to_dict("records")[0]

    assert abs(row["pitch_mix_volatility_last_start"] - 0.30) < 1e-9
    assert abs(row["pitch_mix_volatility_rolling_3_start"] - 0.11) < 1e-9
    assert abs(row["pitch_mix_volatility_30d"] - 0.12) < 1e-9
    assert row["major_mix_change_flag"] is True

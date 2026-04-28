"""Tests for primary pitch quality versus results gap features."""

from diamond_gems.features.primary_pitch_quality import build_primary_pitch_quality_gap


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


def test_primary_pitch_selection_damage_gap_and_flags() -> None:
    """Primary pitch, damage gap, and process/result flags should be correct."""
    rows = [
        {
            "appearance_id": "a1",
            "pitcher_id": 1,
            "pitcher_name": "P1",
            "game_date": "2024-04-01",
            "season": 2024,
            "pitch_type": "FF",
            "pitch_name": "Fastball",
            "usage_rate": 0.60,
            "avg_velocity": 96.0,
            "whiff_rate": 0.30,
            "csw_rate": 0.35,
            "xwoba_allowed": 0.290,
            "woba_allowed": 0.360,
        },
        {
            "appearance_id": "a1",
            "pitcher_id": 1,
            "pitcher_name": "P1",
            "game_date": "2024-04-01",
            "season": 2024,
            "pitch_type": "SL",
            "pitch_name": "Slider",
            "usage_rate": 0.40,
            "avg_velocity": 86.0,
            "whiff_rate": 0.35,
            "csw_rate": 0.33,
            "xwoba_allowed": 0.280,
            "woba_allowed": 0.290,
        },
        {
            "appearance_id": "a2",
            "pitcher_id": 1,
            "pitcher_name": "P1",
            "game_date": "2024-04-08",
            "season": 2024,
            "pitch_type": "CH",
            "pitch_name": "Changeup",
            "usage_rate": 0.55,
            "avg_velocity": 88.0,
            "whiff_rate": 0.20,
            "csw_rate": 0.24,
            "xwoba_allowed": 0.390,
            "woba_allowed": 0.320,
        },
    ]

    output_rows = build_primary_pitch_quality_gap(FakeDataFrame(rows)).to_dict("records")
    by_id = {row["appearance_id"]: row for row in output_rows}

    assert by_id["a1"]["primary_pitch_type"] == "FF"
    assert abs(by_id["a1"]["primary_pitch_damage_gap"] - 0.07) < 1e-9
    assert by_id["a1"]["primary_pitch_good_process_bad_results_flag"] is True
    assert by_id["a1"]["primary_pitch_bad_process_good_results_flag"] is False

    assert by_id["a2"]["primary_pitch_type"] == "CH"
    assert abs(by_id["a2"]["primary_pitch_damage_gap"] + 0.07) < 1e-9
    assert by_id["a2"]["primary_pitch_good_process_bad_results_flag"] is False
    assert by_id["a2"]["primary_pitch_bad_process_good_results_flag"] is True

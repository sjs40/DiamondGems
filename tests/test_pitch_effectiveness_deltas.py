"""Tests for pitch effectiveness delta features."""

from diamond_gems.features.pitch_effectiveness_deltas import build_pitch_effectiveness_deltas


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


def test_pitch_effectiveness_deltas_baselines_and_flags() -> None:
    """Effectiveness deltas should respect directionality and baseline windows."""
    rows = [
        {"appearance_id": "a1", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-01", "season": 2024, "pitch_count": 20, "low_sample_flag": False, "whiff_rate": 0.20, "csw_rate": 0.25, "xwoba_allowed": 0.40, "woba_allowed": 0.35, "hard_hit_rate_allowed": 0.45},
        {"appearance_id": "a2", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-10", "season": 2024, "pitch_count": 21, "low_sample_flag": False, "whiff_rate": 0.22, "csw_rate": 0.27, "xwoba_allowed": 0.38, "woba_allowed": 0.34, "hard_hit_rate_allowed": 0.44},
        {"appearance_id": "a3", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-20", "season": 2024, "pitch_count": 22, "low_sample_flag": False, "whiff_rate": 0.24, "csw_rate": 0.26, "xwoba_allowed": 0.36, "woba_allowed": 0.33, "hard_hit_rate_allowed": 0.43},
        {"appearance_id": "a4", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-05-01", "season": 2024, "pitch_count": 23, "low_sample_flag": False, "whiff_rate": 0.30, "csw_rate": 0.32, "xwoba_allowed": 0.30, "woba_allowed": 0.28, "hard_hit_rate_allowed": 0.35},
        {"appearance_id": "a5", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-05-20", "season": 2024, "pitch_count": 5, "low_sample_flag": True, "whiff_rate": 0.16, "csw_rate": 0.18, "xwoba_allowed": 0.48, "woba_allowed": 0.42, "hard_hit_rate_allowed": 0.52},
    ]

    output_rows = build_pitch_effectiveness_deltas(FakeDataFrame(rows)).to_dict("records")
    by_id = {row["appearance_id"]: row for row in output_rows}

    # baseline exclusion check (a4 uses a1-a3 only)
    assert abs(by_id["a4"]["rolling_3_start_whiff_rate_baseline"] - 0.22) < 1e-9
    assert abs(by_id["a4"]["whiff_rate_30d_baseline"] - 0.22) < 1e-9

    # higher-is-better metric deltas
    assert abs(by_id["a4"]["delta_whiff_rate_rolling_3_start"] - 0.08) < 1e-9
    assert abs(by_id["a4"]["delta_csw_rate_rolling_3_start"] - 0.06) < 1e-9

    # lower-is-better metric deltas should be negative when improved
    assert abs(by_id["a4"]["delta_xwoba_allowed_rolling_3_start"] + 0.08) < 1e-9
    assert abs(by_id["a4"]["delta_woba_allowed_rolling_3_start"] + 0.06) < 1e-9

    # improved/declined flags
    assert by_id["a4"]["effectiveness_improved_flag"] is True
    assert by_id["a4"]["effectiveness_declined_flag"] is False
    assert by_id["a5"]["effectiveness_improved_flag"] is False
    assert by_id["a5"]["effectiveness_declined_flag"] is True

    # low sample passthrough behavior
    assert by_id["a5"]["low_sample_flag"] is True


def test_pitch_effectiveness_deltas_handles_missing_appearance_id_without_sort_crash() -> None:
    rows = [
        {"appearance_id": None, "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-01", "season": 2024, "pitch_count": 20, "whiff_rate": 0.2, "csw_rate": 0.2, "xwoba_allowed": 0.3, "woba_allowed": 0.3, "hard_hit_rate_allowed": 0.3},
        {"appearance_id": "a2", "pitcher_id": 1, "pitch_type": "FF", "game_date": "2024-04-01", "season": 2024, "pitch_count": 21, "whiff_rate": 0.22, "csw_rate": 0.22, "xwoba_allowed": 0.29, "woba_allowed": 0.29, "hard_hit_rate_allowed": 0.29},
    ]
    output_rows = build_pitch_effectiveness_deltas(FakeDataFrame(rows)).to_dict("records")
    assert len(output_rows) == 2

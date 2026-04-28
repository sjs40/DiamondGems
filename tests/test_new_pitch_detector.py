"""Tests for new pitch and pitch-mix detection features."""

from diamond_gems.features.new_pitch_detector import build_new_pitch_detector


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


def test_new_pitch_and_spike_detection_confirmed_and_confidence_bounds() -> None:
    """Detector should trigger expected events and bound confidence to [0, 1]."""
    usage_rows = [
        # new pitch candidate (KN)
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "P1", "pitch_type": "KN", "game_date": "2024-04-01", "current_usage_rate": 0.00, "previous_start_usage_rate": 0.00, "delta_usage_last_start": 0.00, "pitch_count_current": 0, "pitch_count_previous_start": 0, "first_start_usage_rate": 0.00},
        {"appearance_id": "a2", "pitcher_id": 1, "pitcher_name": "P1", "pitch_type": "KN", "game_date": "2024-04-08", "current_usage_rate": 0.18, "previous_start_usage_rate": 0.00, "delta_usage_last_start": 0.18, "pitch_count_current": 9, "pitch_count_previous_start": 0, "first_start_usage_rate": 0.00},
        # pitch mix spike (SL) with confirmation on second spike
        {"appearance_id": "b1", "pitcher_id": 1, "pitcher_name": "P1", "pitch_type": "SL", "game_date": "2024-04-01", "current_usage_rate": 0.10, "previous_start_usage_rate": 0.10, "delta_usage_last_start": 0.00, "pitch_count_current": 8, "pitch_count_previous_start": 8, "first_start_usage_rate": 0.10},
        {"appearance_id": "b2", "pitcher_id": 1, "pitcher_name": "P1", "pitch_type": "SL", "game_date": "2024-04-08", "current_usage_rate": 0.28, "previous_start_usage_rate": 0.10, "delta_usage_last_start": 0.18, "pitch_count_current": 14, "pitch_count_previous_start": 8, "first_start_usage_rate": 0.10},
        {"appearance_id": "b3", "pitcher_id": 1, "pitcher_name": "P1", "pitch_type": "SL", "game_date": "2024-04-15", "current_usage_rate": 0.46, "previous_start_usage_rate": 0.28, "delta_usage_last_start": 0.18, "pitch_count_current": 20, "pitch_count_previous_start": 14, "first_start_usage_rate": 0.10},
    ]

    summary_rows = [
        {"appearance_id": "a2", "pitcher_id": 1, "pitcher_name": "P1", "pitch_type": "KN", "pitch_name": "Knuckleball", "whiff_rate": 0.33, "csw_rate": 0.40, "xwoba_allowed": 0.31},
        {"appearance_id": "b2", "pitcher_id": 1, "pitcher_name": "P1", "pitch_type": "SL", "pitch_name": "Slider", "whiff_rate": 0.35, "csw_rate": 0.38, "xwoba_allowed": 0.29},
        {"appearance_id": "b3", "pitcher_id": 1, "pitcher_name": "P1", "pitch_type": "SL", "pitch_name": "Slider", "whiff_rate": 0.37, "csw_rate": 0.41, "xwoba_allowed": 0.27},
    ]

    detections = build_new_pitch_detector(FakeDataFrame(usage_rows), FakeDataFrame(summary_rows)).to_dict("records")

    new_pitch = next(row for row in detections if row["detection_type"] == "new_pitch")
    spike_b2 = next(row for row in detections if row["appearance_id_detected"] == "b2" and row["detection_type"] == "pitch_mix_spike")
    spike_b3 = next(row for row in detections if row["appearance_id_detected"] == "b3" and row["detection_type"] == "pitch_mix_spike")

    assert new_pitch["appearance_id_detected"] == "a2"
    assert spike_b2["detection_type"] == "pitch_mix_spike"
    assert spike_b3["confirmed_flag"] is True

    for row in detections:
        assert 0.0 <= row["confidence_score"] <= 1.0

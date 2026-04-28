"""Tests for pitcher flag generation output."""

from diamond_gems.outputs.flags import build_pitcher_flags


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


def test_build_pitcher_flags_creates_expected_flags_no_duplicates_and_columns() -> None:
    """Flag generation should create key signals without duplicates."""
    starts = [{"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01", "opponent_team_id": "BOS"}]
    velos = [
        {"appearance_id": "a1", "strong_velo_spike_flag": True, "strong_velo_drop_flag": False, "delta_velo_last_start": 2.0},
        {"appearance_id": "a1", "strong_velo_spike_flag": True, "strong_velo_drop_flag": False, "delta_velo_last_start": 1.8},
    ]
    usages = [{"appearance_id": "a1", "major_usage_spike_flag": True, "major_usage_drop_flag": False, "delta_usage_last_start": 0.2}]
    eff = [{"appearance_id": "a1", "effectiveness_improved_flag": True}]
    new_pitch = [{"appearance_id_detected": "a1", "detection_type": "new_pitch", "current_usage_rate": 0.2, "previous_usage_rate": 0.0, "delta_usage": 0.2, "confidence_score": 0.8}]
    opp = [{"appearance_id": "a1", "adjusted_whiff_rate_diff": 0.09, "raw_whiff_rate": 0.4, "opponent_whiff_rate_baseline": 0.3, "opponent_adjustment_confidence": 0.7}]
    trends = [{"appearance_id": "a1", "pitcher_change_score_raw": 0.9, "pitcher_change_score_percentile": 0.95, "trend_confidence_score": 0.8}]
    conf = [{"appearance_id": "a1", "overall_confidence_score": 0.8, "confidence_tier": "high"}]
    stab = [{"appearance_id": "a1"}]
    primary = [{"appearance_id": "a1", "primary_pitch_damage_gap": 0.08, "primary_pitch_good_process_bad_results_flag": True, "primary_pitch_bad_process_good_results_flag": False, "primary_pitch_woba_allowed": 0.36, "primary_pitch_xwoba_allowed": 0.28}]

    flags = build_pitcher_flags(
        FakeDataFrame(starts), FakeDataFrame(velos), FakeDataFrame(usages), FakeDataFrame(eff),
        FakeDataFrame(new_pitch), FakeDataFrame(opp), FakeDataFrame(trends), FakeDataFrame(conf),
        FakeDataFrame(stab), FakeDataFrame(primary)
    ).to_dict("records")

    names = {f["signal_name"] for f in flags}
    assert "strong velocity spike" in names
    assert "major pitch usage spike" in names
    assert "new pitch detected" in names
    assert "high pitcher change score" in names

    # no duplicate signal names for same appearance/pitcher
    name_counts = {}
    for f in flags:
        key = (f["pitcher_id"], f["appearance_id"], f["signal_name"])
        name_counts[key] = name_counts.get(key, 0) + 1
    assert all(count == 1 for count in name_counts.values())

    required_cols = {
        "flag_id", "pitcher_id", "pitcher_name", "appearance_id", "game_date", "opponent_team_id",
        "signal_category", "signal_name", "signal_direction", "raw_value", "baseline_value", "delta_value",
        "percentile_score", "confidence_score", "severity", "sample_warning_flag", "context_note",
        "auto_generated_angle", "reviewed_flag", "dismissed_flag", "created_at",
    }
    assert required_cols.issubset(set(flags[0].keys()))

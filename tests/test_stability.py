"""Tests for stability and consistency scoring."""

from copy import deepcopy

from diamond_gems.features.stability import build_stability_scores


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


def test_stability_consecutive_counts_scores_and_non_mutation() -> None:
    """Consecutive counts and scores should be computed correctly."""
    velocity_rows = [
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01", "strong_velo_spike_flag": True},
        {"appearance_id": "a2", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-08", "strong_velo_spike_flag": True},
        {"appearance_id": "a3", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-15", "strong_velo_spike_flag": False},
    ]
    usage_rows = [
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01", "major_usage_spike_flag": False, "major_usage_drop_flag": False},
        {"appearance_id": "a2", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-08", "major_usage_spike_flag": True, "major_usage_drop_flag": False},
        {"appearance_id": "a3", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-15", "major_usage_spike_flag": False, "major_usage_drop_flag": True},
    ]
    eff_rows = [
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01", "effectiveness_improved_flag": True},
        {"appearance_id": "a2", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-08", "effectiveness_improved_flag": True},
        {"appearance_id": "a3", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-15", "effectiveness_improved_flag": True},
    ]

    v_original = deepcopy(velocity_rows)
    u_original = deepcopy(usage_rows)
    e_original = deepcopy(eff_rows)

    output_rows = build_stability_scores(
        FakeDataFrame(velocity_rows), FakeDataFrame(usage_rows), FakeDataFrame(eff_rows)
    ).to_dict("records")
    by_id = {row["appearance_id"]: row for row in output_rows}

    assert by_id["a2"]["consecutive_velo_spike_starts"] == 2
    assert by_id["a3"]["consecutive_velo_spike_starts"] == 0
    assert by_id["a3"]["consecutive_major_usage_change_starts"] == 2
    assert by_id["a3"]["consecutive_effectiveness_improvement_starts"] == 3

    for row in output_rows:
        assert 0.0 <= row["velo_stability_score"] <= 1.0
        assert 0.0 <= row["usage_stability_score"] <= 1.0
        assert 0.0 <= row["effectiveness_stability_score"] <= 1.0
        assert 0.0 <= row["overall_stability_score"] <= 1.0

    assert velocity_rows == v_original
    assert usage_rows == u_original
    assert eff_rows == e_original


def test_stability_missing_components_does_not_crash() -> None:
    """Missing component tables should still produce output rows."""
    velocity_rows = [
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01", "strong_velo_spike_flag": True}
    ]

    output_rows = build_stability_scores(
        FakeDataFrame(velocity_rows), FakeDataFrame([]), FakeDataFrame([])
    ).to_dict("records")

    assert len(output_rows) == 1
    assert output_rows[0]["appearance_id"] == "a1"
    assert output_rows[0]["overall_stability_score"] == output_rows[0]["velo_stability_score"]


def test_stability_handles_missing_appearance_id_in_sort() -> None:
    velocity_rows = [
        {"appearance_id": None, "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01", "strong_velo_spike_flag": True},
        {"appearance_id": "a2", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01", "strong_velo_spike_flag": False},
    ]

    output_rows = build_stability_scores(
        FakeDataFrame(velocity_rows), FakeDataFrame([]), FakeDataFrame([])
    ).to_dict("records")
    assert len(output_rows) == 2

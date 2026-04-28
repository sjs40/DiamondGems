"""Tests for appearance-level confidence scoring."""

from copy import deepcopy

from diamond_gems.features.confidence import build_confidence_scores


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


def test_confidence_scores_bounds_tiers_and_no_mutation() -> None:
    """Confidence scores should be bounded, tiered, and non-mutating."""
    appearances = [
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01"},
        {"appearance_id": "a2", "pitcher_id": 2, "pitcher_name": "P2", "game_date": "2024-04-01"},
    ]
    starts = [
        {"appearance_id": "a1", "pitches_thrown": 95, "batters_faced": 26},
        {"appearance_id": "a2", "pitches_thrown": 20, "batters_faced": 8},
    ]
    pitch_types = [
        {"appearance_id": "a1", "pitch_count": 20},
        {"appearance_id": "a1", "pitch_count": 12},
        {"appearance_id": "a2", "pitch_count": 4},
        {"appearance_id": "a2", "pitch_count": 3},
    ]
    opp = [
        {"appearance_id": "a1", "opponent_qualified_pa": 180},
        {"appearance_id": "a2", "opponent_qualified_pa": 30},
    ]

    a_orig = deepcopy(appearances)
    s_orig = deepcopy(starts)
    p_orig = deepcopy(pitch_types)

    out_rows = build_confidence_scores(
        FakeDataFrame(appearances),
        FakeDataFrame(starts),
        FakeDataFrame(pitch_types),
        FakeDataFrame(opp),
    ).to_dict("records")

    by_id = {r["appearance_id"]: r for r in out_rows}

    assert by_id["a1"]["confidence_tier"] == "high"
    assert by_id["a2"]["confidence_tier"] == "low"

    for row in out_rows:
        for field in ["pitch_volume_score", "batter_volume_score", "pitch_type_sample_score", "opponent_context_score", "overall_confidence_score"]:
            assert 0.0 <= row[field] <= 1.0

    assert appearances == a_orig
    assert starts == s_orig
    assert pitch_types == p_orig


def test_confidence_missing_opponent_metrics_does_not_crash() -> None:
    """Missing opponent table should still compute other confidence components."""
    out = build_confidence_scores(
        FakeDataFrame([{"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "P", "game_date": "2024-04-01"}]),
        FakeDataFrame([{"appearance_id": "a1", "pitches_thrown": 60, "batters_faced": 20}]),
        FakeDataFrame([{"appearance_id": "a1", "pitch_count": 10}]),
        None,
    ).to_dict("records")[0]

    assert out["overall_confidence_score"] == out["overall_confidence_score"]

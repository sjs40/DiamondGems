"""Tests for pitcher trend scoring feature."""

from copy import deepcopy

from diamond_gems.features.trend_scores import (
    PITCHER_TREND_SCORE_WEIGHTS,
    build_pitcher_trend_scores,
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


def test_trend_scores_output_percentiles_composite_weights_and_non_mutation() -> None:
    """Trend scoring should emit one row per appearance and bounded percentiles."""
    start = [
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01", "season": 2024, "opponent_team_id": "A", "k_minus_bb_rate": 0.20, "xwoba_allowed": 0.30},
        {"appearance_id": "a2", "pitcher_id": 2, "pitcher_name": "P2", "game_date": "2024-04-01", "season": 2024, "opponent_team_id": "B", "k_minus_bb_rate": 0.10, "xwoba_allowed": 0.40},
    ]
    velo = [
        {"appearance_id": "a1", "delta_velo_rolling_3_start": 1.0},
        {"appearance_id": "a2", "delta_velo_rolling_3_start": -0.5},
    ]
    usage = [
        {"appearance_id": "a1", "delta_usage_rolling_3_start": 0.10},
        {"appearance_id": "a2", "delta_usage_rolling_3_start": -0.10},
    ]
    eff = [
        {"appearance_id": "a1", "delta_whiff_rate_rolling_3_start": 0.05, "delta_csw_rate_rolling_3_start": 0.04, "delta_xwoba_allowed_rolling_3_start": -0.03},
        {"appearance_id": "a2", "delta_whiff_rate_rolling_3_start": -0.02, "delta_csw_rate_rolling_3_start": -0.01, "delta_xwoba_allowed_rolling_3_start": 0.02},
    ]
    opp = [
        {"appearance_id": "a1", "adjusted_whiff_rate_diff": 0.08},
        {"appearance_id": "a2", "adjusted_whiff_rate_diff": -0.02},
    ]
    arsenal = [{"appearance_id": "a1", "arsenal_concentration_score": 0.8}, {"appearance_id": "a2", "arsenal_concentration_score": 0.6}]
    mix = [{"appearance_id": "a1", "pitch_mix_volatility_last_start": 0.1}, {"appearance_id": "a2", "pitch_mix_volatility_last_start": 0.3}]
    stability = [{"appearance_id": "a1", "overall_stability_score": 0.7}, {"appearance_id": "a2", "overall_stability_score": 0.4}]
    confidence = [{"appearance_id": "a1", "overall_confidence_score": 0.8}, {"appearance_id": "a2", "overall_confidence_score": 0.3}]

    start_orig = deepcopy(start)
    out_rows = build_pitcher_trend_scores(
        FakeDataFrame(start), FakeDataFrame(velo), FakeDataFrame(usage), FakeDataFrame(eff),
        FakeDataFrame(opp), FakeDataFrame(arsenal), FakeDataFrame(mix), FakeDataFrame(stability), FakeDataFrame(confidence)
    ).to_dict("records")

    assert len(out_rows) == 2
    for row in out_rows:
        for col in [
            "velo_trend_percentile", "usage_trend_percentile", "whiff_trend_percentile", "csw_trend_percentile",
            "kbb_trend_percentile", "contact_quality_trend_percentile", "opponent_adjusted_whiff_percentile",
            "pitch_effectiveness_percentile", "pitch_mix_volatility_percentile", "arsenal_concentration_percentile",
            "stability_percentile", "confidence_percentile", "pitcher_change_score_percentile",
        ]:
            assert 0.0 <= row[col] <= 1.0
        assert row["pitcher_change_score_raw"] == row["pitcher_change_score_raw"]

    assert abs(sum(PITCHER_TREND_SCORE_WEIGHTS.values()) - 1.0) < 1e-9
    assert start == start_orig

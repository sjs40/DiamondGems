"""Tests for opponent context and opponent-adjusted metrics."""

from diamond_gems.features.opponent_context import (
    build_opponent_team_context,
    build_pitcher_opponent_adjusted_metrics,
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


def test_context_excludes_same_date_and_adjusted_fallback_and_handedness() -> None:
    """Context windows should exclude same-date rows and match handedness/fallback."""
    pitch_rows = [
        # prior date context
        {"game_date": "2024-04-01", "pitcher_throws": "R", "inning_topbot": "Top", "home_team": "AAA", "away_team": "BBB", "swing_flag": True, "whiff_flag": True, "chase_flag": False, "in_zone_flag": True, "pa_terminal_flag": True, "strikeout_flag": True, "walk_flag": False, "called_strike_flag": False, "batted_ball_flag": False, "hard_hit_flag": False, "woba_value": 0.2, "estimated_woba_using_speedangle": 0.2},
        # same date should be excluded for as_of_date 2024-04-02
        {"game_date": "2024-04-02", "pitcher_throws": "R", "inning_topbot": "Top", "home_team": "AAA", "away_team": "BBB", "swing_flag": True, "whiff_flag": False, "chase_flag": False, "in_zone_flag": True, "pa_terminal_flag": True, "strikeout_flag": False, "walk_flag": True, "called_strike_flag": True, "batted_ball_flag": True, "hard_hit_flag": True, "woba_value": 0.6, "estimated_woba_using_speedangle": 0.6},
    ]

    context_rows = build_opponent_team_context(FakeDataFrame(pitch_rows)).to_dict("records")
    target = next(
        r
        for r in context_rows
        if r["team_id"] == "BBB" and r["as_of_date"] == "2024-04-02" and r["window"] == "season_to_date" and r["handedness_split"] == "vs_RHP"
    )
    assert target["qualified_pa"] == 1  # excludes same-date row

    pitcher_start = FakeDataFrame(
        [
            {
                "appearance_id": "app1",
                "whiff_rate": 0.40,
                "csw_rate": 0.35,
                "k_rate": 0.30,
                "chase_rate": 0.25,
                "contact_rate": 0.60,
                "hard_hit_rate_allowed": 0.30,
                "xwoba_allowed": 0.28,
            }
        ]
    )
    appearances = FakeDataFrame(
        [
            {
                "appearance_id": "app1",
                "pitcher_id": 9,
                "pitcher_name": "P",
                "game_date": "2024-04-10",
                "opponent_team_id": "BBB",
                "opponent_team_abbr": "BBB",
                "pitcher_throws": "R",
            }
        ]
    )

    # craft context with low-sample last_30 and usable season_to_date for handedness check
    context_for_adjust = FakeDataFrame(
        [
            {"team_id": "BBB", "as_of_date": "2024-04-10", "window": "last_30", "handedness_split": "vs_RHP", "qualified_pa": 5, "whiff_rate": 0.20, "k_rate": 0.18, "chase_rate": 0.20, "contact_rate": 0.80, "woba": 0.34, "xwoba": 0.33, "opponent_quality_score": 0.1, "low_sample_flag": True},
            {"team_id": "BBB", "as_of_date": "2024-04-10", "window": "season_to_date", "handedness_split": "vs_RHP", "qualified_pa": 120, "whiff_rate": 0.22, "k_rate": 0.20, "chase_rate": 0.21, "contact_rate": 0.78, "woba": 0.32, "xwoba": 0.31, "opponent_quality_score": 0.2, "low_sample_flag": False},
        ]
    )

    adjusted = build_pitcher_opponent_adjusted_metrics(pitcher_start, context_for_adjust, appearances).to_dict("records")[0]

    assert adjusted["opponent_context_window"] == "season_to_date"  # fallback due to low sample
    assert abs(adjusted["adjusted_whiff_rate_diff"] - (0.40 - 0.22)) < 1e-9
    assert abs(adjusted["adjusted_whiff_rate_index"] - (0.40 / 0.22)) < 1e-9

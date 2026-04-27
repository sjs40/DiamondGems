"""Tests for park context and game-state context placeholders."""

from diamond_gems.features.context import add_basic_park_context, build_game_state_context


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


def test_add_basic_park_context_columns_added() -> None:
    """Park context placeholder columns should be present."""
    rows = [{"appearance_id": "a1", "pitcher_id": 1}]
    out = add_basic_park_context(FakeDataFrame(rows)).to_dict("records")[0]

    assert "park_factor_runs" in out
    assert "park_factor_hr" in out
    assert "park_factor_hits" in out
    assert out["park_context_note"] == "park factor unavailable in MVP"


def test_game_state_context_one_row_per_appearance_and_leverage() -> None:
    """Game-state context should aggregate by appearance and compute leverage proxies."""
    rows = [
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "P", "game_date": "2024-04-01", "season": 2024, "inning": 7, "post_home_score": 3, "post_away_score": 2, "on_1b": None, "on_2b": None, "on_3b": None},
        {"appearance_id": "a1", "pitcher_id": 1, "pitcher_name": "P", "game_date": "2024-04-01", "season": 2024, "inning": 8, "post_home_score": 10, "post_away_score": 2, "on_1b": 123, "on_2b": None, "on_3b": None},
        {"appearance_id": "a2", "pitcher_id": 2, "pitcher_name": "Q", "game_date": "2024-04-01", "season": 2024, "inning": 6, "post_home_score": 1, "post_away_score": 1, "on_1b": None, "on_2b": None, "on_3b": None},
    ]

    out_rows = build_game_state_context(FakeDataFrame(rows)).to_dict("records")
    assert len(out_rows) == 2

    a1 = next(r for r in out_rows if r["appearance_id"] == "a1")
    assert a1["high_leverage_proxy_pitches"] == 1  # inning>=7 and margin<=2
    assert a1["low_leverage_proxy_pitches"] == 1   # margin>=6

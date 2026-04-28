"""Tests for sequencing and order-effects feature summary."""

from diamond_gems.features.sequencing import build_pitch_sequencing_summary


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


def test_sequencing_previous_pitch_and_rates_with_grouping() -> None:
    """Previous pitch type, rates, and grouping should be correct by pitcher/game."""
    rows = [
        # pitcher 1, game 10
        {"game_id": 10, "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01", "season": 2024, "pitch_type": "FF", "pitch_name": "Fastball", "description": "called_strike"},
        {"game_id": 10, "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01", "season": 2024, "pitch_type": "SL", "pitch_name": "Slider", "description": "swinging_strike"},
        {"game_id": 10, "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01", "season": 2024, "pitch_type": "FF", "pitch_name": "Fastball", "description": "foul"},
        {"game_id": 10, "pitcher_id": 1, "pitcher_name": "P1", "game_date": "2024-04-01", "season": 2024, "pitch_type": "CH", "pitch_name": "Changeup", "description": "called_strike"},
        # pitcher 2, same game (should not mix sequences)
        {"game_id": 10, "pitcher_id": 2, "pitcher_name": "P2", "game_date": "2024-04-01", "season": 2024, "pitch_type": "FF", "pitch_name": "Fastball", "description": "called_strike"},
        {"game_id": 10, "pitcher_id": 2, "pitcher_name": "P2", "game_date": "2024-04-01", "season": 2024, "pitch_type": "SL", "pitch_name": "Slider", "description": "called_strike"},
    ]

    summary_rows = build_pitch_sequencing_summary(FakeDataFrame(rows)).to_dict("records")

    # appearance_id should be derived as game_id + pitcher_id
    p1_sl = next(r for r in summary_rows if r["appearance_id"] == "10_1" and r["pitch_type"] == "SL")
    p1_ff = next(r for r in summary_rows if r["appearance_id"] == "10_1" and r["pitch_type"] == "FF")
    p2_sl = next(r for r in summary_rows if r["appearance_id"] == "10_2" and r["pitch_type"] == "SL")

    # previous pitch type mode in group
    assert p1_sl["previous_pitch_type"] == "FF"

    # after-fastball rates for P1/SL: one pitch after FF and it is a whiff
    assert p1_sl["pitches_after_fastball"] == 1
    assert p1_sl["whiffs_after_fastball"] == 1
    assert p1_sl["whiff_rate_after_fastball"] == 1.0

    # after-breaking rates for P1/FF: one FF follows SL and not a whiff
    assert p1_ff["pitches_after_breaking_ball"] == 1
    assert p1_ff["whiffs_after_breaking_ball"] == 0
    assert p1_ff["whiff_rate_after_breaking_ball"] == 0.0

    # grouping by pitcher/game should keep P2 independent
    assert p2_sl["pitches_after_fastball"] == 1

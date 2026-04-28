"""Tests for content idea generation from flags."""

from diamond_gems.outputs.content_ideas import build_content_ideas


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


def test_content_ideas_high_flag_creation_and_fields_and_confidence() -> None:
    """High severity flags should create populated content ideas."""
    flags = [
        {
            "pitcher_id": 1,
            "pitcher_name": "P1",
            "appearance_id": "a1",
            "signal_category": "velocity",
            "signal_name": "strong velocity spike",
            "severity": "high",
            "raw_value": 2.1,
            "delta_value": 2.1,
            "percentile_score": 0.92,
            "confidence_score": 0.80,
            "context_note": "velocity up",
            "auto_generated_angle": "Stuff jump",
            "opponent_team_id": "BOS",
        }
    ]

    ideas = build_content_ideas(FakeDataFrame(flags)).to_dict("records")
    assert len(ideas) == 1

    idea = ideas[0]
    assert idea["primary_signal_name"] == "strong velocity spike"
    assert idea["headline_angle"]
    assert idea["thesis"]
    assert idea["content_format"] == "short_form_video"
    assert idea["status"] == "new"
    assert idea["confidence"] == "high"


def test_content_ideas_ignore_only_low_severity_flags() -> None:
    """Only low/medium severity flags should not produce ideas."""
    flags = [
        {
            "pitcher_id": 2,
            "pitcher_name": "P2",
            "appearance_id": "a2",
            "signal_category": "confidence",
            "signal_name": "low confidence warning",
            "severity": "low",
            "confidence_score": 0.2,
        }
    ]

    ideas = build_content_ideas(FakeDataFrame(flags)).to_dict("records")
    assert ideas == []

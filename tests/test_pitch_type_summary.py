"""Tests for pitcher pitch-type summary transform."""

from copy import deepcopy

from diamond_gems.transform.pitch_type_summary import build_pitcher_pitch_type_summary


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


def _appearance(appearance_id: str) -> dict:
    return {
        "appearance_id": appearance_id,
        "pitcher_id": 10,
        "pitcher_name": "Pitcher A",
        "game_id": 111,
        "game_date": "2024-04-01",
        "season": 2024,
        "opponent_team_id": "BOS",
    }


def _event(appearance_id: str, pitch_type: str, **kwargs) -> dict:
    row = {
        "appearance_id": appearance_id,
        "pitch_type": pitch_type,
        "pitch_name": pitch_type,
        "release_speed": 95.0,
        "release_spin_rate": 2300.0,
        "release_extension": 6.1,
        "pfx_x": 0.1,
        "pfx_z": 1.1,
        "swing_flag": False,
        "whiff_flag": False,
        "called_strike_flag": False,
        "in_zone_flag": True,
        "chase_flag": False,
        "batted_ball_flag": False,
        "hard_hit_flag": False,
        "launch_speed": None,
        "estimated_woba_using_speedangle": None,
        "woba_value": None,
    }
    row.update(kwargs)
    return row


def test_pitch_type_summary_usage_counts_and_rates() -> None:
    """Usage sums, counts, and denominators should be correct."""
    appearances = FakeDataFrame([_appearance("A1"), _appearance("A2")])

    events = [
        _event("A1", "FF", swing_flag=True, whiff_flag=True, in_zone_flag=True),
        _event("A1", "FF", swing_flag=True, whiff_flag=False, in_zone_flag=False, chase_flag=True),
        _event("A1", "FF", called_strike_flag=True, in_zone_flag=True),
        _event(
            "A1",
            "SL",
            swing_flag=True,
            whiff_flag=False,
            in_zone_flag=False,
            chase_flag=True,
            batted_ball_flag=True,
            hard_hit_flag=True,
            launch_speed=100.0,
            estimated_woba_using_speedangle=0.8,
            woba_value=1.7,
        ),
    ]

    # Eight pitch-type rows to exceed low-sample threshold for A2/FF.
    for _ in range(8):
        events.append(_event("A2", "FF"))

    pitch_events = FakeDataFrame(events)
    original_events = deepcopy(events)
    original_appearances = deepcopy(appearances.to_dict("records"))

    summary_rows = build_pitcher_pitch_type_summary(pitch_events, appearances).to_dict("records")

    a1_rows = [row for row in summary_rows if row["appearance_id"] == "A1"]
    ff_row = next(row for row in a1_rows if row["pitch_type"] == "FF")
    sl_row = next(row for row in a1_rows if row["pitch_type"] == "SL")
    a2_ff = next(row for row in summary_rows if row["appearance_id"] == "A2" and row["pitch_type"] == "FF")

    # usage rates sum to ~1 per appearance
    assert abs(sum(row["usage_rate"] for row in a1_rows) - 1.0) < 1e-9

    # pitch counts
    assert ff_row["pitch_count"] == 3
    assert sl_row["pitch_count"] == 1

    # denominator checks
    assert ff_row["whiff_rate"] == 0.5  # 1 whiff / 2 swings
    assert ff_row["contact_rate"] == 0.5  # 1 contact / 2 swings
    assert ff_row["chase_rate"] == 1.0  # 1 chase / 1 out-of-zone

    # low sample logic
    assert ff_row["low_sample_flag"] is True
    assert sl_row["low_sample_flag"] is True
    assert a2_ff["low_sample_flag"] is False

    # input non-mutation
    assert events == original_events
    assert appearances.to_dict("records") == original_appearances

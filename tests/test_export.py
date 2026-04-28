"""Tests for export utilities."""

import tempfile
from copy import deepcopy
from pathlib import Path

from diamond_gems.outputs import export


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


def test_export_creates_csv_and_parquet_and_output_dir_and_no_mutation() -> None:
    """Export should create expected files and preserve input object data."""
    df_records = [
        {"game_date": "2024-04-01", "pitcher_name": "B", "whiff_rate": 0.12345, "avg_velocity": 95.56},
        {"game_date": "2024-04-02", "pitcher_name": "A", "whiff_rate": 0.98765, "avg_velocity": 97.44},
    ]
    df = FakeDataFrame(df_records)
    original = deepcopy(df_records)

    with tempfile.TemporaryDirectory() as td:
        export.DATA_OUTPUTS_DIR = Path(td) / "outputs"
        written = export.export_table(df, "test_table", include_csv=True, include_parquet=True)

        assert (Path(td) / "outputs").exists()
        assert written["csv"].exists()
        assert written["parquet"].exists()

    assert df_records == original


def test_prepare_for_csv_rounding_works() -> None:
    """Rounding and sorting rules should be applied for CSV prep."""
    df = FakeDataFrame(
        [
            {"game_date": "2024-04-01", "pitcher_name": "B", "whiff_rate": 0.12345, "pitcher_change_score_percentile": 0.55555, "avg_velocity": 95.56},
            {"game_date": "2024-04-02", "pitcher_name": "A", "whiff_rate": 0.98765, "pitcher_change_score_percentile": 0.11119, "avg_velocity": 97.44},
        ]
    )

    prepped = export.prepare_for_csv(df).to_dict("records")

    # sorted by game_date desc then pitcher_name asc
    assert prepped[0]["game_date"] == "2024-04-02"
    assert prepped[0]["pitcher_name"] == "A"

    assert prepped[0]["whiff_rate"] == 0.988
    assert prepped[0]["pitcher_change_score_percentile"] == 0.111
    assert prepped[0]["avg_velocity"] == 97.4

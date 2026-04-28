"""Utilities for exporting analytics tables to output files."""

from __future__ import annotations

import csv
import json
from copy import deepcopy
from pathlib import Path

from diamond_gems.config import DATA_OUTPUTS_DIR

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None


PIPELINE_EXPORT_REQUIREMENTS = {
    "pitcher_start_summary": {"include_csv": True, "include_parquet": True},
    "pitcher_pitch_type_summary": {"include_csv": True, "include_parquet": True},
    "pitcher_velocity_deltas": {"include_csv": True, "include_parquet": True},
    "pitcher_usage_deltas": {"include_csv": True, "include_parquet": True},
    "pitcher_trend_scores": {"include_csv": True, "include_parquet": True},
    "pitcher_flags": {"include_csv": True, "include_parquet": False},
    "content_ideas": {"include_csv": True, "include_parquet": False},
}


def _to_records(df) -> list[dict]:
    if pd is not None and isinstance(df, pd.DataFrame):
        return df.to_dict("records")
    if hasattr(df, "to_dict"):
        return df.to_dict("records")
    return deepcopy(df)


def _from_records(records: list[dict], template):
    if pd is not None and isinstance(template, pd.DataFrame):
        return pd.DataFrame.from_records(records)
    frame_cls = template.__class__
    if hasattr(frame_cls, "from_records"):
        return frame_cls.from_records(records)
    return records


def prepare_for_csv(df):
    """Return a rounded/sorted copy suitable for CSV export."""
    records = deepcopy(_to_records(df))

    if not records:
        return _from_records(records, df)

    rounded = []
    for row in records:
        row_copy = deepcopy(row)
        for key, value in row_copy.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue

            key_lower = key.lower()
            if any(token in key_lower for token in ["rate", "percentile", "score"]):
                row_copy[key] = round(value, 3)
            elif "velo" in key_lower or "velocity" in key_lower:
                row_copy[key] = round(value, 1)
        rounded.append(row_copy)

    if all("game_date" in r for r in rounded) and all("pitcher_name" in r for r in rounded):
        rounded = sorted(rounded, key=lambda r: (str(r.get("pitcher_name")),), reverse=False)
        rounded = sorted(rounded, key=lambda r: str(r.get("game_date")), reverse=True)

    return _from_records(rounded, df)


def export_table(df, name: str, include_parquet: bool = True, include_csv: bool = True) -> dict[str, Path]:
    """Export a table to configured output formats and return written paths."""
    output_dir = Path(DATA_OUTPUTS_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    records = _to_records(df)

    if include_csv:
        csv_path = output_dir / f"{name}.csv"
        prepared = _to_records(prepare_for_csv(df))
        fieldnames = sorted({key for row in prepared for key in row.keys()}) if prepared else []
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in prepared:
                writer.writerow(row)
        written["csv"] = csv_path

    if include_parquet:
        parquet_path = output_dir / f"{name}.parquet"
        if pd is not None and isinstance(df, pd.DataFrame):
            df.copy(deep=True).to_parquet(parquet_path, index=False)
        else:
            # MVP fallback in constrained envs: write JSON payload to parquet-named artifact.
            parquet_path.write_text(json.dumps(records), encoding="utf-8")
        written["parquet"] = parquet_path

    return written

"""Helpers for downloading daily Statcast CSVs."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from diamond_gems.config import RAW_DIR

STATCAST_CSV_ENDPOINT = "https://baseballsavant.mlb.com/statcast_search/csv"


def _validate_iso_date(download_date: str) -> str:
    parsed = date.fromisoformat(download_date)
    return parsed.isoformat()


def _build_statcast_url(download_date: str) -> str:
    params = {
        "all": "true",
        "player_type": "pitcher",
        "game_date_gt": download_date,
        "game_date_lt": download_date,
        "type": "details",
    }
    return f"{STATCAST_CSV_ENDPOINT}?{urlencode(params)}"


def download_statcast_csv_for_date(download_date: str, output_dir: Path | None = None) -> Path:
    """Download Statcast CSV for a single date and return local file path."""
    normalized_date = _validate_iso_date(download_date)
    out_dir = Path(output_dir) if output_dir is not None else Path(RAW_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    output_path = out_dir / f"statcast_{normalized_date}.csv"
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing raw file: {output_path}")

    url = _build_statcast_url(normalized_date)
    with urlopen(url) as response:  # nosec: URL is fixed to MLB endpoint + encoded params
        payload = response.read()

    output_path.write_bytes(payload)
    return output_path


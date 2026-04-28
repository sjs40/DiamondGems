"""Helpers for downloading daily Statcast CSVs."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from diamond_gems.config import RAW_DIR

STATCAST_CSV_ENDPOINT = "https://baseballsavant.mlb.com/statcast_search/csv"

try:
    from pybaseball import statcast as _pybaseball_statcast  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    _pybaseball_statcast = None


def _validate_iso_date(download_date: str) -> str:
    parsed = date.fromisoformat(download_date)
    return parsed.isoformat()


def _build_statcast_url(start_date: str, end_date: str) -> str:
    params = {
        "all": "true",
        "player_type": "pitcher",
        "game_date_gt": start_date,
        "game_date_lt": end_date,
        "type": "details",
    }
    return f"{STATCAST_CSV_ENDPOINT}?{urlencode(params)}"


def _download_via_savant(start_date: str, end_date: str) -> bytes:
    url = _build_statcast_url(start_date, end_date)
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (DiamondGems; +https://github.com/)",
            "Accept": "text/csv,*/*",
            "Referer": "https://baseballsavant.mlb.com/",
        },
    )
    try:
        with urlopen(request) as response:  # nosec: URL is fixed to MLB endpoint + encoded params
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(
            f"Statcast download failed for window {start_date}..{end_date} with HTTP {exc.code}. "
            "Savant endpoint may be blocked."
        ) from exc


def _download_via_pybaseball(start_date: str, end_date: str) -> bytes:
    if _pybaseball_statcast is None:
        raise RuntimeError("pybaseball is not installed. Install it to use provider='pybaseball'.")
    frame = _pybaseball_statcast(start_dt=start_date, end_dt=end_date)
    return frame.to_csv(index=False).encode("utf-8")


def download_statcast_csv_for_date(
    download_date: str,
    output_dir: Path | None = None,
    provider: str = "auto",
    lookback_days: int = 120,
) -> Path:
    """Download Statcast CSV window ending on `download_date` and return local file path."""
    normalized_date = _validate_iso_date(download_date)
    start_date = (date.fromisoformat(normalized_date) - timedelta(days=lookback_days)).isoformat()
    out_dir = Path(output_dir) if output_dir is not None else Path(RAW_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    output_path = out_dir / f"statcast_{normalized_date}.csv"
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing raw file: {output_path}")

    valid = {"auto", "savant", "pybaseball"}
    if provider not in valid:
        raise ValueError(f"Unknown provider '{provider}'. Expected one of: {sorted(valid)}.")

    if provider == "savant":
        payload = _download_via_savant(start_date, normalized_date)
    elif provider == "pybaseball":
        payload = _download_via_pybaseball(start_date, normalized_date)
    else:
        try:
            payload = _download_via_savant(start_date, normalized_date)
        except RuntimeError as savant_exc:
            try:
                payload = _download_via_pybaseball(start_date, normalized_date)
            except RuntimeError as pybaseball_exc:
                raise RuntimeError(
                    f"{savant_exc} Fallback via pybaseball also failed: {pybaseball_exc}. "
                    "Use manual CSV export and pass --input-file."
                ) from pybaseball_exc

    output_path.write_bytes(payload)
    return output_path

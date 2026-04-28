"""Tests for Statcast download helper."""

from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError

import pytest

from diamond_gems.ingest.statcast_download import download_statcast_csv_for_date


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._payload


def test_download_statcast_csv_for_date_writes_file(monkeypatch, tmp_path: Path) -> None:
    captured = {"url": ""}

    def _fake_urlopen(request):
        captured["url"] = request.full_url
        assert request.headers.get("User-agent")
        return _FakeResponse(b"game_pk,game_date\n1,2024-04-01\n")

    monkeypatch.setattr("diamond_gems.ingest.statcast_download.urlopen", _fake_urlopen)

    output_path = download_statcast_csv_for_date("2024-04-01", output_dir=tmp_path)
    assert output_path.exists()
    assert output_path.name == "statcast_2024-04-01.csv"
    assert "game_date_gt=2024-04-01" in captured["url"]
    assert "game_date_lt=2024-04-01" in captured["url"]


def test_download_statcast_csv_for_date_does_not_overwrite(monkeypatch, tmp_path: Path) -> None:
    existing = tmp_path / "statcast_2024-04-01.csv"
    existing.write_text("already here", encoding="utf-8")

    monkeypatch.setattr(
        "diamond_gems.ingest.statcast_download.urlopen",
        lambda url: _FakeResponse(b"ignored"),
    )

    with pytest.raises(FileExistsError):
        download_statcast_csv_for_date("2024-04-01", output_dir=tmp_path)


def test_download_statcast_csv_for_date_http_error_has_helpful_message(monkeypatch, tmp_path: Path) -> None:
    def _raise_http_error(request):
        raise HTTPError(request.full_url, 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr("diamond_gems.ingest.statcast_download.urlopen", _raise_http_error)

    with pytest.raises(RuntimeError, match="Savant endpoint may be blocked"):
        download_statcast_csv_for_date("2024-04-01", output_dir=tmp_path)


def test_download_statcast_csv_for_date_auto_falls_back_to_pybaseball(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "diamond_gems.ingest.statcast_download._download_via_savant",
        lambda normalized_date: (_ for _ in ()).throw(RuntimeError("blocked")),
    )
    monkeypatch.setattr(
        "diamond_gems.ingest.statcast_download._download_via_pybaseball",
        lambda normalized_date: b"game_pk,game_date\n2,2024-04-01\n",
    )

    output_path = download_statcast_csv_for_date("2024-04-01", output_dir=tmp_path, provider="auto")
    assert output_path.read_text(encoding="utf-8").startswith("game_pk,game_date")


def test_download_statcast_csv_for_date_rejects_unknown_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown provider"):
        download_statcast_csv_for_date("2024-04-01", output_dir=tmp_path, provider="unknown")


def test_download_statcast_csv_for_date_validates_date(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        download_statcast_csv_for_date("2024-99-99", output_dir=tmp_path)

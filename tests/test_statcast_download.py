"""Tests for Statcast download helper."""

from __future__ import annotations

from pathlib import Path

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

    def _fake_urlopen(url: str):
        captured["url"] = url
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


def test_download_statcast_csv_for_date_validates_date(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        download_statcast_csv_for_date("2024-99-99", output_dir=tmp_path)


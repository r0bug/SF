"""Song folders are dated by generation date, and failed downloads leave no trace."""

import os
import sys
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "songfactory"))

from automation.download_manager import DownloadManager, song_date_prefix  # noqa: E402


def test_prefers_lalals_created_at_over_created_at():
    song = {"lalals_created_at": "2026-05-22T18:00:00.000Z",
            "created_at": "2026-09-28 18:13:15"}
    assert song_date_prefix(song) == "2026-05-22"


def test_created_at_is_utc_converted_to_local(monkeypatch):
    monkeypatch.setenv("TZ", "America/Los_Angeles")
    import time
    time.tzset()
    try:
        # 06:08 UTC on the 10th is the evening of the 9th in Yakima
        assert song_date_prefix({"created_at": "2026-11-10 06:08:46"}) == "2026-11-09"
    finally:
        monkeypatch.delenv("TZ")
        time.tzset()


def test_unparseable_returns_empty():
    assert song_date_prefix({"created_at": "garbage"}) == ""
    assert song_date_prefix({}) == ""


def _fake_retrieve(data=b"\xff\xfb" + b"\0" * 20000):
    def retrieve(url, tmp):
        Path(tmp).write_bytes(data)
    return retrieve


def test_save_from_url_uses_date_prefix(tmp_path):
    dm = DownloadManager(str(tmp_path))
    with mock.patch("urllib.request.urlretrieve", _fake_retrieve()), \
         mock.patch.object(dm, "validate_audio_file",
                           return_value={"valid": True, "errors": [], "size": 1}):
        p = dm.save_from_url("https://x/a.mp3", "Song", 1, date_prefix="2026-01-11")
    assert p.parent.name == "2026-01-11_Song"


def test_failed_download_leaves_no_empty_folder(tmp_path):
    dm = DownloadManager(str(tmp_path))

    def boom(url, tmp):
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)

    with mock.patch("urllib.request.urlretrieve", boom):
        try:
            dm.save_from_url("https://x/a.wav", "Song", 1, date_prefix="2026-01-11")
        except urllib.error.HTTPError:
            pass
    assert list(tmp_path.iterdir()) == []


def test_failed_download_keeps_existing_folder(tmp_path):
    dm = DownloadManager(str(tmp_path))
    existing = tmp_path / "2026-01-11_Song"
    existing.mkdir()
    (existing / "Song_v1.mp3").write_bytes(b"x")

    def boom(url, tmp):
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)

    with mock.patch("urllib.request.urlretrieve", boom):
        try:
            dm.save_from_url("https://x/a.wav", "Song", 1,
                             target_path=existing / "Song_v1.wav")
        except urllib.error.HTTPError:
            pass
    assert existing.is_dir() and (existing / "Song_v1.mp3").exists()


def test_duplicate_title_keeps_v1_and_v2_together(tmp_path):
    dm = DownloadManager(str(tmp_path))
    base = tmp_path / "2026-11-09_Song"
    base.mkdir()
    (base / "Song_v1.mp3").write_bytes(b"x")
    (base / "Song_v2.mp3").write_bytes(b"x")

    p1 = dm.get_file_path("Song", 1, date_prefix="2026-11-09")
    p1.write_bytes(b"x")
    with mock.patch("automation.download_manager.datetime") as dt:
        dt.now.return_value.strftime.return_value = "999999"  # a later second
        p2 = dm.get_file_path("Song", 2, date_prefix="2026-11-09")
    assert p1.parent != base
    assert p2.parent == p1.parent

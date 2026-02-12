"""Tests for download verification, selector registry, and card matching."""

import json
import struct
from datetime import date
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from automation.download_manager import (
    DownloadManager,
    DownloadVerificationError,
    MIN_AUDIO_BYTES,
)
from automation.selector_registry import SelectorRegistry


# ── TestValidateAudioFile ────────────────────────────────────────────


class TestValidateAudioFile:
    """Tests for DownloadManager.validate_audio_file()."""

    def test_valid_mp3_sync_word(self, tmp_path):
        """MP3 with 0xFF 0xFB sync word is valid."""
        f = tmp_path / "song.mp3"
        # 0xFF 0xFB = valid MPEG1 Layer3 sync word, then pad to >10KB
        f.write_bytes(b"\xff\xfb" + b"\x00" * (MIN_AUDIO_BYTES + 100))
        result = DownloadManager.validate_audio_file(f)
        assert result["valid"] is True
        assert result["format"] == "mp3"
        assert result["size"] > MIN_AUDIO_BYTES
        assert not result["errors"]

    def test_valid_id3(self, tmp_path):
        """MP3 with ID3 header is valid."""
        f = tmp_path / "song.mp3"
        f.write_bytes(b"ID3" + b"\x00" * (MIN_AUDIO_BYTES + 100))
        result = DownloadManager.validate_audio_file(f)
        assert result["valid"] is True
        assert result["format"] == "mp3/id3"

    def test_valid_wav_riff(self, tmp_path):
        """WAV/RIFF file is valid."""
        f = tmp_path / "song.wav"
        f.write_bytes(b"RIFF" + b"\x00" * (MIN_AUDIO_BYTES + 100))
        result = DownloadManager.validate_audio_file(f)
        assert result["valid"] is True
        assert result["format"] == "wav"

    def test_empty_file_fails(self, tmp_path):
        """Empty file is invalid."""
        f = tmp_path / "empty.mp3"
        f.write_bytes(b"")
        result = DownloadManager.validate_audio_file(f)
        assert result["valid"] is False
        assert result["size"] == 0
        assert any("too small" in e for e in result["errors"])

    def test_tiny_file_fails(self, tmp_path):
        """File under MIN_AUDIO_BYTES is invalid."""
        f = tmp_path / "tiny.mp3"
        f.write_bytes(b"\xff\xfb" + b"\x00" * 100)
        result = DownloadManager.validate_audio_file(f)
        assert result["valid"] is False
        assert any("too small" in e for e in result["errors"])

    def test_html_error_page_fails(self, tmp_path):
        """HTML error page (starts with '<') is detected as invalid."""
        f = tmp_path / "error.mp3"
        content = b"<html><body>Error 403</body></html>"
        # Pad to get past size check
        f.write_bytes(content + b"\x00" * MIN_AUDIO_BYTES)
        result = DownloadManager.validate_audio_file(f)
        assert result["valid"] is False
        assert any("text/markup" in e for e in result["errors"])

    def test_json_error_fails(self, tmp_path):
        """JSON error response is detected as invalid."""
        f = tmp_path / "error.mp3"
        content = b'{"error": "not found"}'
        f.write_bytes(content + b"\x00" * MIN_AUDIO_BYTES)
        result = DownloadManager.validate_audio_file(f)
        assert result["valid"] is False
        assert any("text/markup" in e for e in result["errors"])

    def test_nonexistent_file(self, tmp_path):
        """Non-existent file reports error."""
        f = tmp_path / "nope.mp3"
        result = DownloadManager.validate_audio_file(f)
        assert result["valid"] is False
        assert any("does not exist" in e for e in result["errors"])

    def test_valid_ogg(self, tmp_path):
        """OGG file is valid."""
        f = tmp_path / "song.ogg"
        f.write_bytes(b"OggS" + b"\x00" * (MIN_AUDIO_BYTES + 100))
        result = DownloadManager.validate_audio_file(f)
        assert result["valid"] is True
        assert result["format"] == "ogg"

    def test_valid_flac(self, tmp_path):
        """FLAC file is valid."""
        f = tmp_path / "song.flac"
        f.write_bytes(b"fLaC" + b"\x00" * (MIN_AUDIO_BYTES + 100))
        result = DownloadManager.validate_audio_file(f)
        assert result["valid"] is True
        assert result["format"] == "flac"


# ── TestGetRemoteFileSize ────────────────────────────────────────────


class TestGetRemoteFileSize:
    """Tests for DownloadManager.get_remote_file_size()."""

    def test_returns_content_length(self):
        """Returns Content-Length as int on success."""
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": "123456"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("automation.download_manager.urllib.request.urlopen", return_value=mock_resp):
            size = DownloadManager.get_remote_file_size("https://example.com/song.mp3")
        assert size == 123456

    def test_returns_none_on_error(self):
        """Returns None on network error."""
        with patch("automation.download_manager.urllib.request.urlopen", side_effect=Exception("fail")):
            size = DownloadManager.get_remote_file_size("https://example.com/song.mp3")
        assert size is None

    def test_returns_none_on_missing_header(self):
        """Returns None when Content-Length header is absent."""
        mock_resp = MagicMock()
        mock_resp.headers = {}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("automation.download_manager.urllib.request.urlopen", return_value=mock_resp):
            size = DownloadManager.get_remote_file_size("https://example.com/song.mp3")
        assert size is None


# ── TestSaveFromUrlValidation ────────────────────────────────────────


class TestSaveFromUrlValidation:
    """Tests for save_from_url() validation integration."""

    def _make_dm(self, tmp_path):
        return DownloadManager(str(tmp_path / "downloads"))

    def _fake_download(self, target_path, content):
        """Helper to mock urlretrieve: writes content to the target path."""
        def _urlretrieve(url, dest):
            Path(dest).write_bytes(content)
        return _urlretrieve

    def test_passes_when_valid_audio(self, tmp_path):
        """Valid MP3 file passes verification."""
        dm = self._make_dm(tmp_path)
        content = b"\xff\xfb" + b"\x00" * (MIN_AUDIO_BYTES + 100)

        with patch("automation.download_manager.urllib.request.urlretrieve",
                    side_effect=self._fake_download(None, content)):
            path = dm.save_from_url("https://s3.com/song.mp3", "Test Song", 1)
        assert path.exists()
        assert dm.last_download_size == len(content)

    def test_raises_on_invalid_audio(self, tmp_path):
        """Invalid audio (HTML page) raises DownloadVerificationError."""
        dm = self._make_dm(tmp_path)
        content = b"<html>Error</html>" + b"\x00" * MIN_AUDIO_BYTES

        with patch("automation.download_manager.urllib.request.urlretrieve",
                    side_effect=self._fake_download(None, content)):
            with pytest.raises(DownloadVerificationError):
                dm.save_from_url("https://s3.com/song.mp3", "Test Song", 1)

    def test_raises_on_size_mismatch(self, tmp_path):
        """Raises DownloadVerificationError when size differs >5%."""
        dm = self._make_dm(tmp_path)
        content = b"\xff\xfb" + b"\x00" * (MIN_AUDIO_BYTES + 100)
        expected = len(content) * 3  # way off

        with patch("automation.download_manager.urllib.request.urlretrieve",
                    side_effect=self._fake_download(None, content)):
            with pytest.raises(DownloadVerificationError) as exc_info:
                dm.save_from_url(
                    "https://s3.com/song.mp3", "Test Song", 1,
                    expected_size=expected,
                )
        assert exc_info.value.expected_size == expected
        assert exc_info.value.actual_size == len(content)

    def test_passes_when_size_within_tolerance(self, tmp_path):
        """No error when size within 5% of expected."""
        dm = self._make_dm(tmp_path)
        content = b"\xff\xfb" + b"\x00" * (MIN_AUDIO_BYTES + 100)
        expected = len(content)  # exact match

        with patch("automation.download_manager.urllib.request.urlretrieve",
                    side_effect=self._fake_download(None, content)):
            path = dm.save_from_url(
                "https://s3.com/song.mp3", "Test Song", 1,
                expected_size=expected,
            )
        assert path.exists()


# ── TestSelectorRegistry ────────────────────────────────────────────


class TestSelectorRegistry:
    """Tests for SelectorRegistry promote/demote/persist."""

    def test_register_group(self, tmp_path):
        reg = SelectorRegistry(tmp_path / "reg.json")
        reg.register_group("btn", ["a", "b", "c"])
        assert reg.get_selectors("btn") == ["a", "b", "c"]

    def test_promote(self, tmp_path):
        reg = SelectorRegistry(tmp_path / "reg.json")
        reg.register_group("btn", ["a", "b", "c"])
        reg.promote("btn", "c")
        assert reg.get_selectors("btn") == ["c", "a", "b"]

    def test_demote(self, tmp_path):
        reg = SelectorRegistry(tmp_path / "reg.json")
        reg.register_group("btn", ["a", "b", "c"])
        reg.demote("btn", "a")
        assert reg.get_selectors("btn") == ["b", "c", "a"]

    def test_persistence_round_trip(self, tmp_path):
        path = tmp_path / "reg.json"
        reg1 = SelectorRegistry(path)
        reg1.register_group("btn", ["a", "b", "c"])
        reg1.promote("btn", "c")

        # Load fresh instance from same file
        reg2 = SelectorRegistry(path)
        assert reg2.get_selectors("btn") == ["c", "a", "b"]

    def test_register_noop_if_persisted(self, tmp_path):
        path = tmp_path / "reg.json"
        reg = SelectorRegistry(path)
        reg.register_group("btn", ["a", "b", "c"])
        reg.promote("btn", "c")

        # Re-registering does NOT overwrite learned order
        reg.register_group("btn", ["x", "y", "z"])
        assert reg.get_selectors("btn") == ["c", "a", "b"]

    def test_reset_overwrites(self, tmp_path):
        reg = SelectorRegistry(tmp_path / "reg.json")
        reg.register_group("btn", ["a", "b", "c"])
        reg.promote("btn", "c")
        reg.reset_group("btn", ["x", "y"])
        assert reg.get_selectors("btn") == ["x", "y"]

    def test_get_selectors_unknown_group(self, tmp_path):
        reg = SelectorRegistry(tmp_path / "reg.json")
        assert reg.get_selectors("nonexistent") == []

    def test_promote_unknown_group(self, tmp_path):
        """Promote on unknown group is a no-op."""
        reg = SelectorRegistry(tmp_path / "reg.json")
        reg.promote("nonexistent", "a")  # should not raise

    def test_demote_unknown_selector(self, tmp_path):
        """Demote unknown selector in known group is a no-op."""
        reg = SelectorRegistry(tmp_path / "reg.json")
        reg.register_group("btn", ["a", "b"])
        reg.demote("btn", "z")  # z not in group
        assert reg.get_selectors("btn") == ["a", "b"]


# ── TestCardMatchingProjectId ────────────────────────────────────────


class TestCardMatchingProjectId:
    """Tests for _find_card_on_home project_id priority matching."""

    def _make_mock_page(self, cards_data):
        """Create a mock page with ProjectItem cards.

        cards_data: list of dicts with 'project_id' and 'text' keys.
        """
        page = MagicMock()
        context = MagicMock()

        cards_locator = MagicMock()
        cards_locator.count.return_value = len(cards_data)

        card_mocks = []
        for cd in cards_data:
            card = MagicMock()
            card.get_attribute.return_value = cd.get("project_id", "")
            card.inner_text.return_value = cd.get("text", "")
            card_mocks.append(card)

        cards_locator.nth = lambda i: card_mocks[i]
        page.locator.return_value = cards_locator

        return page, context

    def test_project_id_match_preferred(self):
        """When task_id matches a card's data-project-id, that card is selected."""
        from automation.lalals_driver import LalalsDriver

        page, ctx = self._make_mock_page([
            {"project_id": "abc-123", "text": "Wrong Song Title"},
            {"project_id": "xyz-789", "text": "Also Wrong"},
        ])

        driver = LalalsDriver.__new__(LalalsDriver)
        driver.page = page
        driver.context = ctx
        from automation.selector_registry import SelectorRegistry
        driver._registry = SelectorRegistry(Path("/tmp/_test_reg_unused.json"))

        result = driver._find_card_on_home("My Song", task_id="abc-123")
        assert result is not None
        assert result.get_attribute("data-project-id") == "abc-123"

    def test_fallback_to_text_when_no_project_id_match(self):
        """Falls back to text matching when task_id doesn't match any card."""
        from automation.lalals_driver import LalalsDriver

        page, ctx = self._make_mock_page([
            {"project_id": "other-id", "text": "Some other song"},
            {"project_id": "another-id", "text": "My Cool Song is here"},
        ])

        driver = LalalsDriver.__new__(LalalsDriver)
        driver.page = page
        driver.context = ctx
        from automation.selector_registry import SelectorRegistry
        driver._registry = SelectorRegistry(Path("/tmp/_test_reg_unused2.json"))

        result = driver._find_card_on_home(
            "My Cool Song", task_id="nonexistent-task"
        )
        assert result is not None
        # Should match card #1 (index 1) by text
        assert result.get_attribute("data-project-id") == "another-id"

    def test_no_match_returns_none(self):
        """Returns None when neither project_id nor text matches."""
        from automation.lalals_driver import LalalsDriver

        page, ctx = self._make_mock_page([
            {"project_id": "other-id", "text": "Completely different song"},
        ])

        driver = LalalsDriver.__new__(LalalsDriver)
        driver.page = page
        driver.context = ctx
        from automation.selector_registry import SelectorRegistry
        driver._registry = SelectorRegistry(Path("/tmp/_test_reg_unused3.json"))

        result = driver._find_card_on_home(
            "Nonexistent Song With Many Words Here",
            task_id="wrong-id",
        )
        assert result is None


# ── TestFileSizePopulation ───────────────────────────────────────────


class TestFileSizePopulation:
    """Tests that file_size is stored after downloads."""

    def test_file_size_stored_after_url_download(self, tmp_path):
        """last_download_size is set after save_from_url."""
        dm = DownloadManager(str(tmp_path / "dl"))
        content = b"\xff\xfb" + b"\x00" * (MIN_AUDIO_BYTES + 100)

        def _urlretrieve(url, dest):
            Path(dest).write_bytes(content)

        with patch("automation.download_manager.urllib.request.urlretrieve",
                    side_effect=_urlretrieve):
            dm.save_from_url("https://s3.com/song.mp3", "Test", 1)

        assert dm.last_download_size == len(content)

    def test_file_size_stored_after_playwright_download(self, tmp_path):
        """last_download_size is set after save_playwright_download."""
        dm = DownloadManager(str(tmp_path / "dl"))
        content = b"\xff\xfb" + b"\x00" * (MIN_AUDIO_BYTES + 100)

        mock_download = MagicMock()
        mock_download.suggested_filename = "song.mp3"

        def _save_as(path):
            Path(path).write_bytes(content)

        mock_download.save_as = _save_as

        path = dm.save_playwright_download(mock_download, "Test", 1)
        assert dm.last_download_size == len(content)
        assert path.exists()


# ── TestDatePrefixedFolders ──────────────────────────────────────────


class TestDatePrefixedFolders:
    """Tests for date-prefixed download directory naming."""

    def test_get_song_dir_includes_date(self, tmp_path):
        """Directory name follows YYYY-MM-DD_slug pattern."""
        dm = DownloadManager(str(tmp_path / "dl"))
        song_dir = dm.get_song_dir("Treasure on Second Street", date_prefix="2026-02-12")
        assert song_dir.name == "2026-02-12_treasure-on-second-street"
        assert song_dir.exists()

    def test_get_song_dir_custom_date_prefix(self, tmp_path):
        """Explicit date_prefix is used verbatim."""
        dm = DownloadManager(str(tmp_path / "dl"))
        song_dir = dm.get_song_dir("My Song", date_prefix="2025-01-01")
        assert song_dir.name == "2025-01-01_my-song"

    def test_get_song_dir_default_is_today(self, tmp_path):
        """Default (empty) date_prefix uses today's date."""
        dm = DownloadManager(str(tmp_path / "dl"))
        song_dir = dm.get_song_dir("Hello World")
        today = date.today().isoformat()
        assert song_dir.name == f"{today}_hello-world"

    def test_get_file_path_with_date(self, tmp_path):
        """Full file path includes date in directory component."""
        dm = DownloadManager(str(tmp_path / "dl"))
        fp = dm.get_file_path("Test Song", 1, date_prefix="2026-03-15")
        assert "2026-03-15_test-song" in str(fp)
        assert fp.name == "test-song_v1.mp3"

    def test_get_track_file_path_with_date(self, tmp_path):
        """Track file path includes date in directory component."""
        dm = DownloadManager(str(tmp_path / "dl"))
        fp = dm.get_track_file_path("Test Song", "vocals", date_prefix="2026-04-20")
        assert "2026-04-20_test-song" in str(fp)
        assert fp.name == "test-song_vocals.mp3"

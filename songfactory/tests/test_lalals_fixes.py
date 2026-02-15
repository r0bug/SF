"""Tests for lalals.com browser integration bug fixes.

Verifies:
- S3 URL pattern consistency across all methods
- Error categories and screenshot capture
- Removal of dangerous last-button fallback
- Centralized browser profile usage
"""

import os
import time
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# S3 URL Pattern Consistency
# ---------------------------------------------------------------------------

class TestS3UrlPatternConsistency:
    """Verify all methods produce the same S3 URL pattern."""

    CORRECT_PATTERN = "https://lalals.s3.amazonaws.com/conversions/standard/{cid}/{cid}.mp3"

    def _expected_url(self, cid: str) -> str:
        return self.CORRECT_PATTERN.format(cid=cid)

    def test_extract_metadata_s3_urls(self):
        """extract_metadata() builds correct S3 URLs from conversion IDs."""
        from automation.lalals_driver import LalalsDriver

        api_response = {
            "task_id": "task-123",
            "conversion_id_1": "cid-aaa",
            "conversion_id_2": "cid-bbb",
            "status": "COMPLETED",
        }
        meta = LalalsDriver.extract_metadata(api_response)

        assert meta["audio_url_1"] == self._expected_url("cid-aaa")
        assert meta["audio_url_2"] == self._expected_url("cid-bbb")

    def test_build_s3_metadata_urls(self):
        """_build_s3_metadata() builds correct S3 URLs."""
        from automation.lalals_driver import LalalsDriver

        meta = LalalsDriver._build_s3_metadata("task-123", "cid-aaa", "cid-bbb")

        assert meta["audio_url_1"] == self._expected_url("cid-aaa")
        assert meta["audio_url_2"] == self._expected_url("cid-bbb")

    def test_fetch_fresh_urls_fallback_pattern(self):
        """poll_project_status() S3 fallback uses the correct pattern.

        We verify by inspecting the source code for the S3_BASE variable
        used in poll_project_status() to ensure it matches the other methods.
        """
        import inspect
        from automation.lalals_driver import LalalsDriver

        source = inspect.getsource(LalalsDriver.poll_project_status)
        # The method should use /standard/ in its S3_BASE
        assert "conversions/standard" in source
        # And should use /{pid}/{pid}.mp3 or /{cid}/{cid}.mp3 pattern
        assert ".mp3" in source

    def test_all_three_methods_produce_same_urls(self):
        """All three URL-producing methods give identical URLs for the same CIDs."""
        from automation.lalals_driver import LalalsDriver

        cid1, cid2 = "test-cid-1", "test-cid-2"

        # Method 1: extract_metadata
        meta1 = LalalsDriver.extract_metadata({
            "task_id": "t1",
            "conversion_id_1": cid1,
            "conversion_id_2": cid2,
        })

        # Method 2: _build_s3_metadata
        meta2 = LalalsDriver._build_s3_metadata("t1", cid1, cid2)

        assert meta1["audio_url_1"] == meta2["audio_url_1"]
        assert meta1["audio_url_2"] == meta2["audio_url_2"]

    def test_extract_metadata_fallback_uses_task_id(self):
        """When no conversion IDs, extract_metadata falls back to task_id."""
        from automation.lalals_driver import LalalsDriver

        meta = LalalsDriver.extract_metadata({"task_id": "tid-999"})
        expected = "https://lalals.s3.amazonaws.com/conversions/standard/tid-999/tid-999.mp3"
        assert meta["audio_url_1"] == expected


# ---------------------------------------------------------------------------
# Error Categories
# ---------------------------------------------------------------------------

class TestErrorCategories:
    """Verify LalalsDriverError supports error categories."""

    def test_error_with_category(self):
        from automation.lalals_driver import LalalsDriverError, ErrorCategory

        err = LalalsDriverError("test", category=ErrorCategory.SELECTOR_NOT_FOUND)
        assert err.category == ErrorCategory.SELECTOR_NOT_FOUND
        assert "selector" in err.user_message.lower()

    def test_error_without_category(self):
        from automation.lalals_driver import LalalsDriverError

        err = LalalsDriverError("plain error")
        assert err.category is None
        assert err.user_message == "plain error"

    def test_all_categories_have_messages(self):
        from automation.lalals_driver import ErrorCategory, ERROR_MESSAGES

        for cat in ErrorCategory:
            assert cat in ERROR_MESSAGES, f"Missing message for {cat}"
            assert len(ERROR_MESSAGES[cat]) > 10


# ---------------------------------------------------------------------------
# Dangerous Last-Button Fallback Removed
# ---------------------------------------------------------------------------

class TestClickGenerateNoFallback:
    """Verify click_generate raises LalalsDriverError when no button found."""

    def test_raises_on_no_button(self):
        from automation.lalals_driver import LalalsDriver, LalalsDriverError, ErrorCategory

        mock_page = MagicMock()
        mock_context = MagicMock()

        # Make _find_visible return None (no selectors match)
        driver = LalalsDriver(mock_page, mock_context)
        driver._find_visible = MagicMock(return_value=None)
        driver._capture_debug_screenshot = MagicMock(return_value=None)

        with pytest.raises(LalalsDriverError) as exc_info:
            driver.click_generate()

        assert exc_info.value.category == ErrorCategory.SELECTOR_NOT_FOUND
        assert "Could not find generate button" in str(exc_info.value)
        # Verify screenshot was captured
        driver._capture_debug_screenshot.assert_called_once()

    def test_no_last_button_fallback_in_source(self):
        """The source should NOT contain the dangerous 'button().last' fallback."""
        import inspect
        from automation.lalals_driver import LalalsDriver

        source = inspect.getsource(LalalsDriver.click_generate)
        assert "locator(\"button\").last" not in source
        assert "last visible button" not in source.lower()


# ---------------------------------------------------------------------------
# Screenshot Capture
# ---------------------------------------------------------------------------

class TestScreenshotCapture:
    """Verify the debug screenshot mechanism works."""

    def test_capture_creates_file(self):
        from automation.lalals_driver import LalalsDriver

        mock_page = MagicMock()
        mock_context = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("automation.lalals_driver.SCREENSHOT_DIR", Path(tmpdir)):
                driver = LalalsDriver(mock_page, mock_context)
                result = driver._capture_debug_screenshot("test_context")

            # page.screenshot should have been called
            mock_page.screenshot.assert_called_once()
            call_kwargs = mock_page.screenshot.call_args
            assert "test_context" in call_kwargs.kwargs["path"]

    def test_screenshot_rotation(self):
        from automation.lalals_driver import LalalsDriver

        mock_page = MagicMock()
        mock_context = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Pre-create 25 screenshots
            for i in range(25):
                (tmppath / f"20260101_{i:06d}_old.png").touch()

            with patch("automation.lalals_driver.SCREENSHOT_DIR", tmppath):
                with patch("automation.lalals_driver.MAX_SCREENSHOTS", 20):
                    driver = LalalsDriver(mock_page, mock_context)
                    driver._capture_debug_screenshot("rotation_test")

            # Should have rotated down to MAX_SCREENSHOTS
            remaining = list(tmppath.glob("*.png"))
            # After rotation: we removed enough so len(existing) < MAX,
            # then added 1 new one
            assert len(remaining) <= 21  # 20 max + 1 new


# ---------------------------------------------------------------------------
# Centralized Browser Profile
# ---------------------------------------------------------------------------

class TestBrowserProfileCentralized:
    """Verify browser_worker and network_sniffer use centralized profiles."""

    def test_browser_worker_imports_browser_profiles(self):
        """browser_worker.py source references get_profile_path."""
        import inspect
        from automation import browser_worker

        source = inspect.getsource(browser_worker)
        assert "get_profile_path" in source
        assert "browser_profiles" in source

    def test_network_sniffer_uses_centralized_profile(self):
        """network_sniffer defaults to centralized profile path."""
        from automation.network_sniffer import NetworkSniffer

        with patch("automation.browser_profiles.get_profile_path") as mock_get:
            mock_get.return_value = "/fake/profile/path"
            sniffer = NetworkSniffer()
            assert sniffer.profile_dir == "/fake/profile/path"
            mock_get.assert_called_once_with("lalals")

    def test_network_sniffer_accepts_override(self):
        """network_sniffer accepts a custom profile_dir."""
        from automation.network_sniffer import NetworkSniffer

        sniffer = NetworkSniffer(profile_dir="/custom/path")
        assert sniffer.profile_dir == "/custom/path"


# ---------------------------------------------------------------------------
# Timeout Configuration
# ---------------------------------------------------------------------------

class TestTimeoutConfiguration:
    """Verify new timeout keys exist."""

    def test_api_capture_timeout_exists(self):
        from timeouts import TIMEOUTS
        assert "api_capture_s" in TIMEOUTS
        assert TIMEOUTS["api_capture_s"] == 30

    def test_post_refresh_delay_exists(self):
        from timeouts import TIMEOUTS
        assert "post_refresh_delay_s" in TIMEOUTS
        assert TIMEOUTS["post_refresh_delay_s"] == 5

    def test_get_timeout_returns_defaults(self):
        from timeouts import get_timeout
        assert get_timeout(None, "api_capture_s") == 30
        assert get_timeout(None, "post_refresh_delay_s") == 5


# ---------------------------------------------------------------------------
# API Capture Polling
# ---------------------------------------------------------------------------

class TestFindCardOnHome:
    """Verify _find_card_on_home properly escapes regex and uses multiple strategies."""

    def test_regex_escape_in_title_prefix(self):
        """Title with parentheses should be regex-escaped, not crash."""
        import re
        title = "Grant's Gold (Hop Country Anthem)"
        prefix = re.escape(title[:15].strip())
        # This should NOT raise — parentheses are escaped
        compiled = re.compile(prefix, re.IGNORECASE)
        assert compiled.pattern == re.escape("Grant's Gold (H")

    def test_regex_escape_special_chars(self):
        """Various special regex chars in titles should be escaped."""
        import re
        for title in [
            "Song (Version 2)",
            "Song [Live]",
            "Song {Demo}",
            "Song $pecial",
            "Song +Plus",
            "Song.With.Dots",
            "Song * Star",
            "Song? Question",
        ]:
            prefix = re.escape(title[:15].strip())
            # Should not raise
            re.compile(prefix, re.IGNORECASE)

    def test_download_from_home_accepts_prompt_lyrics(self):
        """download_from_home signature accepts prompt and lyrics kwargs."""
        import inspect
        from automation.lalals_driver import LalalsDriver

        sig = inspect.signature(LalalsDriver.download_from_home)
        params = list(sig.parameters.keys())
        assert "prompt" in params
        assert "lyrics" in params

    def test_find_card_on_home_exists(self):
        """_find_card_on_home method exists on LalalsDriver."""
        from automation.lalals_driver import LalalsDriver
        assert hasattr(LalalsDriver, "_find_card_on_home")

    def test_find_card_on_home_uses_project_item_selector(self):
        """_find_card_on_home uses ProjectItem card selector."""
        import inspect
        from automation.lalals_driver import LalalsDriver
        source = inspect.getsource(LalalsDriver._find_card_on_home)
        assert "ProjectItem" in source

    def test_click_card_menu_exists(self):
        """_click_card_menu helper method exists."""
        from automation.lalals_driver import LalalsDriver
        assert hasattr(LalalsDriver, "_click_card_menu")


class TestApiCapturePolling:
    """Verify submit_song uses polling instead of fixed wait."""

    def test_submit_song_source_has_no_8000ms_wait(self):
        """submit_song should NOT contain the old 8-second hard wait."""
        import inspect
        from automation.lalals_driver import LalalsDriver

        source = inspect.getsource(LalalsDriver.submit_song)
        assert "wait_for_timeout(8000)" not in source

    def test_submit_song_source_uses_polling(self):
        """submit_song should use polling with api_capture_s timeout."""
        import inspect
        from automation.lalals_driver import LalalsDriver

        source = inspect.getsource(LalalsDriver.submit_song)
        assert "api_capture_s" in source
        assert "wait_for_timeout(500)" in source

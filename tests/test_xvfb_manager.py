"""Tests for the Xvfb manager."""

import os
from unittest.mock import patch

from automation.xvfb_manager import XvfbManager


def test_find_free_display_first_available(tmp_path):
    """With no lock files, should return :99."""
    display = XvfbManager._find_free_display(99, 200)
    # Result depends on system state, but should be a valid display string
    assert display.startswith(":")
    num = int(display[1:])
    assert 99 <= num < 200


def test_default_display_is_none():
    mgr = XvfbManager()
    assert mgr.display is None


def test_explicit_display():
    mgr = XvfbManager(display=":42")
    assert mgr.display == ":42"


def test_xvfb_not_available_on_non_linux():
    """When supports_xvfb() returns False, is_available() should be False."""
    with patch("automation.xvfb_manager.supports_xvfb", return_value=False):
        assert XvfbManager.is_available() is False


def test_xvfb_start_skips_on_non_linux():
    """When supports_xvfb() returns False, start() should return empty string."""
    mgr = XvfbManager()
    with patch("automation.xvfb_manager.supports_xvfb", return_value=False):
        result = mgr.start()
        assert result == ""

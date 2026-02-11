"""Tests for the Xvfb manager."""

import os
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

"""Tests for platform_utils module."""

import sys
from unittest.mock import patch

from platform_utils import (
    is_linux, is_macos, is_windows,
    platform_name, is_frozen, get_bundle_dir, get_resource_dir,
    get_font_search_paths, supports_xvfb,
)


def test_exactly_one_platform_true():
    """Only one of is_linux/is_macos/is_windows should be True."""
    results = [is_linux(), is_macos(), is_windows()]
    assert sum(results) == 1, f"Expected exactly one True, got {results}"


def test_platform_name_returns_valid():
    """platform_name() should return a known string."""
    name = platform_name()
    assert name in ("linux", "macos", "windows"), f"Unexpected platform: {name}"


def test_is_frozen_false_in_tests():
    """When running under pytest, is_frozen() should be False."""
    assert is_frozen() is False


def test_is_frozen_true_when_mocked():
    """When sys.frozen is set, is_frozen() should return True."""
    with patch.object(sys, 'frozen', True, create=True):
        assert is_frozen() is True


def test_get_bundle_dir_returns_string():
    """get_bundle_dir() should return a non-empty string."""
    result = get_bundle_dir()
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_resource_dir_returns_string():
    """get_resource_dir() should return a non-empty string."""
    result = get_resource_dir()
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_resource_dir_frozen():
    """When frozen, get_resource_dir() should use sys._MEIPASS."""
    with patch.object(sys, 'frozen', True, create=True):
        with patch.object(sys, '_MEIPASS', '/fake/meipass', create=True):
            result = get_resource_dir()
            assert result == '/fake/meipass'


def test_get_font_search_paths_nonempty():
    """get_font_search_paths() should return a non-empty list."""
    paths = get_font_search_paths()
    assert isinstance(paths, list)
    assert len(paths) > 0


def test_supports_xvfb_matches_linux():
    """supports_xvfb() should be True only on Linux."""
    assert supports_xvfb() == is_linux()


def test_platform_name_matches_checks():
    """platform_name() should be consistent with the is_* functions."""
    name = platform_name()
    if name == "linux":
        assert is_linux() is True
    elif name == "macos":
        assert is_macos() is True
    elif name == "windows":
        assert is_windows() is True

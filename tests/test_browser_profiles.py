"""Tests for browser profile management."""

import os
import pytest
from automation.browser_profiles import (
    get_profile_path, clear_cache, clear_profile,
    clear_all_profiles, get_profile_size, list_profiles,
    PROFILES_DIR,
)


@pytest.fixture(autouse=True)
def use_tmp_profiles(tmp_path, monkeypatch):
    """Redirect PROFILES_DIR to a temp directory for all tests."""
    test_profiles = str(tmp_path / "profiles")
    monkeypatch.setattr("automation.browser_profiles.PROFILES_DIR", test_profiles)
    monkeypatch.setattr("automation.browser_profiles._LEGACY_PATHS", {})
    yield test_profiles


def test_get_profile_path_creates_dir(use_tmp_profiles):
    path = get_profile_path("lalals")
    assert os.path.isdir(path)
    assert path.endswith("lalals")


def test_get_profile_path_idempotent(use_tmp_profiles):
    p1 = get_profile_path("lalals")
    p2 = get_profile_path("lalals")
    assert p1 == p2


def test_clear_cache_no_cache(use_tmp_profiles):
    get_profile_path("test")
    assert clear_cache("test") is False


def test_clear_cache_with_cache(use_tmp_profiles):
    path = get_profile_path("test")
    cache_dir = os.path.join(path, "Default", "Cache")
    os.makedirs(cache_dir)
    with open(os.path.join(cache_dir, "data"), "w") as f:
        f.write("cached")
    assert clear_cache("test") is True
    assert not os.path.exists(cache_dir)


def test_clear_profile(use_tmp_profiles):
    get_profile_path("test")
    assert clear_profile("test") is True
    assert clear_profile("test") is False  # already gone


def test_clear_all_profiles(use_tmp_profiles):
    get_profile_path("a")
    get_profile_path("b")
    assert clear_all_profiles() is True
    assert clear_all_profiles() is False  # already gone


def test_get_profile_size(use_tmp_profiles):
    path = get_profile_path("test")
    with open(os.path.join(path, "file.txt"), "w") as f:
        f.write("x" * 100)
    size = get_profile_size("test")
    assert size >= 100


def test_list_profiles(use_tmp_profiles):
    get_profile_path("alpha")
    get_profile_path("beta")
    profiles = list_profiles()
    names = [p["service"] for p in profiles]
    assert "alpha" in names
    assert "beta" in names

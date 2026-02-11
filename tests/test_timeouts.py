"""Tests for the configuration-driven timeouts module."""

import pytest
from timeouts import TIMEOUTS, get_timeout


def test_all_timeout_keys_exist():
    expected_keys = {
        "login_wait_s", "dk_login_wait_s", "generation_poll_s",
        "element_visible_ms", "page_load_ms", "api_request_s",
        "ffmpeg_convert_s", "download_s", "xvfb_startup_s",
        "poll_interval_s", "search_debounce_ms",
    }
    assert expected_keys.issubset(set(TIMEOUTS.keys()))


def test_get_timeout_returns_defaults(temp_db):
    for key, value in TIMEOUTS.items():
        assert get_timeout(temp_db, key) == value


def test_get_timeout_with_db_override(temp_db):
    temp_db.set_config("timeout_login_wait_s", "120")
    assert get_timeout(temp_db, "login_wait_s") == 120


def test_get_timeout_with_none_db():
    assert get_timeout(None, "login_wait_s") == 300


def test_get_timeout_unknown_key(temp_db):
    with pytest.raises(KeyError):
        get_timeout(temp_db, "nonexistent_key")


def test_get_timeout_bad_override_falls_back(temp_db):
    temp_db.set_config("timeout_login_wait_s", "not_a_number")
    assert get_timeout(temp_db, "login_wait_s") == 300

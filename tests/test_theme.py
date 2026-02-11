"""Tests for the centralized Theme module."""

from theme import Theme


def test_core_colors_are_hex():
    for attr in ("BG", "PANEL", "TEXT", "ACCENT", "ERROR", "SUCCESS", "WARNING"):
        val = getattr(Theme, attr)
        assert val.startswith("#"), f"Theme.{attr} = {val!r} is not a hex color"
        assert len(val) == 7, f"Theme.{attr} = {val!r} is not #RRGGBB"


def test_status_colors_keys():
    expected = {"draft", "queued", "processing", "submitted", "completed", "error", "imported"}
    assert set(Theme.STATUS_COLORS.keys()) == expected


def test_dist_status_colors_keys():
    expected = {"draft", "ready", "uploading", "submitted", "live", "error"}
    assert set(Theme.DIST_STATUS_COLORS.keys()) == expected


def test_global_stylesheet_not_empty():
    ss = Theme.global_stylesheet()
    assert len(ss) > 100
    assert "QMainWindow" in ss
    assert Theme.ACCENT in ss


def test_accent_button_style():
    style = Theme.accent_button_style()
    assert "QPushButton" in style
    assert Theme.ACCENT in style


def test_secondary_button_style():
    style = Theme.secondary_button_style()
    assert "QPushButton" in style


def test_danger_button_style():
    style = Theme.danger_button_style()
    assert "QPushButton" in style
    assert Theme.ERROR in style


def test_panel_style():
    style = Theme.panel_style()
    assert "QWidget" in style
    assert Theme.PANEL in style

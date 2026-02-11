"""Tests for shared widgets."""

import pytest


def test_status_badge_creation(qt_app):
    from widgets.status_badge import StatusBadge
    badge = StatusBadge("completed")
    assert badge.text() == "Completed"


def test_status_badge_update(qt_app):
    from widgets.status_badge import StatusBadge
    badge = StatusBadge("draft")
    badge.set_status("error")
    assert badge.text() == "Error"


def test_status_badge_custom_color_map(qt_app):
    from widgets.status_badge import StatusBadge
    custom = {"ready": "#00FF00"}
    badge = StatusBadge("ready", color_map=custom)
    assert badge.text() == "Ready"


def test_search_bar_creation(qt_app):
    from widgets.search_bar import SearchBar
    bar = SearchBar("Search songs...")
    assert bar.placeholderText() == "Search songs..."


def test_search_bar_signal(qt_app):
    from widgets.search_bar import SearchBar
    bar = SearchBar(debounce_ms=10)
    received = []
    bar.search_changed.connect(lambda t: received.append(t))
    bar.setText("hello")
    # Signal is debounced — timer must fire
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(50, qt_app.quit)
    qt_app.exec()
    assert received == ["hello"]


def test_log_viewer_creation(qt_app):
    from widgets.log_viewer import LogViewer
    viewer = LogViewer()
    viewer.append_line("Test message")
    assert "Test message" in viewer.toPlainText()

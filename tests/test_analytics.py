"""Tests for the analytics tab."""

import pytest


def test_analytics_tab_creation(qt_app, temp_db):
    from tabs.analytics import AnalyticsTab
    tab = AnalyticsTab(temp_db)
    assert tab is not None


def test_analytics_refresh_empty(qt_app, temp_db):
    from tabs.analytics import AnalyticsTab
    tab = AnalyticsTab(temp_db)
    tab.refresh()
    assert tab.total_songs_card._value_label.text() == "0"


def test_analytics_refresh_with_data(qt_app, seeded_db):
    from tabs.analytics import AnalyticsTab
    tab = AnalyticsTab(seeded_db)
    tab.refresh()
    # Should show non-zero total
    total = int(tab.total_songs_card._value_label.text())
    assert total > 0


def test_stat_card_set_value(qt_app):
    from tabs.analytics import StatCard
    card = StatCard("Test", "0")
    card.set_value("42")
    assert card._value_label.text() == "42"


def test_bar_chart_set_data(qt_app):
    from tabs.analytics import BarChartWidget
    chart = BarChartWidget("Test Chart")
    chart.set_data([("A", 10, "#FF0000"), ("B", 5, "#00FF00")])
    assert len(chart._data) == 2

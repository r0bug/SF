"""Tests for selector health check module."""

from automation.selector_health import CheckResult, HealthReport, SelectorHealthChecker


def test_check_result_creation():
    r = CheckResult(name="test", url="http://x", selector="body", ok=True)
    assert r.ok is True
    assert r.error == ""


def test_health_report_counts():
    report = HealthReport(results=[
        CheckResult("a", "", "", True),
        CheckResult("b", "", "", False, "err"),
        CheckResult("c", "", "", True),
    ])
    assert report.passed == 2
    assert report.failed == 1
    assert report.total == 3


def test_health_report_summary():
    report = HealthReport(results=[
        CheckResult("check1", "", "", True),
        CheckResult("check2", "", "", False, "not found"),
    ])
    summary = report.summary()
    assert "1/2 passed" in summary
    assert "[PASS] check1" in summary
    assert "[FAIL] check2" in summary
    assert "not found" in summary


def test_health_report_empty():
    report = HealthReport()
    assert report.passed == 0
    assert report.total == 0
    assert "0/0" in report.summary()

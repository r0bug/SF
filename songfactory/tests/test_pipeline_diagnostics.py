"""Tests for the pipeline diagnostic tool.

Verifies:
- DiagnosticResult dataclass construction
- DiagnosticReport HTML rendering
- DiagnosticReport overall status aggregation
"""

import pytest

from automation.pipeline_diagnostics import DiagnosticResult, DiagnosticReport


class TestDiagnosticResult:
    """Test the DiagnosticResult dataclass."""

    def test_basic_construction(self):
        r = DiagnosticResult(phase="A", name="Browser Launch", status="pass")
        assert r.phase == "A"
        assert r.name == "Browser Launch"
        assert r.status == "pass"
        assert r.duration == 0.0
        assert r.error_category == ""
        assert r.screenshot_path == ""
        assert r.selectors_tried == []
        assert r.selector_matched == ""
        assert r.detail == ""

    def test_full_construction(self):
        r = DiagnosticResult(
            phase="B",
            name="Form Elements",
            status="warn",
            duration=2.5,
            error_category="selector_not_found",
            screenshot_path="/tmp/test.png",
            selectors_tried=["textarea", "input"],
            selector_matched="textarea",
            detail="Only prompt found",
        )
        assert r.phase == "B"
        assert r.duration == 2.5
        assert len(r.selectors_tried) == 2
        assert r.selector_matched == "textarea"

    def test_default_lists_are_independent(self):
        """Ensure default list fields don't share state between instances."""
        r1 = DiagnosticResult(phase="A", name="Test", status="pass")
        r2 = DiagnosticResult(phase="B", name="Test2", status="pass")
        r1.selectors_tried.append("foo")
        assert "foo" not in r2.selectors_tried


class TestDiagnosticReport:
    """Test the DiagnosticReport aggregation and rendering."""

    def _make_report(self, statuses: list[str]) -> DiagnosticReport:
        return DiagnosticReport(results=[
            DiagnosticResult(phase=chr(65 + i), name=f"Phase {chr(65 + i)}", status=s)
            for i, s in enumerate(statuses)
        ])

    def test_overall_status_all_pass(self):
        report = self._make_report(["pass", "pass", "pass"])
        assert report.overall_status == "pass"

    def test_overall_status_one_fail(self):
        report = self._make_report(["pass", "fail", "pass"])
        assert report.overall_status == "fail"

    def test_overall_status_warn_no_fail(self):
        report = self._make_report(["pass", "warn", "pass"])
        assert report.overall_status == "warn"

    def test_overall_status_fail_overrides_warn(self):
        report = self._make_report(["warn", "fail", "pass"])
        assert report.overall_status == "fail"

    def test_overall_status_empty(self):
        report = DiagnosticReport()
        assert report.overall_status == "skip"

    def test_overall_status_all_skip(self):
        report = self._make_report(["skip", "skip"])
        assert report.overall_status == "pass"  # no fail or warn

    def test_to_html_contains_phases(self):
        report = self._make_report(["pass", "fail", "warn"])
        html = report.to_html()
        assert "<html>" in html
        assert "Phase A" in html
        assert "Phase B" in html
        assert "Phase C" in html
        assert "PASS" in html
        assert "FAIL" in html
        assert "WARN" in html

    def test_to_html_includes_overall(self):
        report = self._make_report(["pass", "pass"])
        html = report.to_html()
        assert "Overall" in html
        assert "PASS" in html

    def test_to_html_shows_screenshots(self):
        report = DiagnosticReport(results=[
            DiagnosticResult(
                phase="A", name="Test", status="fail",
                screenshot_path="/tmp/screenshot.png",
            ),
        ])
        html = report.to_html()
        assert "/tmp/screenshot.png" in html
        assert "Screenshots" in html

    def test_to_html_no_screenshots_section_when_empty(self):
        report = self._make_report(["pass"])
        html = report.to_html()
        assert "Screenshots" not in html

    def test_to_html_shows_matched_selector(self):
        report = DiagnosticReport(results=[
            DiagnosticResult(
                phase="B", name="Selectors", status="pass",
                selector_matched="textarea",
            ),
        ])
        html = report.to_html()
        assert "textarea" in html

    def test_to_html_shows_detail(self):
        report = DiagnosticReport(results=[
            DiagnosticResult(
                phase="E", name="Downloads", status="warn",
                detail="audio_url_1: HTTP 404",
            ),
        ])
        html = report.to_html()
        assert "HTTP 404" in html

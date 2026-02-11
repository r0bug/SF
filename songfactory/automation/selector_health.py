"""Selector health check for browser automation targets.

Provides a lightweight way to verify that the CSS selectors used by
lalals_driver.py and distrokid_driver.py still resolve on the target
websites.  Can be run from Settings > Diagnostics without requiring
login credentials.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("songfactory.automation.selector_health")


@dataclass
class CheckResult:
    """Result of a single selector health check."""
    name: str
    url: str
    selector: str
    ok: bool
    error: str = ""


@dataclass
class HealthReport:
    """Aggregated results from a health check run."""
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.ok)

    @property
    def total(self) -> int:
        return len(self.results)

    def summary(self) -> str:
        lines = [f"Selector Health Check: {self.passed}/{self.total} passed"]
        for r in self.results:
            status = "PASS" if r.ok else "FAIL"
            lines.append(f"  [{status}] {r.name}")
            if r.error:
                lines.append(f"         Error: {r.error}")
        return "\n".join(lines)


# Selectors to check — these match what lalals_driver.py actually uses.
# Public page checks (no login required)
LALALS_CHECKS = [
    ("Lalals homepage loads", "https://lalals.com", "body"),
    ("Music page accessible", "https://lalals.com/music", "body"),
    # Prompt textarea (public page may redirect to auth, but selector is still checkable)
    ("Prompt textarea (title)", "https://lalals.com/music", 'textarea[title*="Describe"]'),
    ("Prompt textarea (maxlength)", "https://lalals.com/music", 'textarea[maxlength="500"]'),
    ("Prompt textarea (placeholder)", "https://lalals.com/music", 'textarea[placeholder*="escribe"]'),
    ("Prompt textarea (generic)", "https://lalals.com/music", "textarea"),
    # Lyrics toggle button
    ("Lyrics toggle button", "https://lalals.com/music", '[data-name="LyricsButton"] button'),
    # Generate button
    ("Generate button (submit)", "https://lalals.com/music", "button[type='submit']"),
    ("Generate button (text)", "https://lalals.com/music", "button:has-text('Generate')"),
    # Home page card selectors
    ("Home page cards", "https://lalals.com", "[data-testid]"),
]

DISTROKID_CHECKS = [
    ("DistroKid homepage loads", "https://distrokid.com", "body"),
]

ALL_CHECKS = LALALS_CHECKS + DISTROKID_CHECKS


class SelectorHealthChecker:
    """Runs selector health checks against target websites.

    Usage::

        checker = SelectorHealthChecker()
        report = checker.run_checks()  # requires Playwright
        print(report.summary())
    """

    def __init__(self, timeout_ms: int = 15000):
        self.timeout_ms = timeout_ms

    def run_checks(self, checks: list[tuple] | None = None) -> HealthReport:
        """Run all checks using Playwright.

        Args:
            checks: Optional list of (name, url, selector) tuples.
                    Defaults to ALL_CHECKS.

        Returns:
            HealthReport with individual check results.
        """
        if checks is None:
            checks = ALL_CHECKS

        report = HealthReport()

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            report.results.append(CheckResult(
                name="Playwright import",
                url="",
                selector="",
                ok=False,
                error="Playwright is not installed",
            ))
            return report

        pw = None
        browser = None
        try:
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            for name, url, selector in checks:
                result = self._check_one(page, name, url, selector)
                report.results.append(result)
                logger.info(
                    "Health check [%s] %s: %s",
                    "PASS" if result.ok else "FAIL",
                    name,
                    result.error or "OK",
                )

        except Exception as e:
            report.results.append(CheckResult(
                name="Browser launch",
                url="",
                selector="",
                ok=False,
                error=str(e),
            ))
        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass
            if pw:
                try:
                    pw.stop()
                except Exception:
                    pass

        return report

    def _check_one(self, page, name: str, url: str, selector: str) -> CheckResult:
        """Navigate to *url* and check if *selector* resolves."""
        try:
            page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")
            element = page.query_selector(selector)
            return CheckResult(
                name=name,
                url=url,
                selector=selector,
                ok=element is not None,
                error="" if element else f"Selector '{selector}' not found",
            )
        except Exception as e:
            return CheckResult(
                name=name,
                url=url,
                selector=selector,
                ok=False,
                error=str(e),
            )

"""Pipeline diagnostic tool for Song Factory browser automation.

Tests each phase of the lalals.com integration independently:
  A. Browser launch + login check
  B. Form element selectors
  C. Form fill test (non-destructive)
  D. API submission (opt-in, consumes 1 credit)
  E. Download URL validation

Usage from Settings tab or standalone::

    worker = PipelineDiagnosticWorker(db_path, test_api=False)
    worker.phase_completed.connect(on_phase)
    worker.diagnostic_finished.connect(on_done)
    worker.start()
"""

import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger("songfactory.automation.diagnostics")

SCREENSHOT_DIR = Path.home() / ".songfactory" / "screenshots"


@dataclass
class DiagnosticResult:
    """Result of a single diagnostic phase."""
    phase: str
    name: str
    status: str  # "pass", "fail", "skip", "warn"
    duration: float = 0.0
    error_category: str = ""
    screenshot_path: str = ""
    selectors_tried: list[str] = field(default_factory=list)
    selector_matched: str = ""
    detail: str = ""


@dataclass
class DiagnosticReport:
    """Aggregated results from a full diagnostic run."""
    results: list[DiagnosticResult] = field(default_factory=list)

    @property
    def overall_status(self) -> str:
        """Return 'pass' if all passed, 'fail' if any failed, 'warn' otherwise."""
        statuses = {r.status for r in self.results}
        if "fail" in statuses:
            return "fail"
        if "warn" in statuses:
            return "warn"
        if not self.results:
            return "skip"
        return "pass"

    def to_html(self) -> str:
        """Render the report as an HTML string for display."""
        lines = [
            "<html><body style='font-family: monospace; background: #1e1e1e; color: #e0e0e0;'>",
            "<h2>Pipeline Diagnostic Report</h2>",
            f"<p>Overall: <b>{self.overall_status.upper()}</b></p>",
            "<table border='1' cellpadding='6' cellspacing='0' style='border-color: #555;'>",
            "<tr><th>Phase</th><th>Name</th><th>Status</th><th>Duration</th><th>Detail</th></tr>",
        ]
        status_colors = {
            "pass": "#4CAF50",
            "fail": "#f44336",
            "warn": "#FF9800",
            "skip": "#888888",
        }
        for r in self.results:
            color = status_colors.get(r.status, "#e0e0e0")
            detail = r.detail or r.error_category or ""
            if r.selector_matched:
                detail += f" (matched: {r.selector_matched})"
            lines.append(
                f"<tr>"
                f"<td>{r.phase}</td>"
                f"<td>{r.name}</td>"
                f"<td style='color: {color}; font-weight: bold;'>{r.status.upper()}</td>"
                f"<td>{r.duration:.1f}s</td>"
                f"<td>{detail}</td>"
                f"</tr>"
            )
        lines.append("</table>")

        # List screenshots
        screenshots = [r.screenshot_path for r in self.results if r.screenshot_path]
        if screenshots:
            lines.append("<h3>Screenshots</h3><ul>")
            for s in screenshots:
                lines.append(f"<li>{s}</li>")
            lines.append("</ul>")

        lines.append("</body></html>")
        return "\n".join(lines)


class PipelineDiagnosticWorker(QThread):
    """Runs diagnostic phases in a background thread."""

    phase_started = pyqtSignal(str, str)          # phase_id, phase_name
    phase_completed = pyqtSignal(DiagnosticResult)
    diagnostic_finished = pyqtSignal(DiagnosticReport)

    def __init__(self, db_path: str, test_api: bool = False, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.test_api = test_api
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        report = DiagnosticReport()
        page = None
        context = None
        playwright_inst = None

        try:
            # Phase A: Browser Launch + Login
            result_a, page, context, playwright_inst = self._phase_a()
            report.results.append(result_a)
            self.phase_completed.emit(result_a)

            if result_a.status == "fail" or self._stop_flag:
                self.diagnostic_finished.emit(report)
                return

            # Phase B: Form Elements
            result_b = self._phase_b(page)
            report.results.append(result_b)
            self.phase_completed.emit(result_b)

            if self._stop_flag:
                self.diagnostic_finished.emit(report)
                return

            # Phase C: Form Fill Test
            result_c = self._phase_c(page)
            report.results.append(result_c)
            self.phase_completed.emit(result_c)

            if self._stop_flag:
                self.diagnostic_finished.emit(report)
                return

            # Phase D: API Submission (opt-in)
            if self.test_api:
                result_d = self._phase_d(page, context)
                report.results.append(result_d)
                self.phase_completed.emit(result_d)
            else:
                skip = DiagnosticResult(
                    phase="D", name="API Submission", status="skip",
                    detail="Skipped (opt-in, uses 1 credit)",
                )
                report.results.append(skip)
                self.phase_completed.emit(skip)

            if self._stop_flag:
                self.diagnostic_finished.emit(report)
                return

            # Phase E: Download URLs
            result_e = self._phase_e()
            report.results.append(result_e)
            self.phase_completed.emit(result_e)

        except Exception as e:
            logger.error(f"Diagnostic worker error: {e}")
            report.results.append(DiagnosticResult(
                phase="X", name="Unexpected Error", status="fail",
                detail=str(e),
            ))
        finally:
            try:
                if context:
                    context.close()
                if playwright_inst:
                    playwright_inst.stop()
            except Exception:
                pass
            self.diagnostic_finished.emit(report)

    def _capture_screenshot(self, page, name: str) -> str:
        """Capture a screenshot for diagnostic purposes."""
        try:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = SCREENSHOT_DIR / f"{ts}_diag_{name}.png"
            page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception as e:
            logger.warning(f"Screenshot failed: {e}")
            return ""

    def _phase_a(self):
        """Phase A: Browser Launch + Login Check."""
        self.phase_started.emit("A", "Browser Launch + Login")
        start = time.time()

        try:
            from playwright.sync_api import sync_playwright
            from automation.browser_profiles import get_profile_path

            playwright_inst = sync_playwright().start()
            profile_dir = get_profile_path("lalals")

            launch_args = {
                "headless": True,
                "accept_downloads": True,
                "viewport": {"width": 1280, "height": 900},
                "args": ["--disable-blink-features=AutomationControlled"],
            }

            try:
                context = playwright_inst.chromium.launch_persistent_context(
                    profile_dir, channel="chrome", **launch_args
                )
            except Exception:
                context = playwright_inst.chromium.launch_persistent_context(
                    profile_dir, **launch_args
                )

            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://lalals.com/music", wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            screenshot = self._capture_screenshot(page, "phase_a")
            logged_in = "/auth/" not in page.url
            duration = time.time() - start

            if logged_in:
                return DiagnosticResult(
                    phase="A", name="Browser Launch + Login",
                    status="pass", duration=duration,
                    screenshot_path=screenshot,
                    detail=f"Logged in, URL: {page.url}",
                ), page, context, playwright_inst
            else:
                return DiagnosticResult(
                    phase="A", name="Browser Launch + Login",
                    status="warn", duration=duration,
                    error_category="session_expired",
                    screenshot_path=screenshot,
                    detail=f"Not logged in (redirected to {page.url})",
                ), page, context, playwright_inst

        except Exception as e:
            return DiagnosticResult(
                phase="A", name="Browser Launch + Login",
                status="fail", duration=time.time() - start,
                error_category="network_error",
                detail=str(e),
            ), None, None, None

    def _phase_b(self, page):
        """Phase B: Form Element Selectors."""
        self.phase_started.emit("B", "Form Elements")
        start = time.time()

        if "/auth/" in page.url:
            return DiagnosticResult(
                phase="B", name="Form Elements", status="skip",
                duration=time.time() - start,
                detail="Skipped (not logged in)",
            )

        results = []

        # Test prompt textarea selectors
        prompt_selectors = [
            'textarea[title*="Describe"]',
            'textarea[maxlength="500"]',
            'textarea[placeholder*="escribe"]',
            'textarea[placeholder*="song"]',
            "textarea",
        ]
        prompt_matched = ""
        for sel in prompt_selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=3000):
                    prompt_matched = sel
                    break
            except Exception:
                continue

        # Test lyrics button selectors
        lyrics_selectors = [
            '[data-name="LyricsButton"] button',
            'button[aria-label="Lyrics"]',
        ]
        lyrics_matched = ""
        for sel in lyrics_selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=3000):
                    lyrics_matched = sel
                    break
            except Exception:
                continue

        # Test generate button selectors
        generate_selectors = [
            "button[type='submit']",
            "button:has-text('Generate')",
            "button:has-text('Create')",
            "button:has-text('Submit')",
        ]
        generate_matched = ""
        for sel in generate_selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=3000):
                    generate_matched = sel
                    break
            except Exception:
                continue

        screenshot = self._capture_screenshot(page, "phase_b")
        duration = time.time() - start

        all_tried = prompt_selectors + lyrics_selectors + generate_selectors
        matched = []
        if prompt_matched:
            matched.append(f"prompt={prompt_matched}")
        if lyrics_matched:
            matched.append(f"lyrics={lyrics_matched}")
        if generate_matched:
            matched.append(f"generate={generate_matched}")

        # Determine status
        if prompt_matched and generate_matched:
            status = "pass"
        elif prompt_matched or generate_matched:
            status = "warn"
        else:
            status = "fail"

        return DiagnosticResult(
            phase="B", name="Form Elements",
            status=status, duration=duration,
            selectors_tried=all_tried,
            selector_matched=", ".join(matched) if matched else "none",
            screenshot_path=screenshot,
            detail=f"Found: {', '.join(matched)}" if matched else "No selectors matched",
            error_category="selector_not_found" if status == "fail" else "",
        )

    def _phase_c(self, page):
        """Phase C: Form Fill Test (non-destructive)."""
        self.phase_started.emit("C", "Form Fill Test")
        start = time.time()

        if "/auth/" in page.url:
            return DiagnosticResult(
                phase="C", name="Form Fill Test", status="skip",
                duration=time.time() - start,
                detail="Skipped (not logged in)",
            )

        test_text = "DIAGNOSTIC TEST — ignore this text"
        try:
            # Find prompt textarea
            textarea = None
            for sel in ['textarea[maxlength="500"]', 'textarea[placeholder*="escribe"]', 'textarea']:
                try:
                    loc = page.locator(sel).first
                    if loc.is_visible(timeout=3000):
                        textarea = loc
                        break
                except Exception:
                    continue

            if not textarea:
                return DiagnosticResult(
                    phase="C", name="Form Fill Test", status="fail",
                    duration=time.time() - start,
                    detail="Could not find prompt textarea",
                    error_category="selector_not_found",
                )

            # Fill, read back, then clear
            textarea.click()
            textarea.fill(test_text)
            page.wait_for_timeout(500)
            value = textarea.input_value()
            textarea.fill("")  # Clear

            screenshot = self._capture_screenshot(page, "phase_c")
            duration = time.time() - start

            if test_text in value:
                return DiagnosticResult(
                    phase="C", name="Form Fill Test",
                    status="pass", duration=duration,
                    screenshot_path=screenshot,
                    detail="Fill + readback verified, field cleared",
                )
            else:
                return DiagnosticResult(
                    phase="C", name="Form Fill Test",
                    status="warn", duration=duration,
                    screenshot_path=screenshot,
                    detail=f"Readback mismatch: got '{value[:50]}'",
                )
        except Exception as e:
            return DiagnosticResult(
                phase="C", name="Form Fill Test",
                status="fail", duration=time.time() - start,
                detail=str(e),
            )

    def _phase_d(self, page, context):
        """Phase D: API Submission (opt-in, consumes 1 credit)."""
        self.phase_started.emit("D", "API Submission")
        start = time.time()

        if "/auth/" in page.url:
            return DiagnosticResult(
                phase="D", name="API Submission", status="skip",
                duration=time.time() - start,
                detail="Skipped (not logged in)",
            )

        try:
            from automation.lalals_driver import LalalsDriver

            driver = LalalsDriver(page, context)
            task_id, task_data = driver.submit_song(
                prompt="Diagnostic test song — please ignore",
                lyrics="This is a diagnostic test.\nPlease disregard.",
            )
            screenshot = self._capture_screenshot(page, "phase_d")
            duration = time.time() - start

            if task_id:
                return DiagnosticResult(
                    phase="D", name="API Submission",
                    status="pass", duration=duration,
                    screenshot_path=screenshot,
                    detail=f"task_id={task_id}",
                )
            else:
                return DiagnosticResult(
                    phase="D", name="API Submission",
                    status="fail", duration=duration,
                    screenshot_path=screenshot,
                    error_category="api_timeout",
                    detail="task_id not captured",
                )
        except Exception as e:
            return DiagnosticResult(
                phase="D", name="API Submission",
                status="fail", duration=time.time() - start,
                detail=str(e),
            )

    def _phase_e(self):
        """Phase E: Download URL Validation."""
        self.phase_started.emit("E", "Download URLs")
        start = time.time()

        try:
            import sqlite3
            import urllib.request
            import urllib.error

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT task_id, conversion_id_1, conversion_id_2, "
                "audio_url_1, audio_url_2 FROM songs "
                "WHERE task_id IS NOT NULL AND task_id != '' "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            conn.close()

            if not row:
                return DiagnosticResult(
                    phase="E", name="Download URLs", status="skip",
                    duration=time.time() - start,
                    detail="No songs with task_id in database",
                )

            detail_parts = []
            urls_ok = 0
            urls_checked = 0

            for key in ("audio_url_1", "audio_url_2"):
                url = row[key]
                if not url:
                    # Build from conversion ID
                    cid_key = key.replace("audio_url", "conversion_id")
                    cid = row[cid_key]
                    if cid:
                        url = f"https://lalals.s3.amazonaws.com/conversions/standard/{cid}/{cid}.mp3"

                if url:
                    urls_checked += 1
                    try:
                        req = urllib.request.Request(url, method="HEAD")
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            if resp.status == 200:
                                urls_ok += 1
                                detail_parts.append(f"{key}: OK")
                            else:
                                detail_parts.append(f"{key}: HTTP {resp.status}")
                    except urllib.error.HTTPError as e:
                        detail_parts.append(f"{key}: HTTP {e.code}")
                    except Exception as e:
                        detail_parts.append(f"{key}: {e}")

            # Check download dir writable
            download_dir = Path.home() / "Music" / "SongFactory"
            try:
                download_dir.mkdir(parents=True, exist_ok=True)
                test_file = download_dir / ".diag_write_test"
                test_file.write_text("test")
                test_file.unlink()
                detail_parts.append("download_dir: writable")
            except Exception as e:
                detail_parts.append(f"download_dir: {e}")

            duration = time.time() - start
            status = "pass" if urls_ok == urls_checked and urls_checked > 0 else (
                "warn" if urls_ok > 0 else "fail"
            )

            return DiagnosticResult(
                phase="E", name="Download URLs",
                status=status, duration=duration,
                detail="; ".join(detail_parts),
                error_category="download_failed" if status == "fail" else "",
            )

        except Exception as e:
            return DiagnosticResult(
                phase="E", name="Download URLs",
                status="fail", duration=time.time() - start,
                detail=str(e),
            )

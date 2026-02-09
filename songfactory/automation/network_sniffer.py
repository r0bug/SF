"""Network sniffer for lalals.com — logs all traffic, DOM mutations, and API responses.

Standalone script + importable module. Captures everything that happens on
lalals.com during song generation so we can tune selectors and interception logic.

Usage:
    python3 -m automation.network_sniffer --duration 300
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path

LOG_DIR = Path.home() / ".songfactory"
LOG_FILE = LOG_DIR / "network_sniffer.log"
PROFILE_DIR = LOG_DIR / "browser_profile"

logger = logging.getLogger("songfactory.sniffer")


class NetworkSniffer:
    """Captures network traffic, console output, and DOM mutations on lalals.com."""

    def __init__(self, log_path: str = None, profile_dir: str = None):
        self.log_path = Path(log_path) if log_path else LOG_FILE
        self.profile_dir = str(profile_dir) if profile_dir else str(PROFILE_DIR)
        self._log_file = None
        self._page = None
        self._context = None
        self._playwright = None
        self._running = False

    def _write_log(self, category: str, message: str):
        """Write a timestamped log entry."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        line = f"[{ts}] [{category}] {message}\n"
        if self._log_file:
            self._log_file.write(line)
            self._log_file.flush()
        logger.info(f"[{category}] {message[:200]}")

    def _on_request(self, request):
        """Log outgoing requests."""
        url = request.url
        method = request.method
        # Highlight musicgpt/lalals API calls
        highlight = ""
        if "musicgpt.com" in url or "lalals.com/api" in url:
            highlight = " *** API CALL ***"
        self._write_log("REQUEST", f"{method} {url}{highlight}")

        # Log POST body for API calls
        if highlight and method == "POST":
            try:
                body = request.post_data
                if body:
                    self._write_log("REQUEST_BODY", body[:2000])
            except Exception:
                pass

    def _on_response(self, response):
        """Log incoming responses, with special attention to API status fields."""
        url = response.url
        status = response.status
        highlight = ""

        if "musicgpt.com" in url or "lalals.com/api" in url or "byId" in url:
            highlight = " *** API RESPONSE ***"
            # Try to parse the body for status info
            try:
                body = response.json()
                body_str = json.dumps(body, indent=2)[:3000]
                self._write_log(
                    "API_RESPONSE_BODY",
                    f"URL={url}\n{body_str}",
                )
                # Extract status fields
                data_status = None
                if isinstance(body, dict):
                    data_status = body.get("status") or (
                        body.get("data", {}).get("status")
                        if isinstance(body.get("data"), dict)
                        else None
                    )
                if data_status:
                    self._write_log(
                        "STATUS_DETECTED",
                        f"status={data_status} url={url}",
                    )
            except Exception:
                pass

        self._write_log("RESPONSE", f"{status} {url}{highlight}")

    def _on_console(self, msg):
        """Log browser console messages."""
        text = msg.text
        # Highlight DOM mutation logs from our injected observer
        if text.startswith("[DOM_MUTATION]"):
            self._write_log("DOM_MUTATION", text)
        else:
            self._write_log("CONSOLE", f"[{msg.type}] {text[:500]}")

    def _inject_mutation_observer(self):
        """Inject a MutationObserver that logs DOM changes to console."""
        js = """
        (() => {
            if (window.__sfSnifferObserver) return;
            const observer = new MutationObserver((mutations) => {
                for (const m of mutations) {
                    if (m.type === 'childList') {
                        for (const node of m.addedNodes) {
                            if (node.nodeType === 1) {
                                const tag = node.tagName.toLowerCase();
                                const cls = node.className || '';
                                const id = node.id || '';
                                const text = (node.textContent || '').slice(0, 100);
                                console.log(`[DOM_MUTATION] ADDED <${tag}> id="${id}" class="${cls}" text="${text}"`);
                            }
                        }
                        for (const node of m.removedNodes) {
                            if (node.nodeType === 1) {
                                const tag = node.tagName.toLowerCase();
                                console.log(`[DOM_MUTATION] REMOVED <${tag}> id="${node.id || ''}" class="${node.className || ''}"`);
                            }
                        }
                    } else if (m.type === 'attributes') {
                        const el = m.target;
                        if (el.nodeType === 1) {
                            console.log(`[DOM_MUTATION] ATTR ${m.attributeName} changed on <${el.tagName.toLowerCase()}> id="${el.id || ''}" class="${el.className || ''}"`);
                        }
                    }
                }
            });
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['class', 'style', 'disabled', 'data-state', 'aria-expanded']
            });
            window.__sfSnifferObserver = observer;
            console.log('[DOM_MUTATION] Observer installed');
        })();
        """
        try:
            self._page.evaluate(js)
            self._write_log("SNIFFER", "MutationObserver injected")
        except Exception as e:
            self._write_log("SNIFFER", f"Failed to inject MutationObserver: {e}")

    def start(self, duration_s: int = 300, url: str = "https://lalals.com/music"):
        """Open browser, navigate to URL, and capture traffic for duration_s seconds.

        Args:
            duration_s: How long to sniff in seconds.
            url: Starting URL.
        """
        from playwright.sync_api import sync_playwright

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file = open(self.log_path, "a", encoding="utf-8")
        self._write_log("SNIFFER", f"=== Session started (duration={duration_s}s) ===")
        self._write_log("SNIFFER", f"Target URL: {url}")

        self._running = True

        try:
            self._playwright = sync_playwright().start()

            launch_args = {
                "headless": False,
                "accept_downloads": True,
                "viewport": {"width": 1280, "height": 900},
                "args": ["--disable-blink-features=AutomationControlled"],
            }

            try:
                self._context = self._playwright.chromium.launch_persistent_context(
                    self.profile_dir, channel="chrome", **launch_args
                )
            except Exception:
                self._context = self._playwright.chromium.launch_persistent_context(
                    self.profile_dir, **launch_args
                )

            self._page = (
                self._context.pages[0]
                if self._context.pages
                else self._context.new_page()
            )

            # Register listeners
            self._page.on("request", self._on_request)
            self._page.on("response", self._on_response)
            self._page.on("console", self._on_console)

            # Navigate
            self._write_log("SNIFFER", f"Navigating to {url}")
            self._page.goto(url, wait_until="domcontentloaded")
            self._page.wait_for_load_state("networkidle", timeout=15000)
            self._write_log("SNIFFER", f"Page loaded: {self._page.url}")

            # Inject mutation observer
            self._inject_mutation_observer()

            # Re-inject observer on navigation
            self._page.on(
                "load",
                lambda: self._inject_mutation_observer(),
            )

            # Wait for specified duration
            self._write_log("SNIFFER", f"Sniffing for {duration_s}s — interact with the page as needed")
            start = time.time()
            while time.time() - start < duration_s and self._running:
                self._page.wait_for_timeout(1000)

            self._write_log("SNIFFER", "=== Session ended ===")

        except Exception as e:
            self._write_log("SNIFFER", f"Error: {e}")
            raise
        finally:
            self.stop()

    def stop(self):
        """Stop the sniffer and close everything."""
        self._running = False
        try:
            if self._context:
                self._context.close()
                self._context = None
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
        except Exception:
            pass
        if self._log_file:
            self._log_file.close()
            self._log_file = None


def main():
    parser = argparse.ArgumentParser(description="Lalals.com network sniffer")
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Sniff duration in seconds (default: 300)",
    )
    parser.add_argument(
        "--url",
        default="https://lalals.com/music",
        help="Starting URL",
    )
    parser.add_argument(
        "--log",
        default=None,
        help="Log file path (default: ~/.songfactory/network_sniffer.log)",
    )
    args = parser.parse_args()

    sniffer = NetworkSniffer(log_path=args.log)
    try:
        sniffer.start(duration_s=args.duration, url=args.url)
    except KeyboardInterrupt:
        print("\nSniffer stopped by user")
        sniffer.stop()

    print(f"\nLog saved to: {sniffer.log_path}")


if __name__ == "__main__":
    main()

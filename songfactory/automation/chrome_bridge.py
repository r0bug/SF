"""Claude Chrome Bridge — file-based protocol for Claude Code ↔ Claude Chrome extension.

Provides a simple file-based protocol at ~/.songfactory/chrome_bridge/ for
coordinating exploration tasks between Claude Code and the Claude Chrome extension.

Usage:
    from automation.chrome_bridge import ChromeBridge

    bridge = ChromeBridge()
    req_id = bridge.send_request(
        url="https://lalals.com/music",
        prompt="After generation completes, identify: 1) What DOM elements change..."
    )
    # User opens Chrome, gives the prompt to Claude Chrome, pastes response
    response = bridge.poll_response(req_id, timeout_s=600)
"""

import json
import time
from datetime import datetime
from pathlib import Path

BRIDGE_DIR = Path.home() / ".songfactory" / "chrome_bridge"
REQUESTS_DIR = BRIDGE_DIR / "requests"
RESPONSES_DIR = BRIDGE_DIR / "responses"


class ChromeBridge:
    """File-based protocol for Claude Code ↔ Claude Chrome extension communication."""

    def __init__(self, bridge_dir: str = None):
        base = Path(bridge_dir) if bridge_dir else BRIDGE_DIR
        self.requests_dir = base / "requests"
        self.responses_dir = base / "responses"
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)

    def _next_id(self) -> str:
        """Generate the next sequential request ID (zero-padded 3-digit)."""
        existing = sorted(self.requests_dir.glob("*_*.json"))
        if not existing:
            return "001"
        # Parse the highest ID from existing filenames
        max_id = 0
        for f in existing:
            try:
                num = int(f.stem.split("_")[0])
                max_id = max(max_id, num)
            except (ValueError, IndexError):
                pass
        return f"{max_id + 1:03d}"

    def send_request(self, url: str, prompt: str) -> str:
        """Create a new exploration request for the Chrome extension user.

        Args:
            url: The URL to explore.
            prompt: The exploration prompt/question for Claude Chrome.

        Returns:
            The request ID (e.g. "001").
        """
        req_id = self._next_id()
        request_data = {
            "id": req_id,
            "url": url,
            "prompt": prompt,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }

        request_file = self.requests_dir / f"{req_id}_pending.json"
        request_file.write_text(json.dumps(request_data, indent=2), encoding="utf-8")
        return req_id

    def poll_response(self, req_id: str, timeout_s: int = 600, poll_interval: float = 5.0) -> dict | None:
        """Poll for a response to a given request ID.

        Checks for a file named {req_id}_complete.json in the responses directory.

        Args:
            req_id: The request ID to wait for.
            timeout_s: Maximum time to wait in seconds.
            poll_interval: Seconds between checks.

        Returns:
            The response dict, or None if timeout.
        """
        response_file = self.responses_dir / f"{req_id}_complete.json"
        start = time.time()

        while time.time() - start < timeout_s:
            if response_file.exists():
                try:
                    data = json.loads(response_file.read_text(encoding="utf-8"))
                    # Mark the request as completed
                    self._mark_request_completed(req_id)
                    return data
                except (json.JSONDecodeError, OSError):
                    pass
            time.sleep(poll_interval)

        return None

    def get_pending_requests(self) -> list[dict]:
        """Return all pending request files as dicts."""
        pending = []
        for f in sorted(self.requests_dir.glob("*_pending.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                pending.append(data)
            except (json.JSONDecodeError, OSError):
                pass
        return pending

    def write_response(self, req_id: str, response_text: str, metadata: dict = None):
        """Write a response for a given request ID.

        This is typically called by a helper script or manually by the user
        after getting Chrome extension output.

        Args:
            req_id: The request ID being responded to.
            response_text: The Chrome extension's findings.
            metadata: Optional extra metadata.
        """
        response_data = {
            "id": req_id,
            "response": response_text,
            "status": "complete",
            "responded_at": datetime.now().isoformat(),
        }
        if metadata:
            response_data["metadata"] = metadata

        response_file = self.responses_dir / f"{req_id}_complete.json"
        response_file.write_text(
            json.dumps(response_data, indent=2), encoding="utf-8"
        )

    def _mark_request_completed(self, req_id: str):
        """Rename the pending request file to indicate completion."""
        pending_file = self.requests_dir / f"{req_id}_pending.json"
        complete_file = self.requests_dir / f"{req_id}_complete.json"
        if pending_file.exists():
            try:
                data = json.loads(pending_file.read_text(encoding="utf-8"))
                data["status"] = "complete"
                complete_file.write_text(
                    json.dumps(data, indent=2), encoding="utf-8"
                )
                pending_file.unlink()
            except (json.JSONDecodeError, OSError):
                pass

    def cleanup(self, max_age_days: int = 7):
        """Remove request/response files older than max_age_days.

        Args:
            max_age_days: Files older than this are deleted.
        """
        import os

        cutoff = time.time() - (max_age_days * 86400)
        for directory in (self.requests_dir, self.responses_dir):
            for f in directory.glob("*.json"):
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                except OSError:
                    pass

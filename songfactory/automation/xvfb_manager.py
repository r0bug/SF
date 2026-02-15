"""Xvfb virtual display manager for headless browser automation.

Starts and manages an Xvfb process so that Playwright can run with
a real display (needed for persistent context / Google Auth) without
showing a visible browser window on the user's desktop.

Usage:
    from automation.xvfb_manager import XvfbManager

    xvfb = XvfbManager()
    display = xvfb.start()   # e.g. ":99"
    # ... launch browser, do work ...
    xvfb.stop()
"""

import os
import logging
import shutil
import subprocess

from platform_utils import supports_xvfb

logger = logging.getLogger("songfactory.automation")


class XvfbManager:
    """Manages an Xvfb virtual display subprocess."""

    def __init__(self, display: str | None = None, resolution: str = "1920x1080x24"):
        """
        Args:
            display: X display number (e.g. ":99").  If None, an available
                     display is auto-detected in start().
            resolution: Screen resolution as WxHxD string.
        """
        self.display = display
        self.resolution = resolution
        self._process = None

    @staticmethod
    def _find_free_display(start: int = 99, end: int = 200) -> str:
        """Find an unused X display number by checking lock files.

        Scans /tmp/.X{N}-lock for display numbers from *start* to *end*.

        Returns:
            Display string like ":99".

        Raises:
            RuntimeError: If no free display is found in the range.
        """
        for num in range(start, end):
            lock_file = f"/tmp/.X{num}-lock"
            if not os.path.exists(lock_file):
                return f":{num}"
        raise RuntimeError(
            f"No free X display found in range :{start}-:{end - 1}"
        )

    def start(self) -> str:
        """Start Xvfb subprocess and set the DISPLAY environment variable.

        Returns:
            The display string (e.g. ":99"), or empty string if not applicable.

        Raises:
            RuntimeError: If Xvfb is not available or fails to start.
        """
        if not supports_xvfb():
            logger.info("Xvfb not applicable on this platform, skipping")
            return ""

        if not self.is_available():
            raise RuntimeError("Xvfb is not installed or not on PATH")

        if self._process and self._process.poll() is None:
            logger.info(f"Xvfb already running on {self.display}")
            return self.display

        # Auto-detect display if not specified
        if self.display is None:
            self.display = self._find_free_display()
            logger.info(f"Auto-detected free display: {self.display}")

        cmd = [
            "Xvfb",
            self.display,
            "-screen", "0", self.resolution,
            "-ac",       # disable access control
            "+extension", "GLX",
        ]

        logger.info(f"Starting Xvfb: {' '.join(cmd)}")
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Give it a moment to start
        try:
            self._process.wait(timeout=0.5)
            # If it exited already, it failed
            raise RuntimeError(
                f"Xvfb exited immediately with code {self._process.returncode}"
            )
        except subprocess.TimeoutExpired:
            pass  # Still running = good

        os.environ["DISPLAY"] = self.display
        logger.info(f"Xvfb started on {self.display}, DISPLAY env set")
        return self.display

    def stop(self):
        """Kill the Xvfb subprocess."""
        if self._process and self._process.poll() is None:
            logger.info("Stopping Xvfb")
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

    def is_running(self) -> bool:
        """Check if the Xvfb process is still alive."""
        return self._process is not None and self._process.poll() is None

    @staticmethod
    def is_available() -> bool:
        """Check if Xvfb is installed on the system."""
        if not supports_xvfb():
            return False
        return shutil.which("Xvfb") is not None

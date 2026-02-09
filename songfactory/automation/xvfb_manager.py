"""Xvfb virtual display manager for headless browser automation.

Starts and manages an Xvfb process so that Playwright can run with
a real display (needed for persistent context / Google Auth) without
showing a visible browser window on the user's desktop.

Usage:
    from automation.xvfb_manager import XvfbManager

    xvfb = XvfbManager()
    display = xvfb.start()   # ":99"
    # ... launch browser, do work ...
    xvfb.stop()
"""

import os
import logging
import shutil
import subprocess

logger = logging.getLogger("songfactory.automation")


class XvfbManager:
    """Manages an Xvfb virtual display subprocess."""

    def __init__(self, display: str = ":99", resolution: str = "1920x1080x24"):
        """
        Args:
            display: X display number (e.g. ":99").
            resolution: Screen resolution as WxHxD string.
        """
        self.display = display
        self.resolution = resolution
        self._process = None

    def start(self) -> str:
        """Start Xvfb subprocess and set the DISPLAY environment variable.

        Returns:
            The display string (e.g. ":99").

        Raises:
            RuntimeError: If Xvfb is not available or fails to start.
        """
        if not self.is_available():
            raise RuntimeError("Xvfb is not installed or not on PATH")

        if self._process and self._process.poll() is None:
            logger.info(f"Xvfb already running on {self.display}")
            return self.display

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
        return shutil.which("Xvfb") is not None

"""
Song Factory - Centralized Logging Configuration

Sets up rotating file handlers for the application.  Call ``setup_logging()``
once at startup (in main.py) before any module creates a logger.

All modules should use named loggers under the ``songfactory`` namespace::

    logger = logging.getLogger("songfactory.tabs.library")
    logger.info("Loaded %d songs", count)
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.expanduser("~/.songfactory/logs/")


def setup_logging() -> None:
    """Configure the root ``songfactory`` logger with a rotating file handler.

    - Log file: ``~/.songfactory/logs/songfactory.log``
    - Rotation: 5 MB per file, 3 backup copies
    - Console: WARNING and above to stderr
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    root = logging.getLogger("songfactory")
    # Avoid adding handlers twice if called more than once
    if root.handlers:
        return
    root.setLevel(logging.DEBUG)

    # --- Rotating file handler (all levels) ---
    log_path = os.path.join(LOG_DIR, "songfactory.log")
    fh = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    )
    root.addHandler(fh)

    # --- Console handler (warnings and above) ---
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(
        logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
    )
    root.addHandler(ch)

    # Also write automation logs to the legacy path for backward compat
    legacy_dir = os.path.expanduser("~/.songfactory/")
    legacy_path = os.path.join(legacy_dir, "automation.log")
    legacy_fh = RotatingFileHandler(
        legacy_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    legacy_fh.setLevel(logging.INFO)
    legacy_fh.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    automation_logger = logging.getLogger("songfactory.automation")
    automation_logger.addHandler(legacy_fh)

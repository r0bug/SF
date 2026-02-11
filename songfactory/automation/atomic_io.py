"""
Song Factory - Atomic File Operations

Write to a temp file, then rename to the target path.  Prevents partial
files from appearing at the target location on crash or interruption.
"""

import os
import shutil
import tempfile
import logging

logger = logging.getLogger("songfactory.automation")


def atomic_write_binary(target_path: str, data: bytes) -> None:
    """Write binary data atomically to target_path."""
    dir_name = os.path.dirname(target_path) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        os.write(fd, data)
        os.close(fd)
        fd = -1
        shutil.move(tmp_path, target_path)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def atomic_write_text(target_path: str, text: str, encoding: str = "utf-8") -> None:
    """Write text data atomically to target_path."""
    atomic_write_binary(target_path, text.encode(encoding))


def atomic_write_fn(target_path: str, write_fn) -> None:
    """Write to target_path via a callback: write_fn(tmp_path).

    The callback receives a temporary file path to write to.
    On success the temp file is renamed to target_path.
    On failure the temp file is cleaned up.
    """
    dir_name = os.path.dirname(target_path) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        os.close(fd)
        write_fn(tmp_path)
        if os.path.getsize(tmp_path) == 0:
            logger.warning("atomic_write_fn produced empty file: %s", target_path)
        shutil.move(tmp_path, target_path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

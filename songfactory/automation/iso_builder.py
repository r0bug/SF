"""
Song Factory - ISO Builder

Cross-platform QThread worker that creates an ISO image from a CD project's
data directory using pycdlib (pure Python, no platform-specific tools needed).

Replaces the Linux-only cd_burn_worker.py.
"""

import os
import logging
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from automation.data_session_builder import build_data_directory

logger = logging.getLogger("songfactory.automation")

CD_PROJECTS_DIR = Path.home() / ".songfactory" / "cd_projects"


class ISOBuildWorker(QThread):
    """Build an ISO image from a CD project's data files."""

    build_progress = pyqtSignal(str)
    build_completed = pyqtSignal(str)  # iso_path
    build_error = pyqtSignal(str)

    def __init__(self, project, tracks, songs, output_path, parent=None):
        super().__init__(parent)
        self.project = project
        self.tracks = tracks
        self.songs = songs
        self.output_path = output_path
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        try:
            import pycdlib
        except ImportError:
            self.build_error.emit(
                "pycdlib is not installed. Install it with:\n"
                "pip install pycdlib"
            )
            return

        try:
            # Step 1: Build the data directory
            self.build_progress.emit("Building data directory...")
            project_id = self.project.get("id", 0)
            project_dir = str(CD_PROJECTS_DIR / str(project_id))
            os.makedirs(project_dir, exist_ok=True)

            data_dir = build_data_directory(
                self.project, self.tracks, self.songs, project_dir
            )

            if self._stop_requested:
                self.build_progress.emit("ISO build cancelled.")
                return

            # Step 2: Create ISO with pycdlib
            self.build_progress.emit("Creating ISO image...")
            album_name = (
                self.project.get("album_title")
                or self.project.get("name", "CD")
            )

            iso = pycdlib.PyCdlib()
            iso.new(
                interchange_level=4,
                joliet=3,
                rock_ridge="1.09",
                vol_ident=album_name[:32],
            )

            # Step 3: Walk data directory and add files/dirs
            file_count = 0
            for dirpath, dirnames, filenames in os.walk(data_dir):
                if self._stop_requested:
                    self.build_progress.emit("ISO build cancelled.")
                    return

                # Compute relative path from data_dir
                rel_dir = os.path.relpath(dirpath, data_dir)

                if rel_dir != ".":
                    # Add directory to ISO
                    iso_dir_path = "/" + rel_dir.replace(os.sep, "/")
                    joliet_dir_path = "/" + rel_dir.replace(os.sep, "/")
                    rr_name = os.path.basename(rel_dir)

                    try:
                        iso.add_directory(
                            iso_path=iso_dir_path,
                            joliet_path=joliet_dir_path,
                            rr_name=rr_name,
                        )
                    except pycdlib.pycdlibexception.PyCdlibInvalidInput:
                        # Directory may already exist
                        pass

                for filename in filenames:
                    if self._stop_requested:
                        self.build_progress.emit("ISO build cancelled.")
                        return

                    full_path = os.path.join(dirpath, filename)
                    file_size = os.path.getsize(full_path)

                    if rel_dir == ".":
                        iso_file_path = "/" + _iso9660_name(filename)
                        joliet_file_path = "/" + filename
                    else:
                        iso_file_path = (
                            "/" + rel_dir.replace(os.sep, "/")
                            + "/" + _iso9660_name(filename)
                        )
                        joliet_file_path = (
                            "/" + rel_dir.replace(os.sep, "/")
                            + "/" + filename
                        )

                    iso.add_file(
                        full_path,
                        iso_path=iso_file_path,
                        joliet_path=joliet_file_path,
                        rr_name=filename,
                    )
                    file_count += 1
                    self.build_progress.emit(f"Added: {filename}")

            if self._stop_requested:
                self.build_progress.emit("ISO build cancelled.")
                return

            # Step 4: Write ISO to output path
            self.build_progress.emit(
                f"Writing ISO ({file_count} files)..."
            )
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            iso.write(self.output_path)
            iso.close()

            size_mb = os.path.getsize(self.output_path) / (1024 * 1024)
            self.build_progress.emit(
                f"ISO complete: {size_mb:.1f} MB, {file_count} files"
            )
            self.build_completed.emit(self.output_path)

        except Exception as e:
            logger.exception("ISO build failed")
            self.build_error.emit(f"ISO build failed: {e}")


def _iso9660_name(filename: str) -> str:
    """Convert a filename to a valid ISO 9660 Level 4 name.

    Ensures uppercase, replaces invalid chars, and truncates.
    The Joliet and Rock Ridge extensions store the full name.
    """
    name, ext = os.path.splitext(filename)
    # Replace invalid chars
    safe = ""
    for ch in name.upper():
        if ch.isalnum() or ch in ("_", "-"):
            safe += ch
        else:
            safe += "_"
    safe = safe[:24]  # Keep it short for ISO 9660
    ext_safe = ext.upper().replace(" ", "_")[:8]
    result = safe + ext_safe if ext_safe else safe
    return result if result else "FILE"

"""
Song Factory - Audio Converter Worker

QThread that converts MP3 files to 16-bit 44.1kHz stereo WAV using ffmpeg,
suitable for Red Book audio CD burning.
"""

import os
import subprocess
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


CD_PROJECTS_DIR = Path.home() / ".songfactory" / "cd_projects"


class AudioConvertWorker(QThread):
    """Convert a list of tracks from MP3 to WAV for CD burning."""

    track_started = pyqtSignal(int, str)      # track_id, title
    track_completed = pyqtSignal(int, str)    # track_id, wav_path
    track_error = pyqtSignal(int, str)        # track_id, error_msg
    all_finished = pyqtSignal()

    def __init__(self, project_id: int, tracks: list[dict], parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.tracks = tracks
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        output_dir = CD_PROJECTS_DIR / str(self.project_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        for track in self.tracks:
            if self._stop_requested:
                break

            track_id = track["id"]
            title = track.get("title", "Unknown")
            source = track.get("source_path", "")
            track_num = track.get("track_number", 0)

            self.track_started.emit(track_id, title)

            if not source or not os.path.exists(source):
                self.track_error.emit(track_id, f"Source file not found: {source}")
                continue

            wav_name = f"track_{track_num:02d}.wav"
            wav_path = str(output_dir / wav_name)

            try:
                cmd = [
                    "ffmpeg", "-i", source,
                    "-acodec", "pcm_s16le",
                    "-ar", "44100",
                    "-ac", "2",
                    "-y",
                    wav_path,
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0:
                    self.track_error.emit(track_id, f"ffmpeg error: {result.stderr[-200:]}")
                    continue

                # Probe duration
                duration = _probe_duration(wav_path)
                self.track_completed.emit(track_id, wav_path)

            except subprocess.TimeoutExpired:
                self.track_error.emit(track_id, "Conversion timed out (5 min)")
            except Exception as e:
                self.track_error.emit(track_id, str(e))

        self.all_finished.emit()


def _probe_duration(file_path: str) -> float:
    """Probe audio duration in seconds using ffprobe.  Returns 0.0 on error."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def probe_duration(file_path: str) -> float:
    """Public wrapper for duration probing."""
    return _probe_duration(file_path)

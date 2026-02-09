"""
Song Factory - CD Burn Worker

QThread that handles the complete CD-Extra burn sequence:
  Session 1: Audio CD with CD-TEXT via cdrdao (--multi to leave disc open)
  Session 2: Data ISO via genisoimage + wodim (appended, then disc closed)
"""

import os
import subprocess
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from automation.toc_generator import generate_toc
from automation.data_session_builder import build_data_directory


CD_PROJECTS_DIR = Path.home() / ".songfactory" / "cd_projects"


class CDBurnWorker(QThread):
    """Burn a CD-Extra disc (audio + data sessions)."""

    burn_progress = pyqtSignal(str)    # real-time status lines
    burn_completed = pyqtSignal()
    burn_error = pyqtSignal(str)

    def __init__(
        self,
        project: dict,
        tracks: list[dict],
        songs: list[dict],
        device: str = "/dev/sr0",
        speed: int = 0,
        simulate: bool = False,
        audio_only: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.project = project
        self.tracks = tracks
        self.songs = songs
        self.device = device
        self.speed = speed
        self.simulate = simulate
        self.audio_only = audio_only
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        try:
            project_dir = str(CD_PROJECTS_DIR / str(self.project["id"]))
            os.makedirs(project_dir, exist_ok=True)

            # ---- Session 1: Audio CD with CD-TEXT ----
            self.burn_progress.emit("Generating TOC file...")
            toc_content = generate_toc(self.project, self.tracks)
            toc_path = os.path.join(project_dir, "project.toc")
            with open(toc_path, "w", encoding="utf-8") as f:
                f.write(toc_content)

            self.burn_progress.emit("Starting Session 1: Audio CD...")

            cdrdao_cmd = [
                "cdrdao", "write",
                "--device", self.device,
            ]

            # Only use --multi if we're going to write a data session
            if not self.audio_only and not self.simulate:
                cdrdao_cmd.append("--multi")

            if self.speed > 0:
                cdrdao_cmd.extend(["--speed", str(self.speed)])

            if self.simulate:
                cdrdao_cmd.append("--simulate")

            cdrdao_cmd.append(toc_path)

            if not self._run_command(cdrdao_cmd, "Session 1 (Audio)"):
                return

            if self._stop_requested:
                self.burn_progress.emit("Burn cancelled by user.")
                return

            # ---- Session 2: Data (skip in simulate or audio_only mode) ----
            if self.simulate or self.audio_only:
                if self.simulate:
                    self.burn_progress.emit("Simulation complete (data session skipped).")
                else:
                    self.burn_progress.emit("Audio-only burn complete.")
                self.burn_completed.emit()
                return

            self.burn_progress.emit("Building data directory for Session 2...")
            data_dir = build_data_directory(
                self.project, self.tracks, self.songs, project_dir
            )

            if self._stop_requested:
                return

            # Get multisession info
            self.burn_progress.emit("Reading multisession info from disc...")
            msinfo = self._get_msinfo()
            if msinfo is None:
                self.burn_error.emit("Failed to read multisession info from disc.")
                return

            # Create ISO
            self.burn_progress.emit("Creating ISO image for data session...")
            album_name = self.project.get("album_title") or self.project.get("name", "CD")
            iso_path = os.path.join(project_dir, "data_session.iso")

            geniso_cmd = [
                "genisoimage",
                "-V", album_name[:32],   # Volume ID max 32 chars
                "-iso-level", "4",
                "-r", "-J",
                "-C", msinfo,
                "-M", self.device,
                "-o", iso_path,
                data_dir,
            ]

            if not self._run_command(geniso_cmd, "ISO creation"):
                self.burn_error.emit(
                    "Failed to create data ISO. Audio session was written successfully.\n"
                    "You can try burning data manually or eject the disc."
                )
                return

            if self._stop_requested:
                return

            # Append data session
            self.burn_progress.emit("Writing Session 2: Data...")
            wodim_cmd = [
                "wodim",
                f"dev={self.device}",
                "-multi",
                iso_path,
            ]

            if not self._run_command(wodim_cmd, "Session 2 (Data)"):
                self.burn_error.emit(
                    "Failed to write data session. Audio session is intact.\n"
                    "The disc may still be playable as audio-only."
                )
                return

            # Eject
            self.burn_progress.emit("Ejecting disc...")
            subprocess.run(["eject", self.device], capture_output=True, timeout=10)

            self.burn_progress.emit("CD-Extra burn complete!")
            self.burn_completed.emit()

        except Exception as e:
            self.burn_error.emit(f"Unexpected error: {e}")

    def _run_command(self, cmd: list[str], label: str) -> bool:
        """Run a subprocess with real-time output.  Returns True on success."""
        self.burn_progress.emit(f"[{label}] Running: {' '.join(cmd)}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self.burn_progress.emit(f"[{label}] {line}")
                if self._stop_requested:
                    proc.kill()
                    self.burn_progress.emit(f"[{label}] Cancelled.")
                    return False

            proc.wait(timeout=60)

            if proc.returncode != 0:
                self.burn_progress.emit(f"[{label}] Failed (exit code {proc.returncode})")
                self.burn_error.emit(f"{label} failed with exit code {proc.returncode}")
                return False

            self.burn_progress.emit(f"[{label}] Complete.")
            return True

        except FileNotFoundError:
            msg = f"{cmd[0]} not found. Install it with your package manager."
            self.burn_progress.emit(f"[{label}] {msg}")
            self.burn_error.emit(msg)
            return False
        except subprocess.TimeoutExpired:
            self.burn_progress.emit(f"[{label}] Timed out.")
            self.burn_error.emit(f"{label} timed out")
            return False
        except Exception as e:
            self.burn_error.emit(f"{label} error: {e}")
            return False

    def _get_msinfo(self) -> str | None:
        """Get multisession info string from the disc (e.g. '0,12345')."""
        try:
            result = subprocess.run(
                ["wodim", "-msinfo", f"dev={self.device}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout.strip()
            if result.returncode == 0 and "," in output:
                return output
            # Sometimes msinfo is on stderr
            err = result.stderr.strip()
            for line in err.splitlines():
                if "," in line and line.replace(",", "").replace(" ", "").isdigit():
                    return line.strip()
            return None
        except Exception:
            return None

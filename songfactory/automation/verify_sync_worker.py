"""Verify & Sync worker — checks all songs for missing MP3, WAV, or lyrics.

Scans every song in the DB that has a conversion_id. For each song:
- If MP3 file is missing on disk, downloads from S3
- If WAV file doesn't exist alongside the MP3, tries to download from S3
- If lyrics are empty, fetches ``lyrics_output`` from the project detail
  endpoint (``/api/backend/projects/front/get-one-by-id``, cookie auth via
  a headless browser on the saved lalals profile)

Usage:
    worker = VerifySyncWorker(db_path, config)
    worker.progress.connect(on_progress)
    worker.finished.connect(on_done)
    worker.start()
"""

import logging
import sqlite3
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger("songfactory.automation")

# Older songs live under conversions/standard, newer under
# conversions/web/standard — the stored/API URL is tried first.
from automation.lalals_api import LEGACY_S3_BASE, S3_BASE

S3_BASES = (S3_BASE, LEGACY_S3_BASE)


class VerifySyncWorker(QThread):
    """Background worker that verifies and fills missing song data."""

    progress = pyqtSignal(str)
    song_updated = pyqtSignal(int, str)   # db_id, description of what changed
    finished = pyqtSignal(int, int, int)  # mp3_count, wav_count, lyrics_count
    error = pyqtSignal(str)

    def __init__(self, db_path: str, config: dict):
        super().__init__()
        self.db_path = db_path
        self.config = config
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        mp3_count = 0
        wav_count = 0
        lyrics_count = 0
        pw = ctx = None

        try:
            pw, ctx, api = self._open_api()
            if not api.is_logged_in():
                self.error.emit(
                    "Not logged in to lalals.com — "
                    "log in via the Library tab first."
                )
                self.finished.emit(0, 0, 0)
                return

            # Get download dir
            download_dir = self.config.get(
                "download_dir",
                str(Path.home() / "Music" / "SongFactory"),
            )
            from automation.download_manager import DownloadManager
            dm = DownloadManager(download_dir)

            # Query all songs that have a conversion_id
            songs = conn.execute(
                "SELECT id, title, conversion_id_1, conversion_id_2, "
                "file_path_1, file_path_2, lyrics, status, audio_url_1 "
                "FROM songs "
                "WHERE (conversion_id_1 IS NOT NULL AND conversion_id_1 != '') "
                "   OR (conversion_id_2 IS NOT NULL AND conversion_id_2 != '') "
                "ORDER BY id"
            ).fetchall()

            if not songs:
                self.progress.emit("No songs with conversion IDs found")
                self.finished.emit(0, 0, 0)
                return

            total = len(songs)
            self.progress.emit(f"Verifying {total} song(s)...")
            logger.info(f"VerifySync: checking {total} songs")

            for i, song in enumerate(songs):
                if self._stop_flag:
                    break

                song_id = song["id"]
                title = song["title"] or f"Song #{song_id}"
                cid = song["conversion_id_1"] or song["conversion_id_2"] or ""

                if not cid:
                    continue

                self.progress.emit(
                    f"[{i + 1}/{total}] Checking: {title}"
                )

                updates = {}
                detail = None  # project detail, fetched lazily

                def _detail():
                    nonlocal detail
                    if detail is None:
                        try:
                            detail = api.get_project(cid)
                        except Exception as e:
                            logger.debug(f"VerifySync: detail failed for {cid}: {e}")
                            detail = {}
                    return detail

                # --- Check MP3 ---
                fp1 = song["file_path_1"] or ""
                mp3_url = ""
                if not fp1 or not Path(fp1).exists():
                    from automation.lalals_api import project_audio_url
                    candidates = [song["audio_url_1"] or "",
                                  project_audio_url(_detail())]
                    candidates += [f"{b}/{cid}/{cid}.mp3" for b in S3_BASES]
                    for url in dict.fromkeys(u for u in candidates if u):
                        try:
                            path = dm.save_from_url(url, title, 1)
                        except Exception as e:
                            logger.debug(f"VerifySync: MP3 failed for '{title}' ({url}): {e}")
                            continue
                        mp3_url = url
                        updates["file_path_1"] = str(path)
                        updates["audio_url_1"] = url
                        updates["status"] = "completed"
                        mp3_count += 1
                        self.song_updated.emit(song_id, f"Downloaded MP3: {title}")
                        logger.info(f"VerifySync: MP3 downloaded for '{title}'")
                        break

                # --- Check WAV ---
                # WAV lives alongside the MP3 with .wav extension
                mp3_path = updates.get("file_path_1") or fp1
                if mp3_path and Path(mp3_path).exists():
                    wav_path = Path(mp3_path).with_suffix(".wav")
                    base_url = mp3_url or song["audio_url_1"] or ""
                    if not wav_path.exists() and base_url.endswith(".mp3"):
                        wav_url = base_url[:-4] + ".wav"
                        try:
                            dm.save_from_url(wav_url, title, 1)
                            wav_count += 1
                            self.song_updated.emit(song_id, f"Downloaded WAV: {title}")
                            logger.info(f"VerifySync: WAV downloaded for '{title}'")
                        except Exception as e:
                            logger.debug(f"VerifySync: WAV failed for '{title}': {e}")

                # --- Check Lyrics ---
                if not (song["lyrics"] or "").strip():
                    lyrics = (_detail().get("lyrics_output")
                              or _detail().get("lyrics_input") or "")
                    if lyrics:
                        updates["lyrics"] = lyrics
                        lyrics_count += 1
                        self.song_updated.emit(song_id, f"Fetched lyrics: {title}")
                        logger.info(
                            f"VerifySync: lyrics fetched for '{title}' "
                            f"({len(lyrics)} chars)"
                        )

                # --- Update DB ---
                if updates:
                    set_parts = []
                    vals = []
                    for col, val in updates.items():
                        set_parts.append(f"{col}=?")
                        vals.append(val)
                    set_parts.append("updated_at=CURRENT_TIMESTAMP")
                    vals.append(song_id)
                    conn.execute(
                        f"UPDATE songs SET {', '.join(set_parts)} WHERE id=?",
                        vals,
                    )
                    conn.commit()

        except Exception as e:
            error_msg = f"Verify sync error: {e}"
            logger.error(error_msg)
            self.error.emit(error_msg)
        finally:
            conn.close()
            try:
                if ctx:
                    ctx.close()
                if pw:
                    pw.stop()
            except Exception:
                pass

        summary = (
            f"Verify complete: {mp3_count} MP3, "
            f"{wav_count} WAV, {lyrics_count} lyrics updated"
        )
        self.progress.emit(summary)
        logger.info(f"VerifySync: {summary}")
        self.finished.emit(mp3_count, wav_count, lyrics_count)

    def _open_api(self):
        """Open a headless browser on the saved lalals profile.

        Returns:
            (playwright, context, LalalsApi) — caller closes context/playwright.
        """
        from playwright.sync_api import sync_playwright
        from automation.browser_profiles import get_profile_path
        from automation.lalals_api import LalalsApi

        profile_dir = get_profile_path("lalals")
        pw = sync_playwright().start()
        args = ["--disable-blink-features=AutomationControlled"]
        try:
            ctx = pw.chromium.launch_persistent_context(
                profile_dir, headless=True, channel="chrome", args=args,
            )
        except Exception:
            ctx = pw.chromium.launch_persistent_context(
                profile_dir, headless=True, args=args,
            )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        api = LalalsApi(page)
        api.ensure_origin()
        return pw, ctx, api

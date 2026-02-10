"""DistroKid upload worker for Song Factory.

QThread that manages the browser lifecycle, login/2FA flow, and upload
queue processing for distributing songs via distrokid.com.
"""

import time
import logging
import sqlite3
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from playwright.sync_api import sync_playwright

logger = logging.getLogger("songfactory.automation")

LOG_DIR = Path.home() / ".songfactory"
DK_PROFILE_DIR = LOG_DIR / "dk_browser_profile"


class DistroKidWorker(QThread):
    """Background worker that uploads songs to DistroKid via browser automation."""

    # Signals
    upload_started = pyqtSignal(int, str)       # dist_id, song_title
    upload_completed = pyqtSignal(int)           # dist_id
    upload_error = pyqtSignal(int, str)          # dist_id, error_message
    progress_update = pyqtSignal(str)            # status message
    login_required = pyqtSignal(str)             # message for user
    queue_finished = pyqtSignal()                # all done

    def __init__(self, db_path: str, config: dict, dist_ids: list = None):
        """
        Args:
            db_path: Path to SQLite database.
            config: Dict with keys:
                - download_dir: str
                - browser_path: str (optional)
                - use_xvfb: bool (default False)
            dist_ids: Optional list of distribution IDs to process.
                      If None, processes all with status='ready'.
        """
        super().__init__()
        self.db_path = db_path
        self.config = config
        self.dist_ids = dist_ids
        self._stop_flag = False

    def stop(self):
        """Signal graceful stop after current upload finishes."""
        self._stop_flag = True
        logger.info("DistroKid worker: stop requested")

    def run(self):
        """Main loop: open browser, login if needed, upload each release."""
        from automation.distrokid_driver import DistroKidDriver, DistroKidDriverError

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Fetch distributions to process
        if self.dist_ids:
            placeholders = ",".join("?" for _ in self.dist_ids)
            cursor = conn.execute(
                f"SELECT d.*, s.title AS song_title, s.file_path_1, s.lyrics "
                f"FROM distributions d "
                f"JOIN songs s ON d.song_id = s.id "
                f"WHERE d.id IN ({placeholders}) ORDER BY d.id",
                self.dist_ids,
            )
        else:
            cursor = conn.execute(
                "SELECT d.*, s.title AS song_title, s.file_path_1, s.lyrics "
                "FROM distributions d "
                "JOIN songs s ON d.song_id = s.id "
                "WHERE d.status = 'ready' ORDER BY d.id"
            )
        releases = [dict(row) for row in cursor.fetchall()]

        if not releases:
            self.progress_update.emit("No releases ready for upload")
            self.queue_finished.emit()
            conn.close()
            return

        total = len(releases)
        self.progress_update.emit(f"Starting DistroKid upload: {total} release(s)")
        logger.info(f"DistroKid queue started: {total} releases")

        # Xvfb
        xvfb = None
        if self.config.get("use_xvfb", False):
            try:
                from automation.xvfb_manager import XvfbManager
                if XvfbManager.is_available():
                    xvfb = XvfbManager()
                    display = xvfb.start()
                    logger.info(f"Xvfb started on {display}")
                    self.progress_update.emit(f"Virtual display started ({display})")
            except Exception as e:
                logger.warning(f"Failed to start Xvfb: {e}")

        playwright = None
        context = None
        try:
            playwright = sync_playwright().start()

            profile_dir = str(DK_PROFILE_DIR)

            launch_args = {
                "headless": False,
                "slow_mo": 150,
                "accept_downloads": True,
                "viewport": {"width": 1280, "height": 900},
                "args": [
                    "--disable-blink-features=AutomationControlled",
                ],
            }
            browser_path = self.config.get("browser_path")
            if browser_path:
                launch_args["executable_path"] = browser_path

            try:
                context = playwright.chromium.launch_persistent_context(
                    profile_dir, channel="chrome", **launch_args
                )
                logger.info("DistroKid: launched with system Chrome")
            except Exception:
                context = playwright.chromium.launch_persistent_context(
                    profile_dir, **launch_args
                )
                logger.info("DistroKid: launched with bundled Chromium")

            page = context.pages[0] if context.pages else context.new_page()
            driver = DistroKidDriver(page, context)

            # Check login
            self.progress_update.emit("Checking DistroKid login...")
            if not driver.is_logged_in():
                self.progress_update.emit(
                    "Please log in to DistroKid and complete 2FA..."
                )
                self.login_required.emit(
                    "Please log in to DistroKid in the browser window.\n"
                    "Complete email/password and 2FA verification.\n"
                    "The upload will continue automatically once you're logged in."
                )
                driver.open_login_page()

                try:
                    driver.wait_for_manual_login(
                        timeout_s=600,
                        stop_flag=lambda: self._stop_flag,
                    )
                except DistroKidDriverError as e:
                    self.progress_update.emit(f"Login failed: {e}")
                    conn.close()
                    context.close()
                    playwright.stop()
                    if xvfb:
                        xvfb.stop()
                    self.queue_finished.emit()
                    return

            self.progress_update.emit("Logged in to DistroKid")

            # Process each release
            for i, release in enumerate(releases):
                if self._stop_flag:
                    self.progress_update.emit("Stopped by user")
                    break

                dist_id = release["id"]
                song_title = release["song_title"]
                self.upload_started.emit(dist_id, song_title)
                self.progress_update.emit(
                    f"Uploading '{song_title}' ({i + 1}/{total})"
                )
                logger.info(f"Uploading dist {dist_id}: {song_title}")

                # Mark as uploading
                conn.execute(
                    "UPDATE distributions SET status='uploading', "
                    "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (dist_id,),
                )
                conn.commit()

                try:
                    # Build form data
                    form_data = {
                        "artist_name": release.get("artist_name", "Yakima Finds"),
                        "album_title": release.get("album_title") or song_title,
                        "title": song_title,
                        "songwriter": release.get("songwriter", ""),
                        "primary_genre": release.get("primary_genre", "Pop"),
                        "language": release.get("language", "English"),
                        "cover_art_path": release.get("cover_art_path", ""),
                        "is_instrumental": release.get("is_instrumental", 0),
                        "ai_disclosure": release.get("ai_disclosure", 1),
                        "audio_path": release.get("file_path_1", ""),
                    }

                    # Fill the form
                    driver.fill_upload_form(form_data)

                    # Click upload
                    driver.click_upload()

                    # Wait for completion
                    driver.wait_for_upload_complete(
                        timeout_s=300,
                        stop_flag=lambda: self._stop_flag,
                    )

                    # Mark as submitted
                    conn.execute(
                        "UPDATE distributions SET status='submitted', "
                        "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (dist_id,),
                    )
                    conn.commit()

                    self.upload_completed.emit(dist_id)
                    logger.info(f"Upload complete: {song_title}")

                except DistroKidDriverError as e:
                    error_msg = str(e)
                    logger.error(f"Upload error for {song_title}: {error_msg}")
                    conn.execute(
                        "UPDATE distributions SET status='error', "
                        "error_message=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (error_msg, dist_id),
                    )
                    conn.commit()
                    self.upload_error.emit(dist_id, error_msg)

                except Exception as e:
                    error_msg = f"Unexpected error: {e}"
                    logger.error(f"Upload error for {song_title}: {error_msg}")
                    conn.execute(
                        "UPDATE distributions SET status='error', "
                        "error_message=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (error_msg, dist_id),
                    )
                    conn.commit()
                    self.upload_error.emit(dist_id, error_msg)

                # Brief pause between uploads
                if i < total - 1 and not self._stop_flag:
                    self.progress_update.emit("Waiting before next upload...")
                    for _ in range(10):
                        if self._stop_flag:
                            break
                        time.sleep(1)

            self.progress_update.emit("DistroKid upload queue complete")

        except Exception as e:
            logger.error(f"Fatal error in DistroKid worker: {e}")
            self.progress_update.emit(f"Fatal error: {e}")

        finally:
            try:
                if context:
                    context.close()
                if playwright:
                    playwright.stop()
            except Exception:
                pass
            if xvfb:
                try:
                    xvfb.stop()
                except Exception:
                    pass
            conn.close()
            self.queue_finished.emit()

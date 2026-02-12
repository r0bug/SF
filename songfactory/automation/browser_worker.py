"""Browser automation worker for Song Factory — processes lalals.com queue.

New flow (v3):
1. Submit each song (fill form + click generate)
2. Capture task_id from the API response
3. Set status → "submitted", emit awaiting_refresh signal
4. **Wait** for the user to click "Refresh" in the UI
5. On refresh → download via fresh-URL API or Home page 3-dot menu
6. Link files to the song record, mark "completed"
"""

import time
import logging
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from playwright.sync_api import sync_playwright

logger = logging.getLogger("songfactory.automation")

LOG_DIR = Path.home() / ".songfactory"
LOG_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = LOG_DIR / "browser_state.json"


class LalalsWorker(QThread):
    """Background worker that processes the lalals queue via browser automation."""

    # Signals to communicate with the GUI
    song_started = pyqtSignal(int, str)         # song_id, song_title
    song_completed = pyqtSignal(int, str, str)  # song_id, file_path_1, file_path_2
    song_error = pyqtSignal(int, str)           # song_id, error_message
    progress_update = pyqtSignal(str)           # status message
    queue_finished = pyqtSignal()               # all done
    login_required = pyqtSignal(str)            # error message when login fails
    awaiting_refresh = pyqtSignal(int, str)     # song_id, title — waiting for user

    def __init__(self, db_path: str, config: dict, song_ids: list = None):
        """
        Args:
            db_path: Path to SQLite database
            config: Dict with keys:
                - lalals_email: str
                - lalals_password: str
                - download_dir: str (default ~/Music/SongFactory/)
                - headless: bool (default False)
                - delay_between_songs: int seconds (default 30)
                - max_songs_per_session: int (default 20)
                - dry_run: bool (default False)
                - use_xvfb: bool (default False)
            song_ids: Optional list of specific song IDs to process.
                      If None, processes all songs with status='queued'.
        """
        super().__init__()
        self.db_path = db_path
        self.config = config
        self.song_ids = song_ids
        self._stop_flag = False
        self._refresh_requested = False
        self._current_song_id = None

    def stop(self):
        """Signal graceful stop after current song finishes."""
        self._stop_flag = True
        self._refresh_requested = True  # also unblock refresh wait
        logger.info("Stop requested — will finish current song then stop")

    def request_refresh(self):
        """Called by the UI when user clicks Refresh (song is done)."""
        self._refresh_requested = True
        logger.info("Refresh requested by user")

    def run(self):
        """Main loop: open browser, login if needed, submit each song,
        wait for refresh, then download."""
        import sqlite3
        from automation.lalals_driver import LalalsDriver, LalalsDriverError
        from automation.download_manager import DownloadManager

        # Create own DB connection for thread safety
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        download_dir = self.config.get(
            'download_dir', str(Path.home() / "Music" / "SongFactory")
        )
        dm = DownloadManager(download_dir)
        dry_run = self.config.get('dry_run', False)
        delay = self.config.get('delay_between_songs', 30)
        max_songs = self.config.get('max_songs_per_session', 20)
        use_xvfb = self.config.get('use_xvfb', False)

        # Fetch queued songs
        if self.song_ids:
            placeholders = ','.join('?' for _ in self.song_ids)
            cursor = conn.execute(
                f"SELECT * FROM songs WHERE id IN ({placeholders}) ORDER BY id",
                self.song_ids
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM songs WHERE status='queued' ORDER BY id"
            )
        songs = [dict(row) for row in cursor.fetchall()]

        if not songs:
            self.progress_update.emit("No queued songs to process")
            self.queue_finished.emit()
            conn.close()
            return

        total = min(len(songs), max_songs)
        self.progress_update.emit(f"Starting queue: {total} song(s) to process")
        logger.info(f"Queue started: {total} songs, dry_run={dry_run}")

        if dry_run:
            self._run_dry(songs[:total], conn, dm)
            conn.close()
            return

        # Xvfb virtual display
        xvfb = None
        if use_xvfb:
            try:
                from automation.xvfb_manager import XvfbManager
                if XvfbManager.is_available():
                    xvfb = XvfbManager()
                    display = xvfb.start()
                    logger.info(f"Xvfb started on {display}")
                    self.progress_update.emit(f"Virtual display started ({display})")
                else:
                    logger.warning("Xvfb requested but not available on system")
                    self.progress_update.emit("Xvfb not available — using normal display")
            except Exception as e:
                logger.warning(f"Failed to start Xvfb: {e}")

        # Real browser automation
        playwright = None
        context = None
        try:
            playwright = sync_playwright().start()

            from automation.browser_profiles import get_profile_path
            profile_dir = get_profile_path("lalals")

            # Always headless — visible browser lets users close it mid-queue
            launch_args = {
                'headless': True,
                'slow_mo': 100,
                'accept_downloads': True,
                'viewport': {'width': 1280, 'height': 900},
                'args': [
                    '--disable-blink-features=AutomationControlled',
                ],
            }
            browser_path = self.config.get('browser_path')
            if browser_path:
                launch_args['executable_path'] = browser_path

            try:
                context = playwright.chromium.launch_persistent_context(
                    profile_dir, channel='chrome', **launch_args
                )
                logger.info("Launched with system Chrome + persistent profile")
            except Exception:
                context = playwright.chromium.launch_persistent_context(
                    profile_dir, **launch_args
                )
                logger.info("Launched with bundled Chromium + persistent profile")

            page = context.pages[0] if context.pages else context.new_page()
            driver = LalalsDriver(page, context)

            # Check login status
            self.progress_update.emit("Checking login status...")
            if not driver.is_logged_in():
                self.progress_update.emit(
                    "Please log in to lalals.com in the browser window..."
                )
                self.login_required.emit(
                    "Please log in to lalals.com in the browser window "
                    "(Google Auth, etc). The queue will continue automatically "
                    "once you're logged in."
                )
                driver.open_login_page()

                try:
                    driver.wait_for_manual_login(
                        timeout_s=300,
                        stop_flag=lambda: self._stop_flag,
                    )
                except LalalsDriverError as e:
                    self.progress_update.emit(f"Login failed: {e}")
                    conn.close()
                    context.close()
                    playwright.stop()
                    if xvfb:
                        xvfb.stop()
                    self.queue_finished.emit()
                    return

            self.progress_update.emit("Logged in successfully")

            # Process each song
            for i, song in enumerate(songs[:total]):
                if self._stop_flag:
                    self.progress_update.emit("Stopped by user")
                    logger.info("Queue stopped by user")
                    break

                song_id = song['id']
                title = song['title']
                prompt = song['prompt']
                lyrics = song['lyrics']
                self._current_song_id = song_id

                self.song_started.emit(song_id, title)
                self.progress_update.emit(
                    f"Submitting '{title}' ({i + 1}/{total})"
                )
                logger.info(f"Submitting song {song_id}: {title}")

                # Mark as processing
                conn.execute(
                    "UPDATE songs SET status='processing' WHERE id=?", (song_id,)
                )
                conn.commit()

                try:
                    # Check browser is still alive before each song
                    try:
                        _ = page.url
                    except Exception:
                        error_msg = "Browser was closed — cannot continue queue"
                        logger.error(error_msg)
                        conn.execute(
                            "UPDATE songs SET status='error', notes=? WHERE id=?",
                            (error_msg, song_id)
                        )
                        conn.commit()
                        self.song_error.emit(song_id, error_msg)
                        self.progress_update.emit(error_msg)
                        break

                    # Check if still logged in before each song
                    if "/auth/" in page.url:
                        self.progress_update.emit(
                            "Session expired — please log in again..."
                        )
                        self.login_required.emit(
                            "Session expired. Please log in again in the "
                            "browser window."
                        )
                        driver.open_login_page()
                        driver.wait_for_manual_login(
                            timeout_s=300,
                            stop_flag=lambda: self._stop_flag,
                        )

                    # ---- SUBMIT the song ----
                    task_id, task_data = driver.submit_song(prompt, lyrics)

                    # Extract captured data for later use
                    auth_token = task_data.get("auth_token", "")
                    cid1 = task_data.get("conversion_id_1", "")
                    cid2 = task_data.get("conversion_id_2", "")

                    # Store task_id + conversion IDs, set status to "submitted"
                    if task_id:
                        set_parts = ["status='submitted'", "task_id=?"]
                        vals = [task_id]
                        if cid1:
                            set_parts.append("conversion_id_1=?")
                            vals.append(cid1)
                        if cid2:
                            set_parts.append("conversion_id_2=?")
                            vals.append(cid2)
                        vals.append(song_id)
                        conn.execute(
                            f"UPDATE songs SET {', '.join(set_parts)} WHERE id=?",
                            vals
                        )
                    else:
                        conn.execute(
                            "UPDATE songs SET status='submitted' WHERE id=?",
                            (song_id,)
                        )
                    conn.commit()

                    # ---- WAIT for user to click Refresh ----
                    self.awaiting_refresh.emit(song_id, title)
                    self.progress_update.emit(
                        f"'{title}' submitted — click Refresh when generation is done"
                    )
                    logger.info(f"Song {song_id} submitted, waiting for refresh...")

                    self._refresh_requested = False
                    while not self._refresh_requested and not self._stop_flag:
                        time.sleep(1)

                    if self._stop_flag:
                        logger.info("Stop flag set during refresh wait")
                        break

                    # ---- REFRESH: Download the song ----
                    self._refresh_requested = False
                    self.progress_update.emit(
                        f"Refreshing — downloading '{title}'..."
                    )
                    logger.info(f"Refresh received for song {song_id}, downloading...")

                    # Post-refresh delay: S3 files may still be propagating
                    from timeouts import TIMEOUTS
                    post_delay = TIMEOUTS.get("post_refresh_delay_s", 5)
                    logger.info(f"Post-refresh delay: {post_delay}s")
                    time.sleep(post_delay)

                    from automation.retry import retry_call
                    from automation.download_manager import DownloadVerificationError

                    file_path_1 = ""
                    file_path_2 = ""
                    actual_size_1 = 0
                    actual_size_2 = 0
                    metadata = {}

                    # Strategy 1: Use task_id to fetch fresh URLs via API
                    if task_id:
                        def _strategy_1():
                            nonlocal metadata
                            m = driver.fetch_fresh_urls(
                                task_id, auth_token, cid1, cid2
                            )
                            if m:
                                p = driver.download_songs_v2(
                                    m, download_dir, title
                                )
                                return m, p
                            return m, []

                        try:
                            metadata, paths = retry_call(
                                _strategy_1,
                                max_attempts=3,
                                backoff_base=2,
                            )
                            if len(paths) >= 1:
                                file_path_1 = str(paths[0])
                                actual_size_1 = Path(paths[0]).stat().st_size
                            if len(paths) >= 2:
                                file_path_2 = str(paths[1])
                                actual_size_2 = Path(paths[1]).stat().st_size
                            logger.info(
                                f"API download: {len(paths)} file(s)"
                            )
                        except Exception as e:
                            logger.warning(f"API download failed: {e}")

                    # Strategy 2: Home page three-dot menu download
                    if not file_path_1:
                        def _strategy_2():
                            driver.go_to_home_page()
                            page.wait_for_timeout(3000)
                            return driver.download_from_home(
                                title, download_dir,
                                prompt=prompt, lyrics=lyrics,
                                task_id=task_id,
                            )

                        try:
                            logger.info("Trying Home page download fallback...")
                            paths = retry_call(
                                _strategy_2,
                                max_attempts=2,
                                backoff_base=3,
                            )
                            if paths:
                                file_path_1 = str(paths[0])
                                actual_size_1 = Path(paths[0]).stat().st_size
                                logger.info(f"Home page download: {paths[0]}")
                                if len(paths) >= 2:
                                    file_path_2 = str(paths[1])
                                    actual_size_2 = Path(paths[1]).stat().st_size
                        except Exception as e:
                            logger.warning(f"Home page download failed: {e}")

                    # Strategy 3: If we have file_path_1 but not file_path_2,
                    # try to grab the second version via direct URL download
                    if file_path_1 and not file_path_2:
                        url_2 = metadata.get("audio_url_2")
                        if not url_2:
                            # Build S3 URL from conversion_id_2
                            c2 = metadata.get("conversion_id_2") or cid2
                            if c2:
                                url_2 = f"https://lalals.s3.amazonaws.com/conversions/standard/{c2}/{c2}.mp3"
                        if url_2:
                            def _strategy_3():
                                from automation.download_manager import DownloadManager
                                dm2 = DownloadManager(download_dir)
                                return dm2.save_from_url(url_2, title, 2)

                            try:
                                p2 = retry_call(
                                    _strategy_3,
                                    max_attempts=3,
                                    backoff_base=2,
                                )
                                file_path_2 = str(p2)
                                actual_size_2 = Path(p2).stat().st_size
                                logger.info(f"Version 2 via URL: {p2}")
                            except Exception as e:
                                logger.warning(f"Version 2 URL download failed: {e}")

                    # Update DB — override API file_size with actual on-disk sizes
                    update_kwargs = {
                        'status': 'completed' if file_path_1 else 'error',
                        'file_path_1': file_path_1,
                        'file_path_2': file_path_2,
                    }
                    # Merge metadata columns
                    metadata_cols = {
                        'task_id', 'conversion_id_1', 'conversion_id_2',
                        'audio_url_1', 'audio_url_2', 'music_style',
                        'duration_seconds', 'file_format', 'file_size_1',
                        'file_size_2', 'voice_used', 'lalals_created_at',
                        'lyrics_timestamped',
                    }
                    for key in metadata_cols:
                        if key in metadata:
                            update_kwargs[key] = metadata[key]

                    # Always use actual file sizes from disk
                    if actual_size_1:
                        update_kwargs['file_size_1'] = actual_size_1
                    if actual_size_2:
                        update_kwargs['file_size_2'] = actual_size_2

                    set_parts = []
                    values = []
                    for k, v in update_kwargs.items():
                        set_parts.append(f"{k}=?")
                        values.append(v)
                    set_parts.append("updated_at=CURRENT_TIMESTAMP")
                    values.append(song_id)

                    conn.execute(
                        f"UPDATE songs SET {', '.join(set_parts)} WHERE id=?",
                        values
                    )
                    conn.commit()

                    if file_path_1:
                        self.song_completed.emit(song_id, file_path_1, file_path_2)
                        logger.info(f"Completed: {title}")
                    else:
                        notes = "No download files captured after refresh"
                        conn.execute(
                            "UPDATE songs SET notes=? WHERE id=?",
                            (notes, song_id)
                        )
                        conn.commit()
                        self.song_error.emit(song_id, notes)
                        logger.warning(f"No files for: {title}")

                except LalalsDriverError as e:
                    try:
                        driver._capture_debug_screenshot(f"error_{song_id}")
                    except Exception:
                        pass
                    error_msg = e.user_message if hasattr(e, 'user_message') else str(e)
                    logger.error(f"Error processing {title}: {error_msg}")
                    conn.execute(
                        "UPDATE songs SET status='error', notes=? WHERE id=?",
                        (error_msg, song_id)
                    )
                    conn.commit()
                    self.song_error.emit(song_id, error_msg)

                except Exception as e:
                    try:
                        driver._capture_debug_screenshot(f"error_{song_id}")
                    except Exception:
                        pass
                    error_msg = f"Unexpected error: {e}"
                    logger.error(f"Error processing {title}: {error_msg}")
                    conn.execute(
                        "UPDATE songs SET status='error', notes=? WHERE id=?",
                        (error_msg, song_id)
                    )
                    conn.commit()
                    self.song_error.emit(song_id, error_msg)

                # Delay between songs (politeness)
                if i < total - 1 and not self._stop_flag:
                    self.progress_update.emit(
                        f"Waiting {delay}s before next song..."
                    )
                    for _ in range(delay):
                        if self._stop_flag:
                            break
                        time.sleep(1)

            self._current_song_id = None
            self.progress_update.emit("Queue processing complete")

        except Exception as e:
            logger.error(f"Fatal error in worker: {e}")
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

    def _run_dry(self, songs: list, conn, dm) -> None:
        """Dry run mode -- simulate processing without launching a browser."""
        total = len(songs)
        for i, song in enumerate(songs):
            if self._stop_flag:
                self.progress_update.emit("Stopped by user")
                break

            song_id = song['id']
            title = song['title']
            self.song_started.emit(song_id, title)
            self.progress_update.emit(
                f"[DRY RUN] Processing '{title}' ({i + 1}/{total})"
            )

            conn.execute(
                "UPDATE songs SET status='processing' WHERE id=?", (song_id,)
            )
            conn.commit()

            time.sleep(2)  # Simulate processing time

            # Create dummy files
            p1 = dm.get_file_path(title, 1, ".mp3")
            p2 = dm.get_file_path(title, 2, ".mp3")
            p1.parent.mkdir(parents=True, exist_ok=True)
            p1.write_text("[dry run placeholder]")
            p2.write_text("[dry run placeholder]")

            conn.execute(
                "UPDATE songs SET status='completed', "
                "file_path_1=?, file_path_2=? WHERE id=?",
                (str(p1), str(p2), song_id)
            )
            conn.commit()

            self.song_completed.emit(song_id, str(p1), str(p2))
            logger.info(f"[DRY RUN] Completed: {title}")

        self.progress_update.emit("[DRY RUN] Queue complete")
        self.queue_finished.emit()

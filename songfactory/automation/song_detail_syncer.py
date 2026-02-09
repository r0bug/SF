"""Song detail syncer — fetches prompt + lyrics from lalals.com profile.

Opens the profile page, clicks Load More to load all songs, and extracts
prompt + lyrics from the API responses (queue_task.input_payload).

The infinite-projects API response includes:
    queue_task.input_payload.lyrics   — full lyrics text
    queue_task.input_payload.prompt   — generation prompt / music style

This avoids clicking into individual songs — one page load gets everything.

Usage:
    syncer = SongDetailSyncer(db_path, config)
    syncer.progress.connect(on_progress)
    syncer.finished.connect(on_done)
    syncer.start()
"""

import logging
import sqlite3
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger("songfactory.automation")

LOG_DIR = Path.home() / ".songfactory"


class SongDetailSyncer(QThread):
    """Background worker that syncs prompt + lyrics for songs from lalals.com."""

    progress = pyqtSignal(str)       # status message
    song_synced = pyqtSignal(int, str)  # db_id, title
    finished = pyqtSignal(int)       # count synced
    error = pyqtSignal(str)          # error message

    def __init__(self, db_path: str, config: dict,
                 song_ids: list = None):
        """
        Args:
            db_path: Path to SQLite database.
            config: Dict with lalals_username, use_xvfb, browser_path.
            song_ids: Optional list of DB song IDs to sync.
                      If None, syncs ALL songs that have a task_id
                      but are missing prompt or lyrics.
        """
        super().__init__()
        self.db_path = db_path
        self.config = config
        self.song_ids = song_ids
        self._stop_flag = False

    def stop(self):
        """Signal graceful stop."""
        self._stop_flag = True

    def run(self):
        """Main: open browser, load profile, extract details, update DB."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Find songs that need syncing
        if self.song_ids:
            placeholders = ",".join("?" * len(self.song_ids))
            songs_to_sync = conn.execute(
                f"SELECT id, title, task_id, prompt, lyrics FROM songs "
                f"WHERE id IN ({placeholders}) AND task_id IS NOT NULL "
                f"AND task_id != ''",
                self.song_ids,
            ).fetchall()
        else:
            songs_to_sync = conn.execute(
                "SELECT id, title, task_id, prompt, lyrics FROM songs "
                "WHERE task_id IS NOT NULL AND task_id != '' "
                "AND (prompt IS NULL OR prompt = '' "
                "     OR lyrics IS NULL OR lyrics = '')"
            ).fetchall()

        if not songs_to_sync:
            self.progress.emit("No songs need syncing")
            conn.close()
            self.finished.emit(0)
            return

        # Build lookup: task_id -> {db_id, title, has_prompt, has_lyrics}
        need_sync = {}
        for row in songs_to_sync:
            need_sync[row["task_id"]] = {
                "db_id": row["id"],
                "title": row["title"],
                "has_prompt": bool(row["prompt"]),
                "has_lyrics": bool(row["lyrics"]),
            }

        self.progress.emit(
            f"Syncing details for {len(need_sync)} song(s)..."
        )
        logger.info(f"SongDetailSyncer: {len(need_sync)} songs to sync")

        # Open browser and load profile page
        playwright_mod = None
        context = None
        xvfb = None
        synced_count = 0

        try:
            from playwright.sync_api import sync_playwright

            # Xvfb setup
            use_xvfb = self.config.get("use_xvfb", True)
            headless = True
            if use_xvfb:
                try:
                    from automation.xvfb_manager import XvfbManager
                    if XvfbManager.is_available():
                        xvfb = XvfbManager()
                        xvfb.start()
                        headless = False
                except Exception:
                    pass

            playwright_mod = sync_playwright().start()
            profile_dir = str(LOG_DIR / "browser_profile")

            launch_args = {
                "headless": headless,
                "accept_downloads": True,
                "viewport": {"width": 1280, "height": 900},
                "args": ["--disable-blink-features=AutomationControlled"],
            }
            browser_path = self.config.get("browser_path")
            if browser_path:
                launch_args["executable_path"] = browser_path

            try:
                context = playwright_mod.chromium.launch_persistent_context(
                    profile_dir, channel="chrome", **launch_args
                )
            except Exception:
                context = playwright_mod.chromium.launch_persistent_context(
                    profile_dir, **launch_args
                )

            page = context.pages[0] if context.pages else context.new_page()

            # Get username
            username = self.config.get("lalals_username", "").strip()
            if not username:
                self.error.emit(
                    "No lalals.com username configured. "
                    "Set it in Settings > Lalals.com Username."
                )
                self.finished.emit(0)
                return

            # Set up API response interception
            # The DB task_id can match the profile's top-level `id`,
            # or `conversion_id_1` / `conversion_id_2` inside
            # queue_task.input_payload.
            api_details = {}  # db_task_id -> {prompt, lyrics}

            def on_response(response):
                if "infinite-projects" not in response.url:
                    return
                try:
                    body = response.json()
                    items = body.get("data", []) if isinstance(body, dict) else []
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        # Extract prompt/lyrics from queue_task
                        qt = item.get("queue_task") or {}
                        ip = qt.get("input_payload") or {} if isinstance(qt, dict) else {}
                        if not isinstance(ip, dict):
                            continue
                        lyrics = ip.get("lyrics", "")
                        prompt = ip.get("prompt", "")
                        if not (lyrics or prompt):
                            continue
                        details = {"lyrics": lyrics, "prompt": prompt}

                        # Check ALL IDs against need_sync
                        candidate_ids = set()
                        pid = item.get("id", "")
                        if pid:
                            candidate_ids.add(pid)
                        c1 = ip.get("conversion_id_1", "")
                        c2 = ip.get("conversion_id_2", "")
                        if c1:
                            candidate_ids.add(c1)
                        if c2:
                            candidate_ids.add(c2)

                        for cid in candidate_ids:
                            if cid in need_sync:
                                api_details[cid] = details
                except Exception as e:
                    logger.debug(f"Detail sync response parse error: {e}")

            page.on("response", on_response)

            # Navigate to profile page
            url = f"https://lalals.com/user/{username}/audio"
            self.progress.emit(f"Loading profile page...")
            page.goto(url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(3000)

            if "/auth/" in page.url:
                self.error.emit("Not logged in to lalals.com")
                self.finished.emit(0)
                return

            # Check if profile loaded
            has_table = page.evaluate(
                '() => !!document.querySelector("[data-name=\'ProjectTable\']")'
            )
            if not has_table:
                self.error.emit("Profile page did not load properly")
                self.finished.emit(0)
                return

            # Check if we already have all the data from initial load
            remaining = set(need_sync.keys()) - set(api_details.keys())
            click_num = 0
            no_new_match_count = 0

            # Click Load More until we've found all needed songs or exhausted
            while remaining and click_num < 30 and not self._stop_flag:
                load_more_visible = page.evaluate("""
                    () => {
                        const btns = document.querySelectorAll("button");
                        for (const btn of btns) {
                            if ((btn.textContent || "").trim() === "Load More"
                                && btn.offsetParent !== null) return true;
                        }
                        return false;
                    }
                """)

                if not load_more_visible:
                    break

                matches_before = len(api_details)

                try:
                    btn = page.locator('button:has-text("Load More")').first
                    btn.scroll_into_view_if_needed()
                    page.wait_for_timeout(500)
                    btn.click()
                except Exception:
                    break

                page.wait_for_timeout(2500)
                click_num += 1
                remaining = set(need_sync.keys()) - set(api_details.keys())

                new_matches = len(api_details) - matches_before
                if new_matches > 0:
                    no_new_match_count = 0
                else:
                    no_new_match_count += 1
                    # Stop early if no new matches after 3 consecutive clicks
                    if no_new_match_count >= 3:
                        logger.info(
                            f"No new matches after 3 clicks, stopping "
                            f"(found {len(api_details)}/{len(need_sync)})"
                        )
                        break

                self.progress.emit(
                    f"Loading songs... found details for "
                    f"{len(api_details)}/{len(need_sync)} "
                    f"(click {click_num})"
                )

            # Update DB with extracted data
            self.progress.emit(
                f"Updating {len(api_details)} song(s) with prompt/lyrics..."
            )

            for task_id, details in api_details.items():
                if self._stop_flag:
                    break

                info = need_sync.get(task_id)
                if not info:
                    continue

                db_id = info["db_id"]
                title = info["title"]

                set_parts = []
                vals = []

                # Only update fields that are currently empty
                # unless this was an explicit single-song sync
                if details.get("prompt") and (
                    not info["has_prompt"] or self.song_ids
                ):
                    set_parts.append("prompt=?")
                    vals.append(details["prompt"])

                if details.get("lyrics") and (
                    not info["has_lyrics"] or self.song_ids
                ):
                    set_parts.append("lyrics=?")
                    vals.append(details["lyrics"])

                if not set_parts:
                    continue

                set_parts.append("updated_at=CURRENT_TIMESTAMP")
                vals.append(db_id)

                conn.execute(
                    f"UPDATE songs SET {', '.join(set_parts)} WHERE id=?",
                    vals,
                )
                conn.commit()
                synced_count += 1
                self.song_synced.emit(db_id, title)
                logger.info(
                    f"Synced details for '{title}' (id={db_id}): "
                    f"prompt={len(details.get('prompt',''))}ch "
                    f"lyrics={len(details.get('lyrics',''))}ch"
                )

        except Exception as e:
            error_msg = f"Detail sync error: {e}"
            logger.error(error_msg)
            self.error.emit(error_msg)
        finally:
            try:
                if context:
                    context.close()
                if playwright_mod:
                    playwright_mod.stop()
                if xvfb:
                    xvfb.stop()
            except Exception:
                pass
            conn.close()

        self.progress.emit(
            f"Sync complete: updated {synced_count} song(s)"
        )
        self.finished.emit(synced_count)

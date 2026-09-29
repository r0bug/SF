"""Song detail syncer — fetches prompt + lyrics via the lalals backend API.

Opens a browser with the persistent profile, navigates to lalals.com
to establish an authenticated session, then pages through
``/api/backend/user/{uid}/projects`` to fetch prompt + lyrics for songs
that are missing them.

Each project item includes:
    queue_task.input_payload.prompt   — generation prompt / music style
Lyrics come from the project detail endpoint (``lyrics_output``).

Usage:
    syncer = SongDetailSyncer(db_path, config)
    syncer.progress.connect(on_progress)
    syncer.finished.connect(on_done)
    syncer.start()
"""

import logging
import re
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
            config: Dict with use_xvfb, browser_path.
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
        """Main: open browser, fetch lalals projects, extract details, update DB."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Find songs that need syncing
        if self.song_ids:
            placeholders = ",".join("?" * len(self.song_ids))
            songs_to_sync = conn.execute(
                f"SELECT id, title, task_id, conversion_id_1, conversion_id_2, "
                f"prompt, lyrics FROM songs "
                f"WHERE id IN ({placeholders}) AND task_id IS NOT NULL "
                f"AND task_id != ''",
                self.song_ids,
            ).fetchall()
        else:
            songs_to_sync = conn.execute(
                "SELECT id, title, task_id, conversion_id_1, conversion_id_2, "
                "prompt, lyrics FROM songs "
                "WHERE task_id IS NOT NULL AND task_id != '' "
                "AND (prompt IS NULL OR prompt = '' "
                "     OR lyrics IS NULL OR lyrics = '')"
            ).fetchall()

        if not songs_to_sync:
            self.progress.emit("No songs need syncing")
            conn.close()
            self.finished.emit(0)
            return

        # Build lookup: any known ID -> {db_id, title, has_prompt, has_lyrics}
        need_sync = {}
        for row in songs_to_sync:
            info = {
                "db_id": row["id"],
                "title": row["title"],
                "has_prompt": bool(row["prompt"]),
                "has_lyrics": bool(row["lyrics"]),
            }
            # Index by task_id, conversion_id_1, and conversion_id_2
            need_sync[row["task_id"]] = info
            if row["conversion_id_1"]:
                need_sync[row["conversion_id_1"]] = info
            if row["conversion_id_2"]:
                need_sync[row["conversion_id_2"]] = info

        self.progress.emit(
            f"Syncing details for {len(songs_to_sync)} song(s)..."
        )
        logger.info(f"SongDetailSyncer: {len(songs_to_sync)} songs to sync")

        # Open browser and use the lalals backend API
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
            from automation.browser_profiles import get_profile_path
            profile_dir = get_profile_path("lalals")

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

            from automation.lalals_api import LalalsApi, LalalsApiError, PRODUCE_URL
            api = LalalsApi(page)

            self.progress.emit("Connecting to lalals.com...")
            page.goto(PRODUCE_URL, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            if not api.is_logged_in():
                self.error.emit(
                    "Not logged in to lalals.com — log in via the Library tab first."
                )
                self.finished.emit(0)
                return

            # Fetch all projects via the /api/backend proxy (cookie auth)
            api_details = {}  # db_id -> {prompt, lyrics}
            self.progress.emit("Fetching projects from API...")
            total_fetched = 0
            try:
                for item in api.iter_projects(stop_flag=lambda: self._stop_flag):
                    self._match_item(item, need_sync, api_details)
                    total_fetched += 1
                    if total_fetched % 50 == 0:
                        self.progress.emit(
                            f"Fetching projects... {total_fetched} scanned, "
                            f"{len(api_details)} matched"
                        )
            except LalalsApiError as e:
                logger.warning(f"Projects fetch failed: {e}")
                self.error.emit(f"Could not fetch lalals history: {e}")

            # The list has no plain lyrics — pull lyrics_output from detail
            need_lyrics = {d["_pid"]: db_id for db_id, d in api_details.items()
                           if not d.get("lyrics") and d.get("_pid")}
            if need_lyrics and not self._stop_flag:
                self.progress.emit(f"Fetching lyrics for {len(need_lyrics)} song(s)...")
                details = api.get_projects_bulk(
                    list(need_lyrics), stop_flag=lambda: self._stop_flag,
                )
                for pid, detail in details.items():
                    api_details[need_lyrics[pid]]["lyrics"] = (
                        detail.get("lyrics_output") or detail.get("lyrics_input") or ""
                    )

            logger.info(
                f"SongDetailSyncer: scanned {total_fetched} projects, "
                f"matched {len(api_details)}"
            )

            # Update DB with extracted data
            self.progress.emit(
                f"Updating {len(api_details)} song(s) with prompt/lyrics..."
            )

            for db_id, details in api_details.items():
                if self._stop_flag:
                    break

                title = details.get("title", "?")

                set_parts = []
                vals = []

                # Only update fields that are currently empty
                # unless this was an explicit single-song sync
                if details.get("prompt") and (
                    not details["has_prompt"] or self.song_ids
                ):
                    set_parts.append("prompt=?")
                    vals.append(details["prompt"])

                if details.get("lyrics") and (
                    not details["has_lyrics"] or self.song_ids
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

    def _match_item(self, item, need_sync, api_details):
        """Check if a lalals project item matches any song needing sync.

        Args:
            item: Dict from the user/{uid}/projects response.
            need_sync: Dict mapping known IDs to song info.
            api_details: Output dict mapping db_id to extracted details.
        """
        qt = item.get("queue_task") or {}
        ip = qt.get("input_payload") or {} if isinstance(qt, dict) else {}
        if not isinstance(ip, dict):
            ip = {}

        lyrics = ip.get("lyrics", "")
        prompt = ip.get("prompt", "")
        if not (lyrics or prompt):
            return

        # Collect all candidate IDs from this item
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
        # Also check top-level task_id
        task_id = ""
        op = qt.get("output_payload") or {} if isinstance(qt, dict) else {}
        if isinstance(op, dict):
            task_id = op.get("taskId", "")
        if task_id:
            candidate_ids.add(task_id)

        for cid in candidate_ids:
            if cid in need_sync:
                info = need_sync[cid]
                db_id = info["db_id"]
                if db_id not in api_details:
                    api_details[db_id] = {
                        "_pid": pid,
                        "prompt": prompt,
                        "lyrics": lyrics,
                        "title": info["title"],
                        "has_prompt": info["has_prompt"],
                        "has_lyrics": info["has_lyrics"],
                    }

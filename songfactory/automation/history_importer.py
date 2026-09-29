"""History importer for lalals.com — discovers and imports past generations.

Opens Playwright with the persistent profile, navigates to lalals.com,
clicks the "Home" sidebar button to reach the workspace showing
"Latest generations", then scrolls down to lazy-load all past tracks
while intercepting every API response that carries song data.

For tracks where API interception doesn't yield download URLs, falls
back to the three-dot menu → Download → Full Song DOM workflow.

Usage from code:
    worker = HistoryImportWorker(db_path, config)
    worker.song_found.connect(on_song_found)
    worker.import_finished.connect(on_done)
    worker.start()
"""

import logging
import re
import time
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger("songfactory.automation")

LOG_DIR = Path.home() / ".songfactory"


class HistoryImportWorker(QThread):
    """Background worker that discovers and imports songs from lalals.com history."""

    # Signals
    song_found = pyqtSignal(dict)          # raw song data dict
    song_imported = pyqtSignal(int, str)   # song_id, title
    import_error = pyqtSignal(str)         # error message
    import_finished = pyqtSignal(int)      # total imported count
    progress_update = pyqtSignal(str)      # status message

    def __init__(self, db_path: str, config: dict, selected_task_ids: list = None,
                 pre_discovered: list = None, profile_mode: bool = False,
                 track_types: list = None, extract_lyrics: bool = True):
        """
        Args:
            db_path: Path to SQLite database.
            config: Dict with download_dir, browser_path, etc.
            selected_task_ids: If set, only import these task_ids.
                               If None, discover all (import phase selects).
            pre_discovered: List of already-discovered song dicts from a
                           previous discovery pass.  When provided with
                           selected_task_ids, the worker skips browser
                           discovery and imports directly from this data.
            profile_mode: If True, use profile page scraper instead of
                         the projects API.
            track_types: List of track labels to download, e.g.
                        ["Full Song", "Vocals", "Instrumental"].
                        Defaults to ["Full Song"] if None.
            extract_lyrics: Whether to extract lyrics from song detail views
                           (profile mode only).
        """
        super().__init__()
        self.db_path = db_path
        self.config = config
        self.selected_task_ids = selected_task_ids
        self.pre_discovered = pre_discovered or []
        self.profile_mode = profile_mode
        self.track_types = track_types or ["Full Song"]
        self.extract_lyrics = extract_lyrics
        self._stop_flag = False
        self._captured_user_id = None

    def stop(self):
        """Signal graceful stop."""
        self._stop_flag = True

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _click_home_button(self, page):
        """Click the "Home" sidebar button to reach the workspace/history.

        The lalals.com sidebar has a "Home" link that navigates to the
        workspace page showing "Latest generations:".

        Returns True if a click was performed and the page changed.
        """
        strategies = [
            # Exact text match for "Home" in sidebar nav
            lambda: page.locator('a:has-text("Home")').first,
            lambda: page.locator('button:has-text("Home")').first,
            lambda: page.locator('nav a:has-text("Home")').first,
            # Href-based
            lambda: page.locator('a[href="/"]').first,
            lambda: page.locator('a[href="/home"]').first,
            lambda: page.locator('a[href="/workspace"]').first,
            lambda: page.locator('a[href*="home"]').first,
            # Icon + text combos common in sidebars
            lambda: page.locator('[data-name="Home"]').first,
            lambda: page.locator('[data-testid="home"]').first,
            lambda: page.locator('[data-testid="nav-home"]').first,
            # SVG home icon parent
            lambda: page.locator('a:has(svg), button:has(svg)').filter(
                has_text="Home"
            ).first,
        ]

        for i, strategy in enumerate(strategies):
            try:
                loc = strategy()
                if loc.is_visible(timeout=2000):
                    text = ""
                    try:
                        text = (loc.text_content() or "")[:40]
                    except Exception:
                        pass
                    logger.info(f"Home button found via strategy {i}, text='{text}'")
                    loc.click()
                    page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue

        # Debug: log all visible sidebar/nav elements
        try:
            elements = page.evaluate("""
                () => {
                    const els = document.querySelectorAll(
                        'nav a, nav button, aside a, aside button, ' +
                        '[role="navigation"] a, [role="navigation"] button'
                    );
                    return Array.from(els)
                        .filter(el => el.offsetParent !== null)
                        .map(el => ({
                            tag: el.tagName,
                            text: (el.textContent || '').trim().slice(0, 60),
                            href: el.href || '',
                        }))
                        .slice(0, 30);
                }
            """)
            logger.info(f"Sidebar/nav elements ({len(elements)}):")
            for el in elements:
                logger.info(f"  <{el['tag']}> text='{el['text']}' href={el['href']}")
        except Exception:
            pass

        return False

    def _scrape_generation_cards(self, page):
        """Scrape song data directly from the DOM generation cards.

        When API interception doesn't capture data (e.g. already loaded
        before we attached the listener), we can read the visible cards.

        Returns a list of dicts with whatever info we can extract from
        the card elements.
        """
        cards = page.evaluate("""
            () => {
                // Look for the "Latest generations" section and its cards
                const results = [];
                // Try various container selectors
                const cards = document.querySelectorAll(
                    '[class*="generation"], [class*="track"], [class*="card"], ' +
                    '[class*="project"], [class*="item"]'
                );
                for (const card of cards) {
                    const text = (card.textContent || '').trim();
                    if (text.length < 5) continue;

                    // Try to extract title - usually the first heading or
                    // prominent text element
                    let title = '';
                    const headings = card.querySelectorAll('h1, h2, h3, h4, h5, h6, [class*="title"], [class*="name"]');
                    if (headings.length > 0) {
                        title = headings[0].textContent.trim();
                    }

                    // Extract any links that might contain track IDs
                    let trackId = '';
                    const links = card.querySelectorAll('a[href]');
                    for (const link of links) {
                        const href = link.href || '';
                        const match = href.match(/\\/track\\/([^/]+)/) ||
                                     href.match(/\\/project\\/([^/]+)/) ||
                                     href.match(/[?&]id=([^&]+)/);
                        if (match) {
                            trackId = match[1];
                            break;
                        }
                    }

                    // Extract type/version labels
                    let type = '';
                    const labels = card.querySelectorAll('[class*="label"], [class*="tag"], [class*="badge"]');
                    for (const label of labels) {
                        const lt = label.textContent.trim();
                        if (lt === 'Music' || lt === 'Lyrics' || lt.match(/Version \\d/)) {
                            type = lt;
                        }
                    }

                    if (title || trackId) {
                        results.push({
                            title: title,
                            id: trackId,
                            type: type,
                            fullText: text.slice(0, 200),
                        });
                    }
                }
                return results;
            }
        """)
        return cards or []

    def _scroll_to_load_all(self, page, discovered_count_fn, max_scrolls=50):
        """Scroll down repeatedly to trigger lazy-loading of history items.

        Stops when no new items are discovered after 3 consecutive scrolls.

        Args:
            page: Playwright page.
            discovered_count_fn: Callable returning current discovered count.
            max_scrolls: Safety limit.
        """
        no_new_count = 0

        for scroll_num in range(max_scrolls):
            if self._stop_flag:
                break

            count_before = discovered_count_fn()

            # Scroll window to bottom
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            # Also scroll any inner scrollable containers
            page.evaluate("""
                (() => {
                    const containers = document.querySelectorAll(
                        'main, [role="main"], [class*="content"], ' +
                        '[class*="scroll"], [class*="list"], [class*="feed"], ' +
                        '[class*="generation"], [class*="workspace"]'
                    );
                    for (const c of containers) {
                        if (c.scrollHeight > c.clientHeight + 10) {
                            c.scrollTop = c.scrollHeight;
                        }
                    }
                })()
            """)
            page.wait_for_timeout(1500)

            count_after = discovered_count_fn()
            new_items = count_after - count_before

            if new_items > 0:
                no_new_count = 0
                self.progress_update.emit(
                    f"Scrolling... found {count_after} song(s) so far"
                )
                logger.info(
                    f"Scroll {scroll_num + 1}: +{new_items} (total={count_after})"
                )
            else:
                no_new_count += 1
                if no_new_count >= 3:
                    logger.info("No new items after 3 scrolls, done loading")
                    break

    # ------------------------------------------------------------------
    # Profile page discovery
    # ------------------------------------------------------------------

    def _run_profile_discovery(self, page, add_fn):
        """Discover songs via the profile page scraper.

        Args:
            page: Playwright page with active session.
            add_fn: Callable(item_dict) to register each discovered song.
        """
        from automation.profile_scraper import ProfileScraper

        username = self.config.get("lalals_username", "").strip()
        if not username:
            # Try to auto-detect: navigate to lalals.com to access localStorage
            try:
                self.progress_update.emit("Detecting username from browser session...")
                page.goto("https://lalals.com", wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                username = page.evaluate("""
                    () => {
                        const u = localStorage.getItem('lalals-username')
                                || localStorage.getItem('username');
                        return u || '';
                    }
                """) or ""
                if username:
                    logger.info(f"Auto-detected username from localStorage: {username}")
            except Exception:
                pass
        if not username:
            self.import_error.emit(
                "No lalals.com username configured. "
                "Set it in Settings > Lalals.com Settings > Lalals.com Username."
            )
            return

        scraper = ProfileScraper(
            page, username,
            stop_flag_fn=lambda: self._stop_flag,
            progress_fn=lambda msg: self.progress_update.emit(msg),
        )

        if not scraper.navigate_to_profile():
            self.import_error.emit(
                "Could not load profile page. Check that you are logged in "
                "and the username is correct."
            )
            return

        songs = scraper.discover_songs()
        for song in songs:
            if self._stop_flag:
                break
            # Normalize to our standard format, passing through all data
            normalized = {
                "id": song.get("id", ""),
                "task_id": song.get("id", ""),
                "title": song.get("title", ""),
                "status": song.get("status", ""),
                "audio_url_1": song.get("audio_url_1") or song.get("track_url", ""),
                "track_url": song.get("track_url", ""),
                "music_style": song.get("music_style", ""),
                "created_at": song.get("created_at", ""),
                "prompt": song.get("prompt", ""),
                "lyrics": song.get("lyrics", ""),
                "conversionType": song.get("conversionType", ""),
                "conversion_id_1": song.get("conversion_id_1", ""),
                "conversion_id_2": song.get("conversion_id_2", ""),
                "_profile_index": song.get("index", 0),
            }
            add_fn(normalized)

    def _import_songs_from_profile(self, discovered, selected_task_ids, conn, dm, page):
        """Import songs discovered via profile page — downloads and lyrics.

        Args:
            discovered: List of discovered song dicts.
            selected_task_ids: List of task_ids the user selected.
            conn: SQLite connection.
            dm: DownloadManager instance.
            page: Playwright page.

        Returns:
            Number of songs imported/updated.
        """
        from automation.profile_scraper import ProfileScraper

        username = self.config.get("lalals_username", "")
        scraper = ProfileScraper(
            page, username,
            stop_flag_fn=lambda: self._stop_flag,
            progress_fn=lambda msg: self.progress_update.emit(msg),
        )

        imported_count = 0
        selected_set = set(selected_task_ids)

        songs_to_import = [
            s for s in discovered
            if (s.get("task_id") or s.get("id", "")) in selected_set
        ]

        for item in songs_to_import:
            if self._stop_flag:
                break

            task_id = item.get("task_id") or item.get("id", "")
            title = item.get("title") or f"Imported-{task_id[:8]}"

            self.progress_update.emit(f"Importing: {title}")

            # Check existing record — by task_id, conversion_id, then title
            existing = conn.execute(
                "SELECT id, status, title FROM songs WHERE task_id=?", (task_id,)
            ).fetchone()
            if not existing:
                existing = conn.execute(
                    "SELECT id, status, title FROM songs "
                    "WHERE conversion_id_1=? OR conversion_id_2=?",
                    (task_id, task_id),
                ).fetchone()
            if not existing and len(title) > 8:
                existing = conn.execute(
                    "SELECT id, status, title FROM songs WHERE LOWER(title)=LOWER(?)",
                    (title,)
                ).fetchone()

            # Extract lyrics if enabled
            lyrics = ""
            if self.extract_lyrics:
                self.progress_update.emit(f"Extracting lyrics: {title}")
                lyrics = scraper.extract_lyrics(title)

            # Download requested track types via 3-dot menu
            self.progress_update.emit(f"Downloading tracks: {title}")
            track_paths = scraper.download_all_tracks(title, dm, self.track_types)

            file_path_1 = track_paths.get("full_song", "")
            file_path_vocals = track_paths.get("vocals", "")
            file_path_instrumental = track_paths.get("instrumental", "")

            status = "completed" if (file_path_1 or file_path_vocals or file_path_instrumental) else "imported"

            if existing:
                # Update existing record
                set_parts = ["status=?", "updated_at=CURRENT_TIMESTAMP"]
                vals = [status]

                if file_path_1:
                    set_parts.append("file_path_1=?")
                    vals.append(file_path_1)
                if file_path_vocals:
                    set_parts.append("file_path_vocals=?")
                    vals.append(file_path_vocals)
                if file_path_instrumental:
                    set_parts.append("file_path_instrumental=?")
                    vals.append(file_path_instrumental)
                if lyrics:
                    set_parts.append("lyrics=?")
                    vals.append(lyrics)
                if task_id:
                    set_parts.append("task_id=?")
                    vals.append(task_id)

                vals.append(existing["id"])
                conn.execute(
                    f"UPDATE songs SET {', '.join(set_parts)} WHERE id=?",
                    vals
                )
                conn.commit()
                imported_count += 1
                self.song_imported.emit(existing["id"], title)
                logger.info(f"Updated existing id={existing['id']}: {title}")
            else:
                # Insert new record
                cursor = conn.execute(
                    """INSERT INTO songs
                       (title, genre_id, genre_label, prompt, lyrics, status,
                        file_path_1, file_path_vocals, file_path_instrumental,
                        task_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        title, None, "", "", lyrics, status,
                        file_path_1, file_path_vocals, file_path_instrumental,
                        task_id,
                    )
                )
                conn.commit()
                song_id = cursor.lastrowid
                imported_count += 1
                self.song_imported.emit(song_id, title)
                logger.info(f"Imported new: {title} (id={song_id})")

        return imported_count

    # ------------------------------------------------------------------
    # lalals.com backend API helpers (/api/backend proxy)
    # ------------------------------------------------------------------

    def _extract_user_id(self, page):
        """Extract the user UUID for the logged-in session.

        Tries: (1) backend session endpoint (authoritative), (2) captured
        from URL interception, (3) DB config, (4) JS state /
        localStorage/sessionStorage.
        Stores captured user_id in DB config for future reuse.
        """
        from automation.lalals_api import LalalsApi, LalalsApiError
        try:
            user = LalalsApi(page).get_session_user()
            if user:
                self._captured_user_id = str(user["id"])
                self._store_user_id(self._captured_user_id)
                logger.info(f"User ID from session: {self._captured_user_id}")
                return self._captured_user_id
        except LalalsApiError as e:
            logger.warning(f"Session lookup failed: {e}")

        if self._captured_user_id:
            self._store_user_id(self._captured_user_id)
            return self._captured_user_id

        # Try DB config (stored from previous successful session)
        try:
            import sqlite3 as _sql
            _conn = _sql.connect(self.db_path)
            row = _conn.execute(
                "SELECT value FROM config WHERE key='lalals_user_id'"
            ).fetchone()
            _conn.close()
            if row and row[0]:
                logger.info(f"Using stored user_id from DB config: {row[0]}")
                self._captured_user_id = row[0]
                return row[0]
        except Exception:
            pass

        # Try JS state: __NEXT_DATA__, cookies, localStorage, etc.
        user_id = page.evaluate("""
        () => {
            // __NEXT_DATA__ (Next.js pages)
            const nd = document.getElementById('__NEXT_DATA__');
            if (nd) {
                try {
                    const d = JSON.parse(nd.textContent);
                    const uid = (d.props && d.props.pageProps && d.props.pageProps.user && d.props.pageProps.user.id)
                             || (d.props && d.props.pageProps && d.props.pageProps.userId)
                             || (d.props && d.props.user && d.props.user.id);
                    if (uid) return uid;
                } catch(e) {}
            }
            // Common global patterns
            try {
                if (window.__user__ && window.__user__.id) return window.__user__.id;
            } catch(e) {}
            // localStorage / sessionStorage
            try {
                for (const store of [localStorage, sessionStorage]) {
                    for (let i = 0; i < store.length; i++) {
                        const key = store.key(i);
                        const val = store.getItem(key);
                        if (val && val.match && val.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/)) {
                            if (key.toLowerCase().includes('user') || key.toLowerCase().includes('uid')) {
                                return val;
                            }
                        }
                        // Try parsing JSON values
                        try {
                            const parsed = JSON.parse(val);
                            if (parsed && typeof parsed === 'object') {
                                for (const k of ['id', 'userId', 'user_id', 'uid']) {
                                    if (parsed[k] && typeof parsed[k] === 'string' && parsed[k].length > 30) {
                                        return parsed[k];
                                    }
                                }
                            }
                        } catch(e) {}
                    }
                }
            } catch(e) {}
            // Cookies
            const cookies = document.cookie.split(';');
            for (const c of cookies) {
                const parts = c.trim().split('=');
                if (parts[0] === 'user_id' || parts[0] === 'userId') return parts[1];
            }
            return null;
        }
        """)
        if user_id:
            self._captured_user_id = user_id
            self._store_user_id(user_id)
            logger.info(f"Extracted user_id from JS state: {user_id}")
            return user_id

        return None

    def _store_user_id(self, user_id):
        """Persist user_id to DB config for future sessions."""
        try:
            import sqlite3 as _sql
            _conn = _sql.connect(self.db_path)
            _conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES ('lalals_user_id', ?)",
                (user_id,)
            )
            _conn.commit()
            _conn.close()
        except Exception as e:
            logger.debug(f"Failed to store user_id: {e}")

    def _fetch_projects_via_api(self, page, add_fn):
        """Fetch every project in the user's lalals history.

        Uses ``POST /api/backend/user/{uid}/projects`` with the session
        cookies of *page* (see ``LalalsApi.iter_projects``).  Each project is
        one generated version and becomes one discovered song.

        Args:
            page: Playwright page with active lalals.com session.
            add_fn: Callable(item_dict) to register each discovered song.
        """
        from automation.lalals_api import LalalsApi, LalalsApiError

        api = LalalsApi(page)
        total_found = 0
        skipped = 0
        try:
            for item in api.iter_projects(stop_flag=lambda: self._stop_flag):
                song = self._normalize_project_item(item)
                if not song:
                    skipped += 1
                    continue
                add_fn(song)
                total_found += 1
                if total_found % 25 == 0:
                    self.progress_update.emit(
                        f"Fetching projects... {total_found} songs found so far"
                    )
        except LalalsApiError as e:
            logger.warning(f"Project list fetch failed: {e}")
            self.import_error.emit(f"Could not fetch lalals history: {e}")

        logger.info(
            f"projects API: {total_found} songs "
            f"(skipped {skipped} non-song/failed entries)"
        )

    def _scrape_project_cards(self, page):
        """Scrape data-project-id elements from the DOM.

        Returns a list of normalized song dicts with id and title.
        """
        cards = page.evaluate("""
        () => {
            const elements = document.querySelectorAll('[data-project-id]');
            return Array.from(elements).map(el => ({
                id: el.getAttribute('data-project-id'),
                text: (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 200),
            }));
        }
        """)

        results = []
        seen = set()
        for card in (cards or []):
            pid = card.get("id", "")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            text = card.get("text", "")
            # First meaningful chunk of text is usually the title
            title = text.split("  ")[0].strip()[:80] if text else f"Project-{pid[:8]}"
            results.append({
                "id": pid,
                "task_id": pid,
                "title": title,
            })
        return results

    def _fetch_project_detail(self, page, project_id):
        """Fetch full project detail (incl. ``lyrics_output``) or None."""
        from automation.lalals_api import LalalsApi, LalalsApiError
        try:
            detail = LalalsApi(page).get_project(project_id)
        except LalalsApiError as e:
            logger.debug(f"Detail fetch failed for {project_id}: {e}")
            return None
        return detail if isinstance(detail, dict) else None

    @staticmethod
    def _normalize_project_item(item):
        """Normalize one lalals projects-list entry into a song dict.

        Every generation creates two projects ("Version 1"/"Version 2"),
        each with its own id — which is also its conversion id / S3 key,
        so it matches ``task_id``/``conversion_id_*`` of earlier imports.

        Returns:
            Song dict, or None for failed runs and non-song entries
            (e.g. LYRICS_GENERATION).
        """
        from automation.lalals_api import (
            LEGACY_S3_BASE, project_audio_url, version_number,
        )

        pid = item.get("id", "")
        conv_type = item.get("conversionType") or ""
        status = item.get("conversion_status") or item.get("status") or ""
        # Only finished songs — in-progress ones have no audio yet and
        # would be imported as broken duplicates of the queued song.
        if not pid or conv_type not in ("", "MUSIC_AI") or status != "SUCCESS":
            return None

        qt = item.get("queue_task") or {}
        ip = qt.get("input_payload") if isinstance(qt, dict) else None
        ip = ip if isinstance(ip, dict) else {}

        base_title = (item.get("track_name") or item.get("name") or "").strip()
        if len(base_title) > 80:
            # lalals falls back to the whole prompt (sometimes with lyrics)
            base_title = base_title.splitlines()[0].strip()[:60].rstrip() + "…"
        ver = version_number(item)
        title = f"{base_title} (V{ver})" if base_title else f"V{ver}-{pid[:8]}"
        url = project_audio_url(item)
        if not url and status == "SUCCESS":
            url = f"{LEGACY_S3_BASE}/{pid}/{pid}.mp3"

        return {
            "id": pid,
            "task_id": pid,
            "title": title,
            "status": status,
            "audio_url_1": url,
            "track_url": url,
            "music_style": item.get("music_style") or "",
            "created_at": item.get("date_added") or item.get("created_at") or "",
            "prompt": ip.get("prompt") or item.get("prompt") or "",
            # list entries carry no plain lyrics; filled from detail later
            "lyrics": item.get("lyrics_output") or ip.get("lyrics") or "",
            "lyrics_timestamped": item.get("lyrics_timestamped") or "",
            "conversion_id_1": pid,
            "conversion_id_2": "",
            "conversionType": conv_type,
            "cover_image": item.get("cover_image") or "",
            "_project_id": pid,
        }

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run(self):
        """Main: open browser, navigate to history, intercept API, import songs."""
        import sqlite3
        from automation.lalals_driver import LalalsDriver
        from automation.download_manager import DownloadManager

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        download_dir = self.config.get(
            'download_dir', str(Path.home() / "Music" / "SongFactory")
        )
        dm = DownloadManager(download_dir)

        # If we have pre-discovered data and selected task_ids, skip
        # the entire browser discovery phase and go straight to import.
        if self.pre_discovered and self.selected_task_ids:
            imported_count = self._import_from_data(
                self.pre_discovered, self.selected_task_ids, conn, dm
            )
            conn.close()
            self.progress_update.emit(f"Import complete: {imported_count} song(s)")
            self.import_finished.emit(imported_count)
            return

        # Dedup set and discovered list
        seen_ids = set()
        discovered = []

        def _add_item(item, emit=True):
            """Deduplicate and track a discovered song item."""
            tid = (
                item.get("task_id")
                or item.get("taskId")
                or item.get("id", "")
            )
            if not tid or tid in seen_ids:
                return
            seen_ids.add(tid)
            discovered.append(item)
            if emit:
                self.song_found.emit(item)

        playwright_mod = None
        context = None
        xvfb = None
        try:
            from playwright.sync_api import sync_playwright

            # Use Xvfb if available, otherwise fall back to headless mode
            use_xvfb = self.config.get('use_xvfb', True)
            headless = True  # default to headless (no visible window)
            if use_xvfb:
                try:
                    from automation.xvfb_manager import XvfbManager
                    if XvfbManager.is_available():
                        xvfb = XvfbManager()
                        xvfb.start()
                        headless = False  # Xvfb provides a virtual display
                        logger.info("Xvfb started for history import")
                    else:
                        logger.info("Xvfb not available, using headless mode")
                except Exception as e:
                    logger.warning(f"Xvfb error, using headless mode: {e}")

            playwright_mod = sync_playwright().start()

            from automation.browser_profiles import get_profile_path
            profile_dir = get_profile_path("lalals")
            launch_args = {
                'headless': headless,
                'accept_downloads': True,
                'viewport': {'width': 1280, 'height': 900},
                'args': ['--disable-blink-features=AutomationControlled'],
            }

            browser_path = self.config.get('browser_path')
            if browser_path:
                launch_args['executable_path'] = browser_path

            try:
                context = playwright_mod.chromium.launch_persistent_context(
                    profile_dir, channel='chrome', **launch_args
                )
            except Exception:
                context = playwright_mod.chromium.launch_persistent_context(
                    profile_dir, **launch_args
                )

            page = context.pages[0] if context.pages else context.new_page()

            if self.profile_mode:
                # ---- Profile mode: let ProfileScraper handle everything ----
                # No competing on_response handler; no homepage navigation.
                # The ProfileScraper navigates directly to the profile page
                # and handles its own API interception + auth check.
                self._run_profile_discovery(page, _add_item)

                self.progress_update.emit(
                    f"Discovery complete: {len(discovered)} song(s) found"
                )
                logger.info(f"Profile discovery: found {len(discovered)} unique songs")

                # Discovery-only mode → stop here
                if self.selected_task_ids is None:
                    self.import_finished.emit(0)
                    return

                # Import via profile scraper (3-dot downloads, lyrics)
                imported_count = self._import_songs_from_profile(
                    discovered, self.selected_task_ids, conn, dm, page
                )
            else:
                # ---- API mode: /api/backend projects list ----
                from automation.lalals_api import LalalsApi, PRODUCE_URL

                self.progress_update.emit("Navigating to lalals.com...")
                page.goto(PRODUCE_URL, wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

                if not LalalsApi(page).is_logged_in():
                    self.import_error.emit(
                        "Not logged in — please log in to lalals.com first "
                        "(use the 'Login to Lalals' button in the Library tab)."
                    )
                    self.import_finished.emit(0)
                    return

                # ---- Step 2: Fetch the full project history ----
                self.progress_update.emit("Fetching project list from lalals...")
                user_id = self._extract_user_id(page)
                if user_id:
                    logger.info(f"User ID: {user_id}")
                    # Emit after lyrics are filled in (step 3): cross-thread
                    # signals may deliver a copy of the dict to the dialog
                    self._fetch_projects_via_api(
                        page, lambda it: _add_item(it, emit=False)
                    )
                else:
                    logger.warning("Could not extract user_id — cannot fetch projects")
                    self.import_error.emit(
                        "Could not determine your user ID. "
                        "Try logging in again via the Library tab."
                    )

                # ---- Step 3: Fill lyrics / missing URLs from project detail ----
                # The list endpoint has no plain lyrics; the detail endpoint
                # has lyrics_output (generated) / lyrics_input (typed).
                need_detail = [
                    song["_project_id"] for song in discovered
                    if song.get("_project_id") and (
                        (self.extract_lyrics and not song.get("lyrics"))
                        or not song.get("track_url")
                    )
                ]
                if need_detail:
                    from automation.lalals_api import LalalsApi, project_audio_url
                    self.progress_update.emit(
                        f"Fetching lyrics/details for {len(need_detail)} song(s)..."
                    )
                    details = LalalsApi(page).get_projects_bulk(
                        need_detail,
                        progress_fn=lambda done, total: self.progress_update.emit(
                            f"Fetching lyrics/details... {done}/{total}"
                        ),
                        stop_flag=lambda: self._stop_flag,
                    )
                    for song in discovered:
                        detail = details.get(song.get("_project_id"))
                        if not detail:
                            continue
                        if not song.get("lyrics"):
                            song["lyrics"] = (detail.get("lyrics_output")
                                              or detail.get("lyrics_input") or "")
                        if not song.get("prompt"):
                            song["prompt"] = detail.get("prompt") or ""
                        if not song.get("track_url"):
                            url = project_audio_url(detail)
                            song["track_url"] = song["audio_url_1"] = url
                        if detail.get("audio_length_seconds"):
                            song["duration"] = detail["audio_length_seconds"]
                    logger.info(
                        f"Project details: {len(details)}/{len(need_detail)} fetched"
                    )

                for song in discovered:
                    self.song_found.emit(song)

                self.progress_update.emit(
                    f"Discovery complete: {len(discovered)} song(s) found"
                )
                logger.info(f"History import: discovered {len(discovered)} unique songs")

                # ---- Discovery-only mode → stop here ----
                if self.selected_task_ids is None:
                    self.import_finished.emit(0)
                    return

                # ---- Step 6: Import selected songs ----
                imported_count = self._import_songs(
                    discovered, self.selected_task_ids, conn, dm, page
                )

        except Exception as e:
            error_msg = f"History import error: {e}"
            logger.error(error_msg)
            self.import_error.emit(error_msg)
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

        count = locals().get("imported_count", 0)
        self.progress_update.emit(f"Import complete: {count} song(s)")
        self.import_finished.emit(count)

    # ------------------------------------------------------------------
    # Import logic
    # ------------------------------------------------------------------

    def _import_songs(self, discovered, selected_task_ids, conn, dm, page=None):
        """Import selected songs, downloading audio files.

        Matching order for each discovered song:
        1. Match by task_id to existing DB record
        2. Match by title (case-insensitive) to existing DB record
        3. Insert as new record

        Returns the number of songs imported/linked.
        """
        from automation.lalals_driver import LalalsDriver

        imported_count = 0
        selected_set = set(selected_task_ids)

        songs_to_import = [
            s for s in discovered
            if (s.get("task_id") or s.get("taskId") or s.get("id", ""))
               in selected_set
        ]

        for item in songs_to_import:
            if self._stop_flag:
                break

            task_id = (
                item.get("task_id")
                or item.get("taskId")
                or item.get("id", "")
            )

            title = (
                item.get("title")
                or item.get("prompt", "")[:60]
                or f"Imported-{task_id[:8]}"
            )

            # Check if already in DB — by task_id, conversion_id, then title
            existing = conn.execute(
                "SELECT id, status, title FROM songs WHERE task_id=?", (task_id,)
            ).fetchone()

            if not existing:
                # Try by conversion_id
                existing = conn.execute(
                    "SELECT id, status, title FROM songs "
                    "WHERE conversion_id_1=? OR conversion_id_2=?",
                    (task_id, task_id),
                ).fetchone()

            if not existing and len(title) > 8:
                # Try matching by title — skip short/generic titles
                existing = conn.execute(
                    "SELECT id, status, title FROM songs WHERE LOWER(title)=LOWER(?)",
                    (title,)
                ).fetchone()
                if existing:
                    logger.info(
                        f"Title match: '{title}' -> DB id={existing['id']} "
                        f"('{existing['title']}')"
                    )

            if existing:
                if existing["status"] == "completed" and conn.execute(
                    "SELECT file_path_1 FROM songs WHERE id=?", (existing["id"],)
                ).fetchone()[0]:
                    logger.info(f"Skipping already-completed with files: task_id={task_id}")
                    continue
                logger.info(
                    f"Found existing record id={existing['id']} for "
                    f"task_id={task_id}, will link/update"
                )

            # Discovery data from the lalals projects API is authoritative
            # (the MusicGPT byId endpoint returns 404 for every task).
            metadata = {}

            if not metadata.get("audio_url_1"):
                # Fall back to discovery data
                metadata = LalalsDriver.extract_metadata(item)

            # Extract prompt + lyrics — may be top-level (normalized)
            # or nested in queue_task.input_payload (raw intercepted)
            _qt = item.get("queue_task") or {}
            _ip = _qt.get("input_payload") or {} if isinstance(_qt, dict) else {}
            if not isinstance(_ip, dict):
                _ip = {}
            prompt = (
                item.get("prompt")
                or _ip.get("prompt")
                or item.get("description")
                or ""
            )
            lyrics = item.get("lyrics") or _ip.get("lyrics") or ""
            style = metadata.get("music_style") or ""

            self.progress_update.emit(f"Importing: {title}")

            # Download audio files via direct URLs (MP3 + WAV)
            file_path_1 = ""
            file_path_2 = ""
            for version in (1, 2):
                url = metadata.get(f"audio_url_{version}")
                if url:
                    # Download MP3
                    try:
                        path = dm.save_from_url(url, title, version)
                        if version == 1:
                            file_path_1 = str(path)
                        else:
                            file_path_2 = str(path)
                    except Exception as e:
                        logger.warning(
                            f"URL download failed for {title} v{version}: {e}"
                        )
                    # Also try the WAV beside the MP3 (same S3 key)
                    if url.endswith(".mp3"):
                        wav_url = url[:-4] + ".wav"
                        try:
                            dm.save_from_url(wav_url, title, version)
                            logger.info(f"Downloaded WAV for {title} v{version}")
                        except Exception as e:
                            logger.debug(
                                f"WAV download failed for {title} v{version}: {e}"
                            )

            # If no files downloaded and we have a browser page, try DOM
            if not file_path_1 and page:
                dom_path = self._download_via_dom(page, title, dm)
                if dom_path:
                    file_path_1 = str(dom_path)

            status = "completed" if file_path_1 else "imported"

            if existing:
                # Update existing record (link to creating entity)
                set_parts = [
                    "status=?", "file_path_1=?", "file_path_2=?",
                    "updated_at=CURRENT_TIMESTAMP",
                ]
                vals = [status, file_path_1, file_path_2]
                for col in ("task_id", "conversion_id_1", "conversion_id_2",
                            "audio_url_1", "audio_url_2", "music_style",
                            "duration_seconds", "file_format", "voice_used",
                            "lalals_created_at", "lyrics_timestamped"):
                    v = metadata.get(col)
                    if v is not None:
                        set_parts.append(f"{col}=?")
                        vals.append(v)
                vals.append(existing["id"])
                conn.execute(
                    f"UPDATE songs SET {', '.join(set_parts)} WHERE id=?",
                    vals
                )
                conn.commit()
                imported_count += 1
                self.song_imported.emit(existing["id"], title)
                logger.info(f"Linked existing id={existing['id']}: {title}")
            else:
                # Insert new record
                cursor = conn.execute(
                    """INSERT INTO songs
                       (title, genre_id, genre_label, prompt, lyrics, status,
                        file_path_1, file_path_2, task_id, conversion_id_1,
                        conversion_id_2, audio_url_1, audio_url_2, music_style,
                        duration_seconds, file_format, voice_used,
                        lalals_created_at, lyrics_timestamped)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        title, None, style, prompt, lyrics, status,
                        file_path_1, file_path_2,
                        metadata.get("task_id"),
                        metadata.get("conversion_id_1"),
                        metadata.get("conversion_id_2"),
                        metadata.get("audio_url_1"),
                        metadata.get("audio_url_2"),
                        metadata.get("music_style"),
                        metadata.get("duration_seconds"),
                        metadata.get("file_format"),
                        metadata.get("voice_used"),
                        metadata.get("lalals_created_at"),
                        metadata.get("lyrics_timestamped"),
                    )
                )
                conn.commit()
                song_id = cursor.lastrowid
                imported_count += 1
                self.song_imported.emit(song_id, title)
                logger.info(f"Imported new: {title} (id={song_id})")

        return imported_count

    def _download_via_dom(self, page, song_title, dm):
        """Try to download a song via the three-dot menu → Download → Full Song.

        This is the fallback when API URLs aren't available.  Finds the card
        for the given song title, clicks its three-dot menu, then clicks
        Download → Full Song.

        Args:
            page: Playwright page (on the Home/workspace page).
            song_title: Title to search for in the card list.
            dm: DownloadManager instance.

        Returns:
            Path to saved file, or None if it failed.
        """
        try:
            # Find the three-dot menu button near the matching title
            # Cards typically have the title as text and a nearby "..." button
            card = page.locator(f'text="{song_title}"').first
            if not card.is_visible(timeout=2000):
                logger.debug(f"Card not visible for '{song_title}'")
                return None

            # The three-dot button is usually a sibling or nearby element
            # Try to find it relative to the card
            menu_btn = card.locator('xpath=ancestor::*[position() <= 5]//button[contains(@class, "menu") or contains(@class, "dot") or contains(@class, "more")]').first
            if not menu_btn.is_visible(timeout=1000):
                # Broader: any button near this text that looks like a menu
                menu_btn = card.locator('xpath=ancestor::*[position() <= 5]//button').last
            if not menu_btn.is_visible(timeout=1000):
                logger.debug(f"Menu button not found for '{song_title}'")
                return None

            menu_btn.click()
            page.wait_for_timeout(1000)

            # Click "Download" in the popup menu
            download_item = page.locator('text="Download"').first
            if not download_item.is_visible(timeout=2000):
                logger.debug("Download menu item not visible")
                page.keyboard.press("Escape")
                return None
            download_item.click()
            page.wait_for_timeout(1000)

            # Click "Full Song" in the submenu
            full_song = page.locator('text="Full Song"').first
            if not full_song.is_visible(timeout=2000):
                logger.debug("Full Song submenu not visible")
                page.keyboard.press("Escape")
                return None

            # Expect a download
            with page.expect_download(timeout=30000) as dl_info:
                full_song.click()
            download = dl_info.value

            path = dm.save_playwright_download(download, song_title, 1)
            logger.info(f"DOM download succeeded for '{song_title}': {path}")
            return path

        except Exception as e:
            logger.debug(f"DOM download failed for '{song_title}': {e}")
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            return None

    # ------------------------------------------------------------------
    # Import from pre-discovered data (no browser needed)
    # ------------------------------------------------------------------

    def _import_from_data(self, songs_data, selected_task_ids, conn, dm):
        """Import songs from already-discovered data without opening a browser.

        Matching order for each discovered song:
        1. Match by task_id to existing DB record
        2. Match by title (case-insensitive) to existing DB record
        3. Insert as new record

        Args:
            songs_data: List of song dicts from the discovery phase.
            selected_task_ids: List of task_ids the user selected.
            conn: SQLite connection.
            dm: DownloadManager instance.

        Returns:
            Number of songs actually imported/linked.
        """
        from automation.lalals_driver import LalalsDriver

        imported_count = 0
        selected_set = set(selected_task_ids)

        def _tid(it):
            return it.get("task_id") or it.get("taskId") or it.get("id", "")

        to_import = [it for it in songs_data if _tid(it) in selected_set]
        total = len(to_import)

        for idx, item in enumerate(to_import, start=1):
            if self._stop_flag:
                break

            task_id = _tid(item)

            title = (
                item.get("title")
                or item.get("prompt", "")[:60]
                or f"Imported-{task_id[:8]}"
            )

            # Check if already in DB — by task_id, conversion_id, then title
            existing = conn.execute(
                "SELECT id, status, title FROM songs WHERE task_id=?", (task_id,)
            ).fetchone()

            if not existing:
                existing = conn.execute(
                    "SELECT id, status, title FROM songs "
                    "WHERE conversion_id_1=? OR conversion_id_2=?",
                    (task_id, task_id),
                ).fetchone()

            if not existing and len(title) > 8:
                existing = conn.execute(
                    "SELECT id, status, title FROM songs WHERE LOWER(title)=LOWER(?)",
                    (title,)
                ).fetchone()
                if existing:
                    logger.info(
                        f"Title match: '{title}' -> DB id={existing['id']} "
                        f"('{existing['title']}')"
                    )

            if existing:
                if existing["status"] == "completed" and conn.execute(
                    "SELECT file_path_1 FROM songs WHERE id=?", (existing["id"],)
                ).fetchone()[0]:
                    logger.info(f"Skipping already-completed with files: task_id={task_id}")
                    continue

            # Discovery data from the lalals projects API is authoritative
            # (the MusicGPT byId endpoint returns 404 for every task).
            metadata = {}

            if not metadata.get("audio_url_1"):
                metadata = LalalsDriver.extract_metadata(item)

            _qt2 = item.get("queue_task") or {}
            _ip2 = _qt2.get("input_payload") or {} if isinstance(_qt2, dict) else {}
            if not isinstance(_ip2, dict):
                _ip2 = {}
            prompt = (
                item.get("prompt")
                or _ip2.get("prompt")
                or item.get("description")
                or ""
            )
            lyrics = item.get("lyrics") or _ip2.get("lyrics") or ""
            style = metadata.get("music_style") or ""

            self.progress_update.emit(f"Importing ({idx}/{total}): {title}")

            # Download audio files
            file_path_1 = ""
            file_path_2 = ""
            for version in (1, 2):
                url = metadata.get(f"audio_url_{version}")
                if url:
                    try:
                        path = dm.save_from_url(url, title, version)
                        if version == 1:
                            file_path_1 = str(path)
                        else:
                            file_path_2 = str(path)
                    except Exception as e:
                        logger.warning(
                            f"Download failed for {title} v{version}: {e}"
                        )

            status = "completed" if file_path_1 else "imported"

            if existing:
                # Update existing record
                set_parts = [
                    "status=?", "file_path_1=?", "file_path_2=?",
                    "updated_at=CURRENT_TIMESTAMP",
                ]
                vals = [status, file_path_1, file_path_2]
                for col in ("task_id", "conversion_id_1", "conversion_id_2",
                            "audio_url_1", "audio_url_2", "music_style",
                            "duration_seconds", "file_format", "voice_used",
                            "lalals_created_at", "lyrics_timestamped"):
                    v = metadata.get(col)
                    if v is not None:
                        set_parts.append(f"{col}=?")
                        vals.append(v)
                vals.append(existing["id"])
                conn.execute(
                    f"UPDATE songs SET {', '.join(set_parts)} WHERE id=?",
                    vals
                )
                conn.commit()
                imported_count += 1
                self.song_imported.emit(existing["id"], title)
                logger.info(f"Linked existing id={existing['id']}: {title}")
            else:
                # Insert new record
                cursor = conn.execute(
                    """INSERT INTO songs
                       (title, genre_id, genre_label, prompt, lyrics, status,
                        file_path_1, file_path_2, task_id, conversion_id_1,
                        conversion_id_2, audio_url_1, audio_url_2, music_style,
                        duration_seconds, file_format, voice_used,
                        lalals_created_at, lyrics_timestamped)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        title, None, style, prompt, lyrics, status,
                        file_path_1, file_path_2,
                        metadata.get("task_id"),
                        metadata.get("conversion_id_1"),
                        metadata.get("conversion_id_2"),
                        metadata.get("audio_url_1"),
                        metadata.get("audio_url_2"),
                        metadata.get("music_style"),
                        metadata.get("duration_seconds"),
                        metadata.get("file_format"),
                        metadata.get("voice_used"),
                        metadata.get("lalals_created_at"),
                        metadata.get("lyrics_timestamped"),
                    )
                )
                conn.commit()
                song_id = cursor.lastrowid
                imported_count += 1
                self.song_imported.emit(song_id, title)
                logger.info(f"Imported new: {title} (id={song_id})")

        return imported_count

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_items_from_response(body, add_fn):
        """Extract song items from an API response body of unknown shape.

        Handles: plain lists, dicts with data/tasks/results arrays, single
        items with task_id, and nested structures.

        Args:
            body: Parsed JSON (dict or list).
            add_fn: Callable(item_dict) to register each discovered item.
        """
        if isinstance(body, list):
            for item in body:
                if isinstance(item, dict) and _looks_like_song(item):
                    add_fn(item)
            return

        if not isinstance(body, dict):
            return

        # Single item at top level
        if _looks_like_song(body):
            add_fn(body)

        # Array fields
        for key in ("data", "tasks", "results", "items", "conversions",
                     "songs", "generations", "history"):
            val = body.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and _looks_like_song(item):
                        add_fn(item)
            elif isinstance(val, dict) and _looks_like_song(val):
                add_fn(val)


def _looks_like_song(item: dict) -> bool:
    """Heuristic: does this dict look like a song/task record?"""
    return bool(
        item.get("task_id")
        or item.get("taskId")
        or (item.get("id") and (
            item.get("status")
            or item.get("prompt")
            or item.get("conversions")
            or item.get("conversion_path")
            or item.get("music_style")
            # lalals projects API fields
            or item.get("track_name")
            or item.get("track_url")
            or item.get("conversion_status")
        ))
    )

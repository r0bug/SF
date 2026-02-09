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
                         devapi discovery.
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

            # Check existing record
            existing = conn.execute(
                "SELECT id, status, title FROM songs WHERE task_id=?", (task_id,)
            ).fetchone()
            if not existing:
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
    # devapi.lalals.com helpers
    # ------------------------------------------------------------------

    def _extract_user_id(self, page):
        """Extract the user UUID from the page.

        Tries: (1) captured from devapi URL interception, (2) JS state,
        (3) fetch to devapi auth endpoint.
        """
        if self._captured_user_id:
            return self._captured_user_id

        # Try JS state: __NEXT_DATA__, cookies, etc.
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
            return user_id

        # Last resort: try devapi auth endpoint
        user_id = page.evaluate("""
        async () => {
            try {
                const resp = await fetch('https://devapi.lalals.com/auth/user', {credentials: 'include'});
                if (resp.ok) {
                    const d = await resp.json();
                    return d.id || d.userId || d.user_id || null;
                }
            } catch(e) {}
            return null;
        }
        """)
        if user_id:
            self._captured_user_id = user_id
        return user_id

    def _fetch_projects_via_devapi(self, page, user_id, add_fn):
        """Fetch all projects from devapi.lalals.com using browser session cookies.

        Calls GET /user/{user_id}/infinite-projects?offset=N in a loop
        until no more results are returned.

        Args:
            page: Playwright page with active lalals.com session.
            user_id: UUID of the logged-in user.
            add_fn: Callable(item_dict) to register each discovered song.
        """
        offset = 0
        total_found = 0

        while not self._stop_flag:
            result = page.evaluate("""
            async (args) => {
                const [userId, offset] = args;
                try {
                    const resp = await fetch(
                        'https://devapi.lalals.com/user/' + userId +
                        '/infinite-projects?offset=' + offset,
                        {credentials: 'include'}
                    );
                    if (!resp.ok) return {error: resp.status, data: []};
                    const json = await resp.json();
                    return {data: json.data || (Array.isArray(json) ? json : []), error: null};
                } catch(e) {
                    return {error: e.message, data: []};
                }
            }
            """, [user_id, offset])

            items = result.get("data", [])
            if not items:
                if result.get("error"):
                    logger.warning(
                        f"devapi fetch error at offset={offset}: {result['error']}"
                    )
                break

            for item in items:
                if not isinstance(item, dict):
                    continue
                normalized = self._normalize_devapi_item(item)
                add_fn(normalized)
                total_found += 1

            # Stop when fewer items than a typical batch
            if len(items) < 10:
                break
            offset += len(items)
            self.progress_update.emit(
                f"Fetching projects... {total_found} found so far"
            )

        logger.info(f"devapi: fetched {total_found} projects for user {user_id}")

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
        """Fetch detailed project data from devapi for a single project.

        Returns a normalized song dict, or None on failure.
        """
        detail = page.evaluate("""
        async (pid) => {
            try {
                const resp = await fetch(
                    'https://devapi.lalals.com/projects/front/get-one-by-id/' + pid,
                    {credentials: 'include'}
                );
                if (!resp.ok) return null;
                return await resp.json();
            } catch(e) {
                return null;
            }
        }
        """, project_id)

        if not detail or not isinstance(detail, dict):
            return None

        return self._normalize_devapi_item(detail)

    @staticmethod
    def _normalize_devapi_item(item):
        """Normalize a devapi.lalals.com project item to our standard format.

        Maps devapi field names (track_name, track_url, conversion_status)
        to the internal format used by the import logic (title, audio_url_1,
        status, task_id, etc.).

        Also builds S3 fallback URLs when track_url is incomplete.
        """
        pid = item.get("id", "")
        track_url = item.get("track_url") or ""

        # Build S3 fallback URL if track_url is missing or incomplete
        S3_BASE = "https://lalals.s3.amazonaws.com/conversions/standard"
        if not track_url or track_url.rstrip("/") == "https://lalals.s3.amazonaws.com":
            if pid:
                track_url = f"{S3_BASE}/{pid}/{pid}.mp3"

        return {
            "id": pid,
            "task_id": pid,
            "title": item.get("track_name") or item.get("name") or "",
            "status": item.get("conversion_status") or item.get("status") or "",
            "audio_url_1": track_url,
            "track_url": track_url,
            "music_style": (
                item.get("music_style")
                or item.get("musicStyle")
                or item.get("style")
                or ""
            ),
            "created_at": item.get("createdAt") or item.get("created_at") or "",
            "prompt": item.get("prompt") or item.get("description") or "",
            "conversionType": item.get("conversionType") or "",
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

        def _add_item(item):
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

            profile_dir = str(LOG_DIR / "browser_profile")
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
                # ---- Legacy mode: devapi + DOM scraping ----

                # Set up API response interception
                def on_response(response):
                    if self._stop_flag:
                        return
                    url = response.url
                    if "devapi.lalals.com/user/" in url and not self._captured_user_id:
                        m = re.search(
                            r'/user/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}'
                            r'-[0-9a-f]{4}-[0-9a-f]{12})/', url
                        )
                        if m:
                            self._captured_user_id = m.group(1)
                            logger.info(f"Captured user_id from devapi: {self._captured_user_id}")
                    if not ("devapi.lalals.com" in url
                            or "musicgpt.com" in url
                            or "lalals.com/api" in url):
                        return
                    try:
                        body = response.json()
                        self._extract_items_from_response(body, _add_item)
                    except Exception:
                        pass

                page.on("response", on_response)

                # Navigate to lalals.com homepage
                self.progress_update.emit("Navigating to lalals.com...")
                page.goto("https://lalals.com", wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                page.wait_for_timeout(3000)

                if "/auth/" in page.url:
                    self.import_error.emit(
                        "Not logged in — please log in to lalals.com first "
                        "(use the 'Login to Lalals' button in the Library tab)."
                    )
                    self.import_finished.emit(0)
                    return

                # ---- Step 2: Extract user_id and fetch projects via devapi ----
                self.progress_update.emit("Fetching project list from devapi...")
                user_id = self._extract_user_id(page)
                if user_id:
                    logger.info(f"User ID: {user_id}")
                    self._fetch_projects_via_devapi(page, user_id, _add_item)

                # ---- Step 3: Scrape data-project-id cards from DOM ----
                if not discovered:
                    self.progress_update.emit("Scraping page for project cards...")
                    cards = self._scrape_project_cards(page)
                    logger.info(f"Scraped {len(cards)} project cards from DOM")
                    for card in cards:
                        _add_item(card)

                # ---- Step 4: Scroll to load more and re-check ----
                if len(discovered) < 5:
                    self.progress_update.emit(
                        f"Scrolling to load more ({len(discovered)} so far)..."
                    )
                    self._scroll_to_load_all(page, lambda: len(discovered))

                    # Re-scrape after scrolling
                    cards = self._scrape_project_cards(page)
                    for card in cards:
                        _add_item(card)

                # ---- Step 5: Fetch detail for each project to get download URLs ----
                self.progress_update.emit(
                    f"Fetching details for {len(discovered)} project(s)..."
                )
                for i, item in enumerate(list(discovered)):
                    if self._stop_flag:
                        break
                    pid = item.get("id") or item.get("task_id") or ""
                    if pid and not item.get("track_url"):
                        detail = self._fetch_project_detail(page, pid)
                        if detail:
                            # Merge detail into the discovered item
                            item.update(detail)
                            logger.info(
                                f"Detail {i+1}/{len(discovered)}: "
                                f"{detail.get('track_name', '?')} "
                                f"url={detail.get('track_url', 'none')[:60]}"
                            )

                try:
                    page.remove_listener("response", on_response)
                except Exception:
                    pass

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

        When a MusicGPT API key is available, fetches fresh download
        URLs via the byId API endpoint (more reliable than discovery data).

        Returns the number of songs imported/linked.
        """
        from automation.lalals_driver import LalalsDriver

        imported_count = 0
        selected_set = set(selected_task_ids)

        # Try to get API key for fresh URL fetching
        api_key = ""
        try:
            row = conn.execute(
                "SELECT value FROM config WHERE key='musicgpt_api_key'"
            ).fetchone()
            if row:
                api_key = row[0] or ""
        except Exception:
            pass

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

            # Check if already in DB — first by task_id, then by title
            existing = conn.execute(
                "SELECT id, status, title FROM songs WHERE task_id=?", (task_id,)
            ).fetchone()

            if not existing:
                # Try matching by title (case-insensitive)
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

            # Get metadata — prefer fresh API data if key available
            metadata = {}
            if api_key and task_id:
                metadata = self._fetch_metadata_via_api(api_key, task_id)

            if not metadata.get("audio_url_1"):
                # Fall back to discovery data
                metadata = LalalsDriver.extract_metadata(item)

            prompt = item.get("prompt") or item.get("description") or ""
            lyrics = item.get("lyrics") or ""
            style = metadata.get("music_style") or ""

            self.progress_update.emit(f"Importing: {title}")

            # Download audio files via direct URLs
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
                            f"URL download failed for {title} v{version}: {e}"
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

        When a MusicGPT API key is available, fetches fresh download
        URLs via the byId API endpoint.

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

        # Try to get API key for fresh URL fetching
        api_key = ""
        try:
            row = conn.execute(
                "SELECT value FROM config WHERE key='musicgpt_api_key'"
            ).fetchone()
            if row:
                api_key = row[0] or ""
        except Exception:
            pass

        for item in songs_data:
            if self._stop_flag:
                break

            task_id = (
                item.get("task_id")
                or item.get("taskId")
                or item.get("id", "")
            )
            if task_id not in selected_set:
                continue

            title = (
                item.get("title")
                or item.get("prompt", "")[:60]
                or f"Imported-{task_id[:8]}"
            )

            # Check if already in DB — first by task_id, then by title
            existing = conn.execute(
                "SELECT id, status, title FROM songs WHERE task_id=?", (task_id,)
            ).fetchone()

            if not existing:
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

            # Get metadata — prefer fresh API data if key available
            metadata = {}
            if api_key and task_id:
                metadata = self._fetch_metadata_via_api(api_key, task_id)

            if not metadata.get("audio_url_1"):
                metadata = LalalsDriver.extract_metadata(item)

            prompt = item.get("prompt") or item.get("description") or ""
            lyrics = item.get("lyrics") or ""
            style = metadata.get("music_style") or ""

            self.progress_update.emit(f"Importing: {title}")

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
    # API-based metadata fetch
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_metadata_via_api(api_key: str, task_id: str) -> dict:
        """Fetch fresh metadata from MusicGPT byId API using the API key.

        Returns parsed metadata dict, or empty dict on failure.
        """
        try:
            from automation.api_worker import fetch_by_task_id
            return fetch_by_task_id(api_key, task_id)
        except Exception as e:
            logger.debug(f"API fetch failed for task_id={task_id}: {e}")
            return {}

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
            # devapi.lalals.com fields
            or item.get("track_name")
            or item.get("track_url")
            or item.get("conversion_status")
        ))
    )

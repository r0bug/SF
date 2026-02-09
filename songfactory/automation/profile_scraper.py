"""Profile page scraper for lalals.com user profiles.

Navigates to https://lalals.com/user/{username}/audio and extracts:
- Song list (titles, project IDs) via "Load More" button + API interception
- Lyrics (by clicking into song detail views)
- Downloads via the 3-dot menu (Full Song / Vocals / Instrumental)

The profile page is a Next.js app. Songs are loaded in batches of 10 via
the devapi.lalals.com/user/{user_id}/infinite-projects endpoint. The page
shows a "Load More" button (not infinite scroll). We click "Load More"
repeatedly and intercept the API responses to capture song data.

DOM structure (discovered via debug):
- Container: div[data-name="ProjectTable"] > div.flex.flex-col
- Each card:  div.relative.flex.rounded-xl (5 children: thumbnail, title area, action buttons)
- Title:      h6.text-lg (inside card)
- Subtitle:   p tag near h6 (e.g. "Music • Version 2")
- Buttons:    64x64 thumbnail + 2x like/share + 1x 3-dot menu (w-5, opacity-25)
- Load More:  button:has-text("Load More") below the card list

Usage:
    scraper = ProfileScraper(page, "johnstorlie", stop_fn, progress_fn)
    if scraper.navigate_to_profile():
        songs = scraper.discover_songs()
        for song in songs:
            lyrics = scraper.extract_lyrics(song["title"])
            paths = scraper.download_all_tracks(song["title"], dm, ["Full Song", "Vocals"])
"""

import logging
import re

logger = logging.getLogger("songfactory.automation")

# S3 base URL for fallback download links
_S3_BASE = "https://lalals.s3.amazonaws.com/conversions/standard"


class ProfileScraper:
    """Scrapes a lalals.com user profile page for songs, lyrics, and downloads."""

    def __init__(self, page, username: str, stop_flag_fn=None, progress_fn=None):
        """
        Args:
            page: Playwright Page object (must be logged in to lalals.com).
            username: Lalals.com username (from profile URL).
            stop_flag_fn: Callable returning True when scraping should stop.
            progress_fn: Callable(str) for status updates.
        """
        self.page = page
        self.username = username
        self._stop = stop_flag_fn or (lambda: False)
        self._progress = progress_fn or (lambda msg: None)
        # API data captured from intercepted responses
        self._api_songs = {}  # id -> dict from infinite-projects API

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_profile(self) -> bool:
        """Navigate to the user's profile audio page.

        Returns:
            True if the profile page loaded successfully.
            False if redirected to auth or page not found.
        """
        url = f"https://lalals.com/user/{self.username}/audio"
        self._progress(f"Navigating to profile: {url}")
        logger.info(f"Navigating to profile: {url}")

        # Set up API response interception before navigating
        self._setup_api_interception()

        self.page.goto(url, wait_until="domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        self.page.wait_for_timeout(3000)

        current_url = self.page.url
        if "/auth/" in current_url:
            logger.warning("Redirected to auth — not logged in")
            return False

        # Check that the ProjectTable container exists (the actual song list).
        # Note: body text always contains "Not Found" in serialised Next.js
        # component data, so we can't rely on text matching alone.
        has_project_table = self.page.evaluate(
            '() => !!document.querySelector("[data-name=\'ProjectTable\']")'
        )
        if not has_project_table:
            logger.warning(f"Profile page not found for username: {self.username}")
            return False

        logger.info(f"Profile page loaded: {current_url}")
        logger.info(f"API songs captured during load: {len(self._api_songs)}")
        return True

    def _setup_api_interception(self):
        """Attach a response listener to capture devapi infinite-projects data."""
        def on_response(response):
            url = response.url
            if "infinite-projects" not in url:
                return
            try:
                body = response.json()
                items = body.get("data", []) if isinstance(body, dict) else []
                for item in items:
                    if isinstance(item, dict) and item.get("id"):
                        self._api_songs[item["id"]] = item
                logger.info(
                    f"Intercepted infinite-projects: +{len(items)} items "
                    f"(total={len(self._api_songs)})"
                )
            except Exception as e:
                logger.debug(f"Failed to parse infinite-projects response: {e}")

        self.page.on("response", on_response)

    # ------------------------------------------------------------------
    # Song Discovery
    # ------------------------------------------------------------------

    def discover_songs(self) -> list[dict]:
        """Click "Load More" repeatedly to load all songs, then extract data.

        Combines data from:
        1. Intercepted devapi infinite-projects API responses (titles, IDs, URLs)
        2. DOM H6 headings as fallback for any missed titles

        Returns:
            List of dicts: [{title, id, index, track_url, ...}, ...]
        """
        self._progress("Loading all songs via Load More...")

        # Click Load More until it disappears or no new songs appear
        self._click_load_more_until_done()

        # Build song list from intercepted API data (most reliable)
        songs = self._build_song_list()

        logger.info(f"Discovered {len(songs)} songs on profile page")
        self._progress(f"Found {len(songs)} songs on profile page")
        return songs

    def _count_dom_cards(self) -> int:
        """Count visible song cards in the ProjectTable container."""
        return self.page.evaluate("""
            () => {
                const container = document.querySelector("[data-name='ProjectTable']");
                if (!container) return 0;
                const list = container.querySelector(".flex.flex-col");
                return list ? list.children.length : 0;
            }
        """)

    def _click_load_more_until_done(self, max_clicks=30):
        """Click the "Load More" button until it disappears or stops adding songs."""
        no_new_count = 0

        for click_num in range(max_clicks):
            if self._stop():
                break

            api_count_before = len(self._api_songs)

            # Check if Load More button is visible
            load_more_visible = self.page.evaluate("""
                () => {
                    const btns = document.querySelectorAll("button");
                    for (const btn of btns) {
                        const text = (btn.textContent || "").trim();
                        if (text === "Load More" && btn.offsetParent !== null) {
                            return true;
                        }
                    }
                    return false;
                }
            """)

            if not load_more_visible:
                logger.info(
                    f"Load More not visible after {click_num} clicks "
                    f"(total songs from API: {len(self._api_songs)})"
                )
                break

            # Scroll Load More into view and click it
            load_more_btn = self.page.locator('button:has-text("Load More")').first
            try:
                load_more_btn.scroll_into_view_if_needed()
                self.page.wait_for_timeout(500)
                load_more_btn.click()
            except Exception as e:
                logger.debug(f"Load More click failed: {e}")
                break

            # Wait for API response
            self.page.wait_for_timeout(3000)

            api_count_after = len(self._api_songs)
            new_items = api_count_after - api_count_before
            dom_count = self._count_dom_cards()

            if new_items > 0:
                no_new_count = 0
                self._progress(
                    f"Load More #{click_num + 1}: {api_count_after} songs "
                    f"({dom_count} in DOM)"
                )
                logger.info(
                    f"Load More click {click_num + 1}: "
                    f"+{new_items} API songs (total={api_count_after}, DOM={dom_count})"
                )
            else:
                no_new_count += 1
                logger.info(
                    f"Load More click {click_num + 1}: no new songs "
                    f"(total={api_count_after}, DOM={dom_count})"
                )
                if no_new_count >= 2:
                    logger.info("No new songs after 2 consecutive clicks, done")
                    break

    def _build_song_list(self) -> list[dict]:
        """Build a normalized song list from intercepted API data.

        Falls back to DOM scraping if API interception captured nothing.
        """
        if self._api_songs:
            songs = []
            for i, (pid, item) in enumerate(self._api_songs.items()):
                track_url = item.get("track_url") or ""
                # Build S3 fallback URL if track_url is missing/incomplete
                if not track_url or track_url.rstrip("/") == "https://lalals.s3.amazonaws.com":
                    track_url = f"{_S3_BASE}/{pid}/{pid}.mp3"

                # Extract prompt + lyrics from queue_task.input_payload
                qt = item.get("queue_task") or {}
                ip = qt.get("input_payload") or {} if isinstance(qt, dict) else {}
                if not isinstance(ip, dict):
                    ip = {}

                prompt = ip.get("prompt", "") or item.get("prompt") or ""
                lyrics = ip.get("lyrics", "") or ""
                conversion_id_1 = ip.get("conversion_id_1", "")
                conversion_id_2 = ip.get("conversion_id_2", "")

                songs.append({
                    "id": pid,
                    "title": item.get("track_name") or item.get("name") or "",
                    "index": i,
                    "track_url": track_url,
                    "audio_url_1": track_url,
                    "status": item.get("conversion_status") or "",
                    "music_style": (
                        item.get("music_style")
                        or item.get("musicStyle")
                        or item.get("style")
                        or ""
                    ),
                    "created_at": item.get("createdAt") or item.get("date_added") or "",
                    "conversionType": item.get("conversionType") or "",
                    "prompt": prompt,
                    "lyrics": lyrics,
                    "conversion_id_1": conversion_id_1,
                    "conversion_id_2": conversion_id_2,
                })
            return songs

        # Fallback: scrape DOM for H6 titles
        logger.warning("No API data intercepted, falling back to DOM scraping")
        return self._extract_song_cards_from_dom()

    def _extract_song_cards_from_dom(self) -> list[dict]:
        """Extract song cards from the DOM as a fallback.

        Uses the ProjectTable container and H6 headings.
        """
        cards = self.page.evaluate("""
            () => {
                const results = [];
                const container = document.querySelector("[data-name='ProjectTable']");
                if (!container) return results;

                const list = container.querySelector(".flex.flex-col");
                if (!list) return results;

                const cardEls = Array.from(list.children);
                for (const card of cardEls) {
                    const h6 = card.querySelector("h6");
                    if (!h6) continue;

                    const title = h6.textContent.trim();
                    if (!title) continue;

                    // Get subtitle (version info)
                    const h6Parent = h6.parentElement;
                    const pTag = h6Parent ? h6Parent.querySelector("p") : null;
                    const subtitle = pTag ? pTag.textContent.trim() : "";

                    results.push({
                        title: title,
                        id: "",
                        index: results.length,
                        subtitle: subtitle,
                    });
                }
                return results;
            }
        """)
        return cards or []

    # ------------------------------------------------------------------
    # Lyrics Extraction
    # ------------------------------------------------------------------

    def extract_lyrics(self, song_title: str) -> str:
        """Click on a song to open its detail view and extract lyrics.

        Args:
            song_title: Title of the song to click.

        Returns:
            Extracted lyrics text, or empty string if not found.
        """
        logger.info(f"Extracting lyrics for: {song_title}")

        try:
            # Find the H6 heading with this title inside ProjectTable
            card = self._find_song_card(song_title)
            if not card:
                logger.debug(f"Song card not found: {song_title}")
                return ""

            card.click()
            self.page.wait_for_timeout(2000)

            # Look for lyrics in a modal, detail panel, or expanded section
            lyrics = self.page.evaluate("""
                () => {
                    // Strategy 1: Element with "lyrics" in class/id
                    const lyricsEls = document.querySelectorAll(
                        '[class*="lyrics"], [class*="Lyrics"], ' +
                        '[id*="lyrics"], [id*="Lyrics"]'
                    );
                    for (const el of lyricsEls) {
                        const text = (el.textContent || '').trim();
                        if (text.length > 10) return text;
                    }

                    // Strategy 2: Look in modal/dialog/drawer
                    const modals = document.querySelectorAll(
                        '[role="dialog"], [class*="modal"], [class*="Modal"], ' +
                        '[class*="drawer"], [class*="Drawer"], ' +
                        '[class*="overlay"], [class*="Overlay"]'
                    );
                    for (const modal of modals) {
                        const textEls = modal.querySelectorAll(
                            'pre, textarea, [class*="text"], [class*="content"]'
                        );
                        for (const te of textEls) {
                            const t = (te.textContent || '').trim();
                            if (t.length > 50 && t.includes('\\n')) return t;
                        }
                    }

                    // Strategy 3: Any large text block that appeared recently
                    const expanded = document.querySelectorAll(
                        '[class*="detail"], [class*="Detail"], ' +
                        '[class*="expanded"], [class*="Expanded"], ' +
                        '[class*="panel"], [class*="Panel"]'
                    );
                    for (const el of expanded) {
                        const t = (el.textContent || '').trim();
                        if (t.length > 50 && t.includes('\\n')) return t;
                    }

                    return '';
                }
            """)

            # Close the detail view
            self._dismiss_overlay()

            if lyrics:
                logger.info(f"Extracted {len(lyrics)} chars of lyrics for: {song_title}")
            else:
                logger.debug(f"No lyrics found for: {song_title}")

            return lyrics or ""

        except Exception as e:
            logger.debug(f"Lyrics extraction failed for '{song_title}': {e}")
            self._dismiss_overlay()
            return ""

    # ------------------------------------------------------------------
    # Downloads via 3-dot menu
    # ------------------------------------------------------------------

    def download_track(self, song_title: str, track_label: str, dm) -> str:
        """Download a specific track type via the 3-dot menu.

        The 3-dot menu button is the last small (w-5) button in each song card.
        Clicking it opens a dropdown: Download > {Full Song | Vocals | Instrumental}

        Args:
            song_title: Title of the song.
            track_label: Menu label — "Full Song", "Vocals", or "Instrumental".
            dm: DownloadManager instance.

        Returns:
            Path string to saved file, or empty string on failure.
        """
        logger.info(f"Downloading '{track_label}' for: {song_title}")

        try:
            # Find the song card
            card = self._find_song_card(song_title)
            if not card:
                logger.debug(f"Song card not found for download: {song_title}")
                return ""
            card.scroll_into_view_if_needed()
            self.page.wait_for_timeout(500)

            # Find and click the 3-dot menu button
            # It's the last opacity-25 button within the card's ancestor
            menu_btn = self._find_menu_button(card)
            if not menu_btn:
                logger.debug(f"3-dot menu button not found for: {song_title}")
                return ""

            menu_btn.click()
            self.page.wait_for_timeout(1000)

            # Click "Download" in the popup
            download_item = self._find_menu_item("Download")
            if not download_item:
                logger.debug("Download menu item not found")
                self._dismiss_menu()
                return ""
            download_item.click()
            self.page.wait_for_timeout(1000)

            # Click the specific track label in the submenu
            track_item = self._find_menu_item(track_label)
            if not track_item:
                logger.debug(f"Track label '{track_label}' not found in submenu")
                self._dismiss_menu()
                return ""

            # Map track_label to track_type for filename
            track_type_map = {
                "Full Song": "full_song",
                "Vocals": "vocals",
                "Instrumental": "instrumental",
            }
            track_type = track_type_map.get(track_label, track_label.lower())

            # Expect and save the download
            with self.page.expect_download(timeout=30000) as dl_info:
                track_item.click()
            download = dl_info.value

            path = dm.save_playwright_download_track(download, song_title, track_type)
            logger.info(f"Downloaded '{track_label}' for '{song_title}': {path}")
            return str(path)

        except Exception as e:
            logger.debug(f"Download failed for '{song_title}' / '{track_label}': {e}")
            self._dismiss_menu()
            return ""

    def download_all_tracks(self, song_title: str, dm, track_types: list) -> dict:
        """Download multiple track types for a song.

        Args:
            song_title: Title of the song.
            dm: DownloadManager instance.
            track_types: List of labels, e.g. ["Full Song", "Vocals", "Instrumental"].

        Returns:
            Dict mapping track_type to file path string.
            E.g. {"full_song": "/path/to/file.mp3", "vocals": "/path/to/file.mp3"}
        """
        results = {}
        type_key_map = {
            "Full Song": "full_song",
            "Vocals": "vocals",
            "Instrumental": "instrumental",
        }

        for label in track_types:
            if self._stop():
                break
            key = type_key_map.get(label, label.lower())
            path = self.download_track(song_title, label, dm)
            if path:
                results[key] = path
            # Brief pause between downloads
            self.page.wait_for_timeout(1000)

        return results

    # ------------------------------------------------------------------
    # DOM element finders
    # ------------------------------------------------------------------

    def _find_song_card(self, song_title: str):
        """Find the clickable song card element for a given title.

        Returns a Playwright Locator, or None.
        """
        # The card contains an H6 with the title. Find the card div.
        try:
            # First try to find the H6 inside the ProjectTable container
            h6 = self.page.locator(
                '[data-name="ProjectTable"] h6',
            ).filter(has_text=song_title).first

            if h6.is_visible(timeout=2000):
                # The clickable card is an ancestor with the rounded-xl class
                card = h6.locator(
                    'xpath=ancestor::div[contains(@class, "rounded-xl")]'
                ).first
                if card.is_visible(timeout=1000):
                    return card
                # Fall back to just clicking the h6
                return h6
        except Exception:
            pass

        # Fallback: any visible text match
        try:
            el = self.page.locator(f'h6:has-text("{song_title}")').first
            if el.is_visible(timeout=2000):
                return el
        except Exception:
            pass

        return None

    def _find_menu_button(self, card_or_title_el):
        """Find the 3-dot menu button near a song card.

        On the profile page, each card has buttons:
        [0] 64x64 thumbnail play button
        [1] 20x20 like button (opacity-35)
        [2] 20x20 share button (opacity-35)
        [3] 20x20 3-dot menu button (opacity-25, w-5)
        [4] 20x20 hidden button (opacity-25, w-5, sometimes 0x0)

        We target the button with opacity-25 class that is visible.
        """
        strategies = [
            # The 3-dot menu uses opacity-25 and w-5 classes
            lambda: card_or_title_el.locator(
                'xpath=ancestor::div[contains(@class, "rounded-xl")]'
                '//button[contains(@class, "opacity-25")]'
            ).first,
            # Broader: last small button in the card
            lambda: card_or_title_el.locator(
                'xpath=ancestor::div[contains(@class, "rounded-xl")]'
                '//button[contains(@class, "w-5")]'
            ).first,
            # Walk up to find any nearby button that looks like a menu
            lambda: card_or_title_el.locator(
                'xpath=ancestor::*[position() <= 6]'
                '//button[contains(@class, "opacity-25")]'
            ).first,
            # Last resort: last button in ancestor
            lambda: card_or_title_el.locator(
                'xpath=ancestor::*[position() <= 4]//button'
            ).last,
        ]

        for strategy in strategies:
            try:
                btn = strategy()
                if btn.is_visible(timeout=1000):
                    return btn
            except Exception:
                continue

        return None

    def _find_menu_item(self, text: str):
        """Find a visible menu/dropdown item by text content."""
        strategies = [
            lambda: self.page.locator(f'text="{text}"').first,
            lambda: self.page.locator(
                f'[role="menuitem"]:has-text("{text}")'
            ).first,
            lambda: self.page.locator(
                f'button:has-text("{text}")'
            ).first,
            lambda: self.page.locator(
                f'a:has-text("{text}"), div:has-text("{text}"), '
                f'li:has-text("{text}")'
            ).first,
        ]

        for strategy in strategies:
            try:
                item = strategy()
                if item.is_visible(timeout=2000):
                    return item
            except Exception:
                continue

        return None

    def _dismiss_menu(self):
        """Dismiss any open popup/dropdown menu."""
        try:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)
        except Exception:
            pass

    def _dismiss_overlay(self):
        """Close any open overlay/modal/drawer."""
        try:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)
        except Exception:
            pass
        # Click outside any remaining overlay
        try:
            self.page.mouse.click(10, 10)
            self.page.wait_for_timeout(300)
        except Exception:
            pass

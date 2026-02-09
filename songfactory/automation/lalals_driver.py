"""Lalals.com page interaction driver for Song Factory automation."""

import json
import time
import logging
from pathlib import Path
from playwright.sync_api import Page, Browser, BrowserContext, Download, expect

logger = logging.getLogger("songfactory.automation")

STATE_FILE = Path.home() / ".songfactory" / "browser_state.json"


class LalalsDriverError(Exception):
    """Raised when a lalals.com interaction fails."""
    pass


class LalalsDriver:
    """Handles all interactions with lalals.com pages.

    Uses resilient selector strategies (text-based, role-based, attribute-based)
    since lalals.com is a React/Next.js SPA with dynamically generated class names
    that may change between deployments.
    """

    def __init__(self, page: Page, context: BrowserContext):
        self.page = page
        self.context = context

    # ------------------------------------------------------------------
    # Selector helpers
    # ------------------------------------------------------------------

    def _find_visible(self, selectors: list[str], *, timeout: int = 3000):
        """Return the first visible locator matching any of *selectors*.

        Iterates through the selector list in order, returning the first
        locator whose element is visible within *timeout* ms.  Returns
        ``None`` if nothing matches.
        """
        for sel in selectors:
            try:
                loc = self.page.locator(sel).first
                if loc.is_visible(timeout=timeout):
                    return loc
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def is_logged_in(self) -> bool:
        """Check if the current session is authenticated.

        Navigate to /music and see if we get redirected to login.
        """
        logger.info("Checking login status...")
        self.page.goto("https://lalals.com/music", wait_until="domcontentloaded")
        self.page.wait_for_load_state("networkidle", timeout=15000)
        logged_in = "/auth/" not in self.page.url
        logger.info(f"Logged in: {logged_in} (url={self.page.url})")
        return logged_in

    def open_login_page(self):
        """Navigate to the lalals.com login page for manual authentication.

        Opens the sign-in page so the user can log in via Google Auth or
        any other method. Call ``wait_for_manual_login()`` afterwards.
        """
        logger.info("Opening lalals.com login page for manual authentication...")
        self.page.goto(
            "https://lalals.com/auth/sign-in", wait_until="domcontentloaded"
        )
        self.page.wait_for_load_state("networkidle", timeout=15000)
        logger.info(f"Login page opened (url={self.page.url})")

    def wait_for_manual_login(self, timeout_s: int = 300, stop_flag=None) -> bool:
        """Wait for the user to complete manual login.

        Polls every 2 seconds, checking if the URL has left the /auth/ path.

        Args:
            timeout_s: Max seconds to wait (default 5 minutes).
            stop_flag: Optional callable returning True to abort early.

        Returns:
            True when login is detected.

        Raises:
            LalalsDriverError: If timeout expires before login completes.
        """
        logger.info(f"Waiting for manual login (timeout: {timeout_s}s)...")
        start = time.time()

        while time.time() - start < timeout_s:
            if stop_flag and stop_flag():
                raise LalalsDriverError("Login wait cancelled by user")

            try:
                url = self.page.url
                if "/auth/" not in url and "lalals.com" in url:
                    logger.info(f"Login detected (url={url})")
                    self.save_state()
                    return True
            except Exception:
                pass

            self.page.wait_for_timeout(2000)

        raise LalalsDriverError(
            f"Manual login timed out after {timeout_s}s"
        )

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def save_state(self):
        """Save browser storage state for session persistence."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=str(STATE_FILE))
        logger.info(f"Browser state saved to {STATE_FILE}")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_music(self):
        """Navigate to the music generation page.

        Raises:
            LalalsDriverError: If the browser is redirected to login
                (session may have expired).
        """
        if "/music" not in self.page.url:
            logger.info("Navigating to /music...")
            self.page.goto(
                "https://lalals.com/music", wait_until="domcontentloaded"
            )
            self.page.wait_for_load_state("networkidle", timeout=15000)

        if "/auth/" in self.page.url:
            raise LalalsDriverError(
                "Redirected to login -- session may have expired"
            )
        logger.info(f"On music page (url={self.page.url})")

    # ------------------------------------------------------------------
    # Form filling
    # ------------------------------------------------------------------

    def fill_prompt(self, prompt_text: str):
        """Fill the song prompt/description field.

        The field is a textarea with a placeholder like "Describe your song".
        Uses ``page.fill()`` for speed over ``page.type()``.

        Args:
            prompt_text: The song description (max ~300 chars).

        Raises:
            LalalsDriverError: If the textarea cannot be located.
        """
        logger.info(f"Filling prompt ({len(prompt_text)} chars)")

        textarea = self._find_visible(
            [
                'textarea[title*="Describe"]',
                'textarea[maxlength="500"]',          # prompt textarea
                'textarea[placeholder*="escribe"]',
                'textarea[placeholder*="song"]',
                "textarea",                           # fallback: first textarea
            ],
            timeout=5000,
        )

        if textarea is None:
            # Last-resort role-based lookup
            try:
                textarea = self.page.get_by_role("textbox").first
                textarea.wait_for(timeout=5000)
            except Exception:
                textarea = None

        if textarea is None:
            raise LalalsDriverError("Could not find prompt textarea on music page")

        textarea.click()
        textarea.fill(prompt_text)
        logger.info("Prompt filled successfully")

    def fill_lyrics(self, lyrics_text: str):
        """Expand the lyrics section and fill in lyrics.

        Steps:
            1. Click the "Lyrics" toggle/button to expand the lyrics input area.
            2. Find the lyrics textarea.
            3. Fill it with ``page.fill()`` for speed.

        Args:
            lyrics_text: Full song lyrics.

        Raises:
            LalalsDriverError: If the lyrics textarea cannot be located.
        """
        logger.info(f"Filling lyrics ({len(lyrics_text)} chars)")

        # -- Click the Lyrics mode toggle in the form footer ----------------
        # The Music page has an Instrumental/Lyrics toggle pair at the
        # bottom of the form.  The Lyrics button is inside a div with
        # data-name="LyricsButton".  Clicking it reveals a lyrics textarea.
        # IMPORTANT: Do NOT click the sidebar "Lyrics" nav button — that
        # navigates to a different tool (AI Lyrics Generator).
        lyrics_toggle = self._find_visible(
            [
                '[data-name="LyricsButton"] button',
                'button[aria-label="Lyrics"]',
            ],
            timeout=5000,
        )

        if lyrics_toggle is not None:
            lyrics_toggle.evaluate("el => el.click()")
            logger.info("Lyrics mode toggle clicked")
            self.page.wait_for_timeout(3000)
        else:
            logger.info("No Lyrics toggle found — section may already be open")

        # -- Fill lyrics textarea -------------------------------------------
        # After toggling, a second textarea appears with placeholder
        # "Write your own lyrics here (optional)" and maxlength=3000.
        lyrics_area = self._find_visible(
            [
                'textarea[placeholder*="Write your own lyrics"]',
                'textarea[placeholder*="lyrics"]',
                'textarea[maxlength="3000"]',
            ],
            timeout=5000,
        )

        if lyrics_area is None:
            # Fallback: the second textarea on the page (first = prompt).
            all_textareas = self.page.locator("textarea")
            count = all_textareas.count()
            logger.info(f"Textarea fallback: found {count} textarea(s)")
            if count >= 2:
                lyrics_area = all_textareas.nth(1)

        if lyrics_area is None:
            raise LalalsDriverError(
                "Could not find lyrics textarea after toggling. "
                "The Lyrics section may not have opened."
            )

        lyrics_area.click()
        lyrics_area.fill(lyrics_text)
        logger.info("Lyrics filled successfully")

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def click_generate(self):
        """Click the generate/submit button to start song creation.

        Raises:
            LalalsDriverError: If the generate button cannot be located.
        """
        logger.info("Clicking generate button")

        generate_btn = self._find_visible(
            [
                "button[type='submit']",
                "button:has-text('Generate')",
                "button:has-text('Create')",
                "button:has-text('Submit')",
                "button[aria-label*='submit']",
                "button[aria-label*='generate']",
                "button[aria-label*='send']",
            ],
            timeout=5000,
        )

        if generate_btn is None:
            # Last resort: the right-most or last button is often the submit
            logger.warning("Using last visible button as generate fallback")
            generate_btn = self.page.locator("button").last

        if generate_btn is None:
            raise LalalsDriverError("Could not find generate button")

        generate_btn.click()
        logger.info("Generate button clicked")

    def wait_for_generation_v2(
        self,
        timeout_ms: int = 600_000,
        stop_flag=None,
        progress_callback=None,
    ) -> dict:
        """Wait for generation by intercepting MusicGPT API responses.

        Instead of polling the DOM for download buttons, this intercepts the
        actual API responses that the lalals.com frontend polls, giving us
        reliable completion detection AND metadata.

        Args:
            timeout_ms: Maximum wait time in milliseconds.
            stop_flag: Optional callable returning True to cancel.
            progress_callback: Optional callable(status_text, elapsed_s).

        Returns:
            dict with parsed API response metadata on COMPLETED.

        Raises:
            LalalsDriverError: On error, timeout, or cancellation.
        """
        logger.info(f"Waiting for generation via API interception (timeout: {timeout_ms / 1000:.0f}s)...")
        completed_data = {}
        error_data = {}

        def on_response(response):
            url = response.url
            if not ("musicgpt.com" in url or "byId" in url or "lalals.com/api" in url):
                return
            try:
                body = response.json()
                status = None
                if isinstance(body, dict):
                    status = body.get("status")
                    if not status and isinstance(body.get("data"), dict):
                        status = body["data"].get("status")

                if status:
                    logger.info(f"API status: {status} (url={url[:100]})")

                if status == "COMPLETED":
                    completed_data["result"] = body
                elif status in ("ERROR", "FAILED"):
                    error_data["result"] = body
            except Exception:
                pass

        self.page.on("response", on_response)

        try:
            start = time.time()
            timeout_s = timeout_ms / 1000

            while time.time() - start < timeout_s:
                elapsed = time.time() - start

                # Check cancel
                if stop_flag and stop_flag():
                    raise LalalsDriverError("Generation cancelled by user")

                # Check for completion
                if "result" in completed_data:
                    metadata = self.extract_metadata(completed_data["result"])
                    logger.info(f"Generation completed via API after {elapsed:.1f}s")
                    return metadata

                # Check for error
                if "result" in error_data:
                    body = error_data["result"]
                    msg = "Generation failed"
                    if isinstance(body, dict):
                        msg = body.get("error", body.get("message", msg))
                    raise LalalsDriverError(f"Generation error from API: {msg}")

                # Progress callback
                if progress_callback and int(elapsed) % 5 == 0 and elapsed > 0:
                    progress_callback(f"Generating... ({elapsed:.0f}s)", elapsed)

                if int(elapsed) % 15 == 0 and elapsed > 0:
                    logger.info(f"Still waiting for API response... ({elapsed:.0f}s elapsed)")

                self.page.wait_for_timeout(2000)

            # Timeout — fall back to DOM-based detection
            logger.warning("API interception timed out, falling back to DOM polling")
            self._wait_for_generation_dom(timeout_ms=60000)
            return {}

        finally:
            try:
                self.page.remove_listener("response", on_response)
            except Exception:
                pass

    @staticmethod
    def extract_metadata(api_response: dict) -> dict:
        """Parse a MusicGPT API response into a flat dict for DB storage.

        Handles the documented response shapes:
        - Submit response: {task_id, conversion_id_1, conversion_id_2, eta}
        - byId response:   {conversion: {task_id, status, audio_url, ...}}
        - Webhook payload:  {conversion_path, conversion_path_wav, ...}
        - Legacy shapes:    nested under "data" key, or lists under "conversions"

        Args:
            api_response: Raw JSON dict from the API.

        Returns:
            Flat dict with keys matching the songs table metadata columns.
        """
        data = api_response

        # Unwrap nested containers
        if isinstance(data.get("conversion"), dict):
            data = data["conversion"]
        elif isinstance(data.get("data"), dict):
            data = data["data"]

        metadata = {}

        # Task ID
        metadata["task_id"] = (
            data.get("task_id") or data.get("taskId") or data.get("id")
        )

        # Conversion IDs — documented submit response has conversion_id_1/2
        cid1 = data.get("conversion_id_1") or data.get("conversion_id")
        cid2 = data.get("conversion_id_2")
        if cid1:
            metadata["conversion_id_1"] = str(cid1)
        if cid2:
            metadata["conversion_id_2"] = str(cid2)

        # Audio URLs — numbered fields from byId COMPLETED response
        url_1 = (
            data.get("conversion_path_1")
            or data.get("audio_url_1")
            or data.get("audio_url")
            or data.get("conversion_path")
            or data.get("conversionPath")
            or data.get("track_url")
        )
        # Filter out incomplete S3 base URLs (no actual file path)
        if url_1 and url_1.rstrip("/") != "https://lalals.s3.amazonaws.com":
            metadata["audio_url_1"] = url_1

        url_2 = (
            data.get("conversion_path_2")
            or data.get("audio_url_2")
            or data.get("conversion_path_wav")
        )
        if url_2 and url_2.rstrip("/") != "https://lalals.s3.amazonaws.com":
            metadata["audio_url_2"] = url_2

        # Build S3 URLs from conversion IDs or task_id if we don't have direct URLs
        S3_BASE = "https://lalals.s3.amazonaws.com/conversions/standard"
        if not metadata.get("audio_url_1") and cid1:
            metadata["audio_url_1"] = f"{S3_BASE}/{cid1}/{cid1}.mp3"
        if not metadata.get("audio_url_2") and cid2:
            metadata["audio_url_2"] = f"{S3_BASE}/{cid2}/{cid2}.mp3"
        # Fallback: use task_id as S3 path (devapi projects use id as path)
        if not metadata.get("audio_url_1") and metadata.get("task_id"):
            tid = metadata["task_id"]
            metadata["audio_url_1"] = f"{S3_BASE}/{tid}/{tid}.mp3"

        # Legacy: conversions list
        conversions = data.get("conversions") or data.get("results") or []
        if isinstance(conversions, list):
            for i, conv in enumerate(conversions[:2]):
                idx = i + 1
                if isinstance(conv, dict):
                    if not metadata.get(f"conversion_id_{idx}"):
                        metadata[f"conversion_id_{idx}"] = (
                            conv.get("conversion_id")
                            or conv.get("conversionId")
                            or conv.get("id")
                        )
                    if not metadata.get(f"audio_url_{idx}"):
                        metadata[f"audio_url_{idx}"] = (
                            conv.get("conversion_path")
                            or conv.get("audio_url")
                            or conv.get("url")
                        )
                    if not metadata.get(f"file_size_{idx}"):
                        metadata[f"file_size_{idx}"] = (
                            conv.get("file_size") or conv.get("fileSize")
                        )
                elif isinstance(conv, str):
                    if not metadata.get(f"audio_url_{idx}"):
                        metadata[f"audio_url_{idx}"] = conv

        # Style/voice/duration
        metadata["music_style"] = (
            data.get("music_style") or data.get("musicStyle") or data.get("style")
        )
        metadata["voice_used"] = (
            data.get("voice") or data.get("voice_name") or data.get("voiceName")
        )
        metadata["duration_seconds"] = (
            data.get("duration")
            or data.get("duration_seconds")
            or data.get("conversion_duration")
        )
        metadata["file_format"] = (
            data.get("format") or data.get("file_format") or "mp3"
        )
        metadata["lalals_created_at"] = (
            data.get("created_at") or data.get("createdAt")
        )

        # Timestamped lyrics
        ts_lyrics = data.get("lyrics_timestamped") or data.get("timestampedLyrics")
        if ts_lyrics and not isinstance(ts_lyrics, str):
            ts_lyrics = json.dumps(ts_lyrics)
        metadata["lyrics_timestamped"] = ts_lyrics

        # Clean up None values
        return {k: v for k, v in metadata.items() if v is not None}

    def _wait_for_generation_dom(self, timeout_ms: int = 600_000) -> bool:
        """Wait for song generation to complete (DOM-based fallback).

        Polls for completion indicators at 3-second intervals:
        - Download buttons or ``<a download>`` links
        - ``<audio>`` player elements
        - Error/failure messages (raises immediately)

        Args:
            timeout_ms: Maximum wait time in milliseconds (default 10 min).

        Returns:
            True when generation completes.

        Raises:
            LalalsDriverError: On timeout or if an error message is detected.
        """
        logger.info(f"Waiting for generation via DOM polling (timeout: {timeout_ms / 1000:.0f}s)...")
        start = time.time()
        timeout_s = timeout_ms / 1000
        poll_interval_ms = 3000
        # Grace period: don't check for errors in the first 15 seconds
        # to avoid false positives from page titles like "AI Lyrics Generator".
        error_grace_s = 15

        while time.time() - start < timeout_s:
            elapsed = time.time() - start

            # -- Check for error banners (after grace period) ---------------
            if elapsed >= error_grace_s:
                error_selectors = [
                    "text=/error occurred/i",
                    "text=/generation failed/i",
                    "text=/something went wrong/i",
                    "text=/please try again/i",
                    "text=/insufficient credits/i",
                    "text=/rate limit/i",
                ]
                for sel in error_selectors:
                    try:
                        loc = self.page.locator(sel)
                        if loc.count() > 0 and loc.first.is_visible(timeout=500):
                            text = loc.first.text_content() or "(no text)"
                            raise LalalsDriverError(
                                f"Generation error detected: {text}"
                            )
                    except LalalsDriverError:
                        raise
                    except Exception:
                        pass

            # -- Check for completion indicators ----------------------------
            completion_selectors = [
                "a[download]",
                "button:has-text('Download')",
                "a:has-text('Download')",
                "[data-testid*='download']",
                "audio",
            ]
            for sel in completion_selectors:
                try:
                    loc = self.page.locator(sel)
                    if loc.count() > 0 and loc.first.is_visible(timeout=500):
                        logger.info(
                            f"Generation complete (found '{sel}') "
                            f"after {elapsed:.1f}s"
                        )
                        return True
                except Exception:
                    pass

            if int(elapsed) % 15 == 0 and elapsed > 0:
                logger.info(f"Still waiting... ({elapsed:.0f}s elapsed)")

            self.page.wait_for_timeout(poll_interval_ms)

        raise LalalsDriverError(
            f"Generation timed out after {timeout_s:.0f}s"
        )

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------

    def download_songs(self) -> list[Download]:
        """Download the generated song files.

        Lalals typically generates 2 versions per request. This method finds
        all download elements and triggers up to 2 downloads.

        Returns:
            List of Playwright ``Download`` objects.

        Raises:
            LalalsDriverError: If no download elements or downloads are captured.
        """
        logger.info("Starting song downloads")

        download_selectors = [
            "a[download]",
            "button:has-text('Download')",
            "a:has-text('Download')",
            "[data-testid*='download']",
        ]

        download_elements = None
        for sel in download_selectors:
            loc = self.page.locator(sel)
            if loc.count() > 0:
                download_elements = loc
                logger.info(f"Download elements matched selector: {sel}")
                break

        if download_elements is None or download_elements.count() == 0:
            raise LalalsDriverError("No download buttons found")

        count = download_elements.count()
        logger.info(f"Found {count} download element(s)")

        downloads: list[Download] = []
        for i in range(min(count, 2)):  # download up to 2 versions
            try:
                with self.page.expect_download(timeout=60000) as download_info:
                    download_elements.nth(i).click()
                download = download_info.value
                downloads.append(download)
                logger.info(
                    f"Download {i + 1}/{min(count, 2)} captured: "
                    f"{download.suggested_filename}"
                )
                self.page.wait_for_timeout(2000)  # brief pause between downloads
            except Exception as exc:
                logger.warning(f"Download {i + 1} failed: {exc}")

        if not downloads:
            raise LalalsDriverError("No downloads were captured")

        logger.info(f"Total downloads captured: {len(downloads)}")
        return downloads

    def download_songs_v2(self, metadata: dict, download_dir: str, song_title: str) -> list[Path]:
        """Download audio via direct URLs from metadata, falling back to DOM clicks.

        Args:
            metadata: Dict from extract_metadata() with audio_url_1/audio_url_2 keys.
            download_dir: Base download directory path.
            song_title: Song title for filename generation.

        Returns:
            List of Paths to downloaded files.
        """
        from automation.download_manager import DownloadManager

        dm = DownloadManager(download_dir)
        paths = []

        for version in (1, 2):
            url = metadata.get(f"audio_url_{version}")
            if url:
                try:
                    path = dm.save_from_url(url, song_title, version)
                    paths.append(path)
                    logger.info(f"Downloaded v{version} via URL: {path}")
                except Exception as e:
                    logger.warning(f"URL download failed for v{version}: {e}")

        if not paths:
            # Fall back to DOM-based download
            logger.info("No URL downloads succeeded, falling back to DOM click download")
            try:
                pw_downloads = self.download_songs()
                for i, dl in enumerate(pw_downloads):
                    path = dm.save_playwright_download(dl, song_title, i + 1)
                    paths.append(path)
            except LalalsDriverError as e:
                logger.error(f"DOM download fallback also failed: {e}")

        return paths

    def fetch_fresh_urls(self, task_id: str, auth_token: str = "",
                         conversion_id_1: str = "", conversion_id_2: str = "") -> dict:
        """Fetch status and fresh download URLs via the documented byId endpoint.

        Documented endpoint:
            GET https://api.musicgpt.com/api/public/v1/byId
                ?conversionType=MUSIC_AI&task_id={task_id}

        Response on COMPLETED:
            {success: true, conversion: {task_id, status, audio_url, ...}}

        Also constructs direct S3 URLs from conversion_ids as fallback:
            https://lalals.s3.amazonaws.com/conversions/{conversion_id}.mp3

        Args:
            task_id: The MusicGPT task UUID.
            auth_token: Authorization header value captured during submit.
            conversion_id_1: First conversion UUID (for S3 URL fallback).
            conversion_id_2: Second conversion UUID (for S3 URL fallback).

        Returns:
            dict with metadata (audio_url_1, audio_url_2, status, etc).
        """
        logger.info(f"Fetching fresh URLs for task_id={task_id}")

        js = """
        async (args) => {
            const { taskId, authToken, cid1, cid2 } = args;
            const headers = {};
            if (authToken) {
                headers['Authorization'] = authToken;
            }

            // Strategy 1: byId with task_id (documented endpoint)
            const byIdUrl = `https://api.musicgpt.com/api/public/v1/byId?conversionType=MUSIC_AI&task_id=${taskId}`;
            try {
                const resp = await fetch(byIdUrl, {
                    headers,
                    credentials: 'include'
                });
                if (resp.ok) {
                    const data = await resp.json();
                    if (data && data.success !== false) {
                        return { source: 'byId_task', data: data };
                    }
                }
            } catch (e) {
                console.log('byId task_id failed:', e.message);
            }

            // Strategy 2: byId with conversion_id_1
            if (cid1) {
                try {
                    const url = `https://api.musicgpt.com/api/public/v1/byId?conversionType=MUSIC_AI&conversion_id=${cid1}`;
                    const resp = await fetch(url, { headers, credentials: 'include' });
                    if (resp.ok) {
                        const data = await resp.json();
                        if (data && data.success !== false) {
                            // Also try cid2
                            let data2 = null;
                            if (cid2) {
                                try {
                                    const url2 = `https://api.musicgpt.com/api/public/v1/byId?conversionType=MUSIC_AI&conversion_id=${cid2}`;
                                    const resp2 = await fetch(url2, { headers, credentials: 'include' });
                                    if (resp2.ok) data2 = await resp2.json();
                                } catch (e) {}
                            }
                            return { source: 'byId_cid', data: data, data2: data2 };
                        }
                    }
                } catch (e) {
                    console.log('byId conversion_id failed:', e.message);
                }
            }

            return null;
        }
        """

        try:
            result = self.page.evaluate(js, {
                "taskId": task_id,
                "authToken": auth_token,
                "cid1": conversion_id_1,
                "cid2": conversion_id_2,
            })

            if not result:
                logger.warning("No response from byId API")
                # Fallback: construct S3 URLs directly from conversion IDs
                return self._build_s3_metadata(
                    task_id, conversion_id_1, conversion_id_2
                )

            source = result.get("source", "")
            data = result.get("data", {})
            data2 = result.get("data2")

            logger.info(f"byId response via {source}")
            metadata = self.extract_metadata(data)

            # If we got a second response (per-conversion queries), merge audio_url_2
            if data2:
                meta2 = self.extract_metadata(data2)
                if meta2.get("audio_url_1") and not metadata.get("audio_url_2"):
                    metadata["audio_url_2"] = meta2["audio_url_1"]
                if meta2.get("conversion_id_1") and not metadata.get("conversion_id_2"):
                    metadata["conversion_id_2"] = meta2["conversion_id_1"]

            # Ensure we have S3 fallback URLs
            S3_BASE = "https://lalals.s3.amazonaws.com/conversions"
            cid1 = metadata.get("conversion_id_1") or conversion_id_1
            cid2 = metadata.get("conversion_id_2") or conversion_id_2
            if not metadata.get("audio_url_1") and cid1:
                metadata["audio_url_1"] = f"{S3_BASE}/{cid1}.mp3"
            if not metadata.get("audio_url_2") and cid2:
                metadata["audio_url_2"] = f"{S3_BASE}/{cid2}.mp3"

            logger.info(f"Fresh URLs: {[k for k in metadata if 'url' in k]}")
            return metadata

        except Exception as e:
            logger.error(f"Failed to fetch fresh URLs: {e}")
            return self._build_s3_metadata(
                task_id, conversion_id_1, conversion_id_2
            )

    @staticmethod
    def _build_s3_metadata(task_id: str, cid1: str, cid2: str) -> dict:
        """Build metadata dict with direct S3 URLs from conversion IDs.

        Documented URL pattern:
            https://lalals.s3.amazonaws.com/conversions/{conversion_id}.mp3
        """
        metadata = {}
        if task_id:
            metadata["task_id"] = task_id
        S3_BASE = "https://lalals.s3.amazonaws.com/conversions/standard"
        if cid1:
            metadata["conversion_id_1"] = cid1
            metadata["audio_url_1"] = f"{S3_BASE}/{cid1}/{cid1}.mp3"
        if cid2:
            metadata["conversion_id_2"] = cid2
            metadata["audio_url_2"] = f"{S3_BASE}/{cid2}/{cid2}.mp3"
        return metadata

    # ------------------------------------------------------------------
    # Submit (fire-and-forget — no wait for completion)
    # ------------------------------------------------------------------

    def submit_song(self, prompt: str, lyrics: str) -> tuple[str, dict]:
        """Submit a song: fill form, click generate, capture task_id.

        Does NOT wait for generation to complete.  Returns as soon as
        the generate button is clicked and the initial API response
        is captured.

        The MusicGPT API submit response contains:
            task_id, conversion_id_1, conversion_id_2, eta

        We also capture the Authorization token from outgoing requests
        so we can call the byId status endpoint later.

        Args:
            prompt: Song description prompt.
            lyrics: Full song lyrics.

        Returns:
            Tuple of (task_id, task_data_dict).
            task_data_dict has keys: task_id, conversion_id_1,
            conversion_id_2, auth_token, response (raw JSON).
        """
        logger.info("=== Submitting song ===")
        logger.info(f"  prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        logger.info(f"  lyrics: {len(lyrics)} chars")

        self.navigate_to_music()
        self.page.wait_for_timeout(2000)

        self.fill_prompt(prompt)
        self.fill_lyrics(lyrics)

        # Intercept requests (for auth token) and responses (for task data)
        task_data = {}

        def on_request(request):
            url = request.url
            if "musicgpt.com" in url or "lalals.com/api" in url:
                headers = request.headers
                auth = headers.get("authorization", "")
                if auth and not task_data.get("auth_token"):
                    task_data["auth_token"] = auth
                    logger.info(f"Captured auth token: {auth[:30]}...")

        def on_response(response):
            url = response.url
            if not ("musicgpt.com" in url or "lalals.com/api" in url):
                return
            try:
                body = response.json()
                if not isinstance(body, dict):
                    return
                if task_data.get("task_id"):
                    return  # already captured

                # Documented submit response: {task_id, conversion_id_1, conversion_id_2, eta}
                src = body
                if isinstance(body.get("data"), dict):
                    src = body["data"]

                tid = src.get("task_id") or src.get("taskId")
                if tid:
                    task_data["task_id"] = str(tid)
                    task_data["conversion_id_1"] = str(src.get("conversion_id_1", ""))
                    task_data["conversion_id_2"] = str(src.get("conversion_id_2", ""))
                    task_data["eta"] = src.get("eta")
                    task_data["response"] = body
                    logger.info(
                        f"Captured: task_id={tid}, "
                        f"cid1={task_data['conversion_id_1']}, "
                        f"cid2={task_data['conversion_id_2']}, "
                        f"eta={task_data.get('eta')}"
                    )
            except Exception:
                pass

        self.page.on("request", on_request)
        self.page.on("response", on_response)
        self.click_generate()

        # Brief wait to capture the initial response
        self.page.wait_for_timeout(8000)

        try:
            self.page.remove_listener("request", on_request)
            self.page.remove_listener("response", on_response)
        except Exception:
            pass

        task_id = task_data.get("task_id", "")
        logger.info(f"=== Song submitted (task_id={task_id or 'not captured'}) ===")
        return task_id, task_data

    # ------------------------------------------------------------------
    # Home page navigation + download
    # ------------------------------------------------------------------

    def go_to_home_page(self):
        """Navigate to the Home/workspace page showing latest generations.

        Tries the sidebar Home button first, then falls back to the
        root URL.
        """
        logger.info("Navigating to Home page...")

        selectors = [
            'a:has-text("Home")',
            'button:has-text("Home")',
            'nav a:has-text("Home")',
            'a[href="/"]',
            'a[href="/home"]',
            'a[href="/workspace"]',
            '[data-name="Home"]',
            '[data-testid="home"]',
        ]

        for sel in selectors:
            try:
                loc = self.page.locator(sel).first
                if loc.is_visible(timeout=2000):
                    loc.click()
                    self.page.wait_for_timeout(2000)
                    try:
                        self.page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                    logger.info(f"Navigated via Home button ({sel})")
                    return
            except Exception:
                continue

        # Fallback: direct navigation
        logger.info("Home button not found — navigating directly")
        self.page.goto("https://lalals.com", wait_until="domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        self.page.wait_for_timeout(3000)

    def download_from_home(self, song_title: str, download_dir: str) -> list[Path]:
        """Download a song from the Home page via the three-dot menu.

        Finds the generation card matching *song_title*, opens its
        three-dot menu, and clicks Download -> Full Song.

        Args:
            song_title: Song title to locate on the page.
            download_dir: Base download directory.

        Returns:
            List of saved file paths (may be empty on failure).
        """
        from automation.download_manager import DownloadManager
        dm = DownloadManager(download_dir)

        try:
            # Find the card by title text
            card = self.page.locator(f'text="{song_title}"').first
            if not card.is_visible(timeout=3000):
                short = song_title[:30].replace('"', '\\"')
                card = self.page.locator(f'text=/{short}/i').first
                if not card.is_visible(timeout=2000):
                    logger.info(f"Card not found for '{song_title}'")
                    return []

            # Find three-dot / menu button near the card
            menu_clicked = False
            for sel in (
                'xpath=ancestor::*[position() <= 5]//button[contains(@class, "menu") or contains(@class, "dot") or contains(@class, "more")]',
                'xpath=ancestor::*[position() <= 5]//button[last()]',
            ):
                try:
                    btn = card.locator(sel).first
                    if btn.is_visible(timeout=1000):
                        btn.click()
                        self.page.wait_for_timeout(1000)
                        menu_clicked = True
                        break
                except Exception:
                    continue

            if not menu_clicked:
                logger.info("Three-dot menu not found")
                return []

            # Click "Download"
            dl = self.page.locator('text="Download"').first
            if not dl.is_visible(timeout=2000):
                self.page.keyboard.press("Escape")
                return []
            dl.click()
            self.page.wait_for_timeout(1000)

            # Click "Full Song" — version 1
            full = self.page.locator('text="Full Song"').first
            if not full.is_visible(timeout=2000):
                self.page.keyboard.press("Escape")
                return []

            with self.page.expect_download(timeout=30000) as dl_info:
                full.click()
            download = dl_info.value

            path1 = dm.save_playwright_download(download, song_title, 1)
            logger.info(f"Downloaded v1 from Home: {path1}")
            paths = [path1]

            # Try to grab version 2 — re-open menu and look for a second option
            self.page.wait_for_timeout(1500)
            try:
                # Dismiss any open menus first
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(500)

                # Re-find the card and re-open three-dot menu
                card2 = self.page.locator(f'text="{song_title}"').first
                if card2.is_visible(timeout=2000):
                    for sel in (
                        'xpath=ancestor::*[position() <= 5]//button[contains(@class, "menu") or contains(@class, "dot") or contains(@class, "more")]',
                        'xpath=ancestor::*[position() <= 5]//button[last()]',
                    ):
                        try:
                            btn = card2.locator(sel).first
                            if btn.is_visible(timeout=1000):
                                btn.click()
                                self.page.wait_for_timeout(1000)
                                break
                        except Exception:
                            continue

                    # Click "Download" again
                    dl2 = self.page.locator('text="Download"').first
                    if dl2.is_visible(timeout=1500):
                        dl2.click()
                        self.page.wait_for_timeout(1000)

                        # Look for "Full Song" items — there may be 2
                        full_songs = self.page.locator('text="Full Song"')
                        count = full_songs.count()
                        if count >= 2:
                            with self.page.expect_download(timeout=30000) as dl_info2:
                                full_songs.nth(1).click()
                            download2 = dl_info2.value
                            path2 = dm.save_playwright_download(download2, song_title, 2)
                            paths.append(path2)
                            logger.info(f"Downloaded v2 from Home: {path2}")
                        else:
                            logger.info(f"Only {count} 'Full Song' option(s) found, no v2")
                            self.page.keyboard.press("Escape")
            except Exception as e:
                logger.info(f"Version 2 Home download attempt: {e}")

            return paths

        except Exception as e:
            logger.warning(f"Home page download failed: {e}")
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass
            return []

    # ------------------------------------------------------------------
    # Full pipeline (legacy — kept for reference)
    # ------------------------------------------------------------------

    def process_song(
        self,
        prompt: str,
        lyrics: str,
        timeout_ms: int = 600_000,
        stop_flag=None,
        progress_callback=None,
        download_dir: str = None,
    ) -> tuple[list, dict]:
        """Legacy full pipeline: fill fields, generate, wait, download.

        NOTE: The active pipeline now uses submit_song() + manual refresh.
        This method is kept for backward compatibility / testing.
        """
        logger.info("=== Starting song processing pipeline (legacy) ===")
        task_id, resp = self.submit_song(prompt, lyrics)
        metadata = self.extract_metadata(resp) if resp else {}
        if task_id:
            metadata["task_id"] = task_id

        # Download via URLs if metadata available, else DOM fallback
        if metadata and download_dir:
            title = prompt[:50].strip()
            paths = self.download_songs_v2(metadata, download_dir, title)
            return (paths, metadata)
        else:
            downloads = self.download_songs()
            return (downloads, metadata)

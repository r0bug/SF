"""DistroKid page interaction driver for Song Factory automation.

Handles login detection, upload form filling, file upload, and genre mapping
for distrokid.com via Playwright browser automation.
"""

import time
import logging
from pathlib import Path
from playwright.sync_api import Page, BrowserContext

logger = logging.getLogger("songfactory.automation")

DK_STATE_FILE = Path.home() / ".songfactory" / "dk_browser_state.json"

# ---------------------------------------------------------------------------
# Genre mapping: Song Factory genre name -> DistroKid genre name
# DistroKid's genre list (~22 genres) is a fixed dropdown.
# ---------------------------------------------------------------------------

GENRE_MAP = {
    "Pop":                  "Pop",
    "Hip-Hop":              "Hip-Hop/Rap",
    "Rock":                 "Rock",
    "Country":              "Country",
    "Latin / Reggaeton":    "Latin",
    "EDM / Dance":          "Dance",
    "R&B / Soul":           "R&B/Soul",
    "Indie Pop":            "Pop",
    "Afrobeats":            "Worldwide",
    "K-Pop":                "K-Pop",
    "Folk / Americana":     "Singer/Songwriter",
    "Lo-Fi Hip-Hop":        "Hip-Hop/Rap",
    "Funk":                 "Funk",
    "Country Rock":         "Country",
    "Electropop":           "Electronic",
    "Reggae":               "Reggae",
    "Melodic Rap":          "Hip-Hop/Rap",
    "Tech House":           "Dance",
    "Pop R&B":              "R&B/Soul",
    "Alt-Rock":             "Alternative",
    "Indie Pop-Rock":       "Alternative",
    "Country Spoken Word":  "Country",
    "Comedy Hip-Hop":       "Hip-Hop/Rap",
}

# DistroKid's full genre list for validation
DK_GENRES = [
    "Alternative", "Anime", "Blues", "Children's Music", "Classical",
    "Comedy", "Country", "Dance", "Electronic", "Fitness & Workout",
    "Funk", "Hip-Hop/Rap", "Holiday", "Inspirational", "Jazz",
    "K-Pop", "Latin", "Metal", "New Age", "Pop", "R&B/Soul",
    "Reggae", "Rock", "Singer/Songwriter", "Soul", "Soundtrack",
    "Spoken Word", "Vocal", "Worldwide",
]


def map_genre(sf_genre: str) -> str:
    """Map a Song Factory genre name to the closest DistroKid genre.

    Args:
        sf_genre: Song Factory genre name (e.g. "EDM / Dance").

    Returns:
        DistroKid genre name. Falls back to "Pop" if no match.
    """
    return GENRE_MAP.get(sf_genre, "Pop")


class DistroKidDriverError(Exception):
    """Raised when a DistroKid interaction fails."""
    pass


class DistroKidDriver:
    """Handles all interactions with distrokid.com pages.

    Uses resilient selector strategies similar to LalalsDriver.
    """

    UPLOAD_URL = "https://distrokid.com/upload/"
    SIGNIN_URL = "https://distrokid.com/signin/"
    MYMUSIC_URL = "https://distrokid.com/mymusic/"

    def __init__(self, page: Page, context: BrowserContext):
        self.page = page
        self.context = context

    # ------------------------------------------------------------------
    # Selector helpers
    # ------------------------------------------------------------------

    def _find_visible(self, selectors: list[str], *, timeout: int = 3000):
        """Return the first visible locator matching any of *selectors*."""
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
        """Check if the current session is authenticated on DistroKid.

        Navigates to /mymusic/ and checks if we get redirected to /signin/.
        """
        logger.info("Checking DistroKid login status...")
        self.page.goto(self.MYMUSIC_URL, wait_until="domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        url = self.page.url
        logged_in = "/signin" not in url.lower()
        logger.info(f"DistroKid logged in: {logged_in} (url={url})")
        return logged_in

    def open_login_page(self):
        """Navigate to the DistroKid sign-in page for manual authentication."""
        logger.info("Opening DistroKid login page...")
        self.page.goto(self.SIGNIN_URL, wait_until="domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

    def wait_for_manual_login(self, timeout_s: int = 600, stop_flag=None) -> bool:
        """Wait for the user to complete manual login + 2FA.

        Polls every 3 seconds, checking if the URL has left /signin/.

        Args:
            timeout_s: Max seconds to wait (default 10 minutes for 2FA).
            stop_flag: Optional callable returning True to abort early.

        Returns:
            True when login is detected.

        Raises:
            DistroKidDriverError: If timeout expires before login completes.
        """
        logger.info(f"Waiting for DistroKid manual login (timeout: {timeout_s}s)...")
        start = time.time()

        while time.time() - start < timeout_s:
            if stop_flag and stop_flag():
                raise DistroKidDriverError("Login wait cancelled by user")

            try:
                url = self.page.url
                if "/signin" not in url.lower() and "distrokid.com" in url.lower():
                    logger.info(f"DistroKid login detected (url={url})")
                    self.save_state()
                    return True
            except Exception:
                pass

            self.page.wait_for_timeout(3000)

        raise DistroKidDriverError(
            f"DistroKid login timed out after {timeout_s}s"
        )

    def save_state(self):
        """Save browser storage state for session persistence."""
        DK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=str(DK_STATE_FILE))
        logger.info(f"DistroKid browser state saved to {DK_STATE_FILE}")

    # ------------------------------------------------------------------
    # Upload form
    # ------------------------------------------------------------------

    def navigate_to_upload(self):
        """Navigate to the DistroKid upload page.

        Raises:
            DistroKidDriverError: If redirected to login.
        """
        logger.info("Navigating to DistroKid upload page...")
        self.page.goto(self.UPLOAD_URL, wait_until="domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        if "/signin" in self.page.url.lower():
            raise DistroKidDriverError(
                "Redirected to login — session may have expired"
            )
        logger.info(f"On upload page (url={self.page.url})")

    def select_artist(self, artist_name: str):
        """Select the artist from the artist dropdown.

        Args:
            artist_name: Artist name to select (must be registered on DK).

        Raises:
            DistroKidDriverError: If the artist cannot be found.
        """
        logger.info(f"Selecting artist: {artist_name}")

        # DK uses a dropdown/select for registered artists
        artist_sel = self._find_visible(
            [
                'select[name*="artist"]',
                '#artist-select',
                'select:near(:text("Artist"))',
            ],
            timeout=5000,
        )

        if artist_sel:
            try:
                artist_sel.select_option(label=artist_name)
                logger.info(f"Artist selected via dropdown: {artist_name}")
                return
            except Exception as e:
                logger.warning(f"Dropdown select failed: {e}")

        # Fallback: click a radio/link with the artist name
        artist_link = self._find_visible(
            [
                f'text="{artist_name}"',
                f'label:has-text("{artist_name}")',
                f'a:has-text("{artist_name}")',
                f'div:has-text("{artist_name}")',
            ],
            timeout=5000,
        )

        if artist_link:
            artist_link.click()
            logger.info(f"Artist clicked: {artist_name}")
        else:
            raise DistroKidDriverError(
                f"Could not find artist '{artist_name}' on the upload page"
            )

    def fill_release_title(self, title: str):
        """Fill the release/album title field."""
        logger.info(f"Filling release title: {title}")

        title_input = self._find_visible(
            [
                'input[name*="title"]',
                'input[name*="album"]',
                'input[placeholder*="itle"]',
                'input[placeholder*="release"]',
                '#title',
                '#albumTitle',
            ],
            timeout=5000,
        )

        if title_input is None:
            raise DistroKidDriverError("Could not find release title field")

        title_input.click()
        title_input.fill(title)
        logger.info("Release title filled")

    def select_genre(self, dk_genre: str):
        """Select the primary genre from DistroKid's genre dropdown.

        Args:
            dk_genre: DistroKid genre name (from GENRE_MAP values or DK_GENRES).
        """
        logger.info(f"Selecting genre: {dk_genre}")

        genre_sel = self._find_visible(
            [
                'select[name*="genre"]',
                'select[name*="Genre"]',
                '#genre',
                '#primaryGenre',
                'select:near(:text("Genre"))',
            ],
            timeout=5000,
        )

        if genre_sel:
            try:
                genre_sel.select_option(label=dk_genre)
                logger.info(f"Genre selected: {dk_genre}")
                return
            except Exception:
                # Try by value
                try:
                    genre_sel.select_option(value=dk_genre)
                    logger.info(f"Genre selected by value: {dk_genre}")
                    return
                except Exception as e:
                    logger.warning(f"Genre dropdown select failed: {e}")

        raise DistroKidDriverError(f"Could not select genre '{dk_genre}'")

    def select_language(self, language: str = "English"):
        """Select the language from the language dropdown."""
        logger.info(f"Selecting language: {language}")

        lang_sel = self._find_visible(
            [
                'select[name*="language"]',
                'select[name*="Language"]',
                '#language',
                'select:near(:text("Language"))',
            ],
            timeout=5000,
        )

        if lang_sel:
            try:
                lang_sel.select_option(label=language)
                logger.info(f"Language selected: {language}")
                return
            except Exception as e:
                logger.warning(f"Language select failed: {e}")

    def fill_songwriter(self, songwriter: str):
        """Fill the songwriter/composer field (legal name)."""
        logger.info(f"Filling songwriter: {songwriter}")

        songwriter_input = self._find_visible(
            [
                'input[name*="songwriter"]',
                'input[name*="writer"]',
                'input[name*="composer"]',
                'input[placeholder*="ongwriter"]',
                'input[placeholder*="legal name"]',
                'input:near(:text("Songwriter"))',
            ],
            timeout=5000,
        )

        if songwriter_input:
            songwriter_input.click()
            songwriter_input.fill(songwriter)
            logger.info("Songwriter filled")
        else:
            logger.warning("Could not find songwriter field")

    def upload_audio_file(self, file_path: str):
        """Upload the audio file to the upload form.

        Args:
            file_path: Absolute path to the audio file (WAV, MP3, FLAC, etc.).

        Raises:
            DistroKidDriverError: If the file input cannot be found.
        """
        logger.info(f"Uploading audio file: {file_path}")

        if not Path(file_path).is_file():
            raise DistroKidDriverError(f"Audio file not found: {file_path}")

        file_input = self._find_visible(
            [
                'input[type="file"][accept*="audio"]',
                'input[type="file"][accept*=".wav"]',
                'input[type="file"][accept*=".mp3"]',
                'input[type="file"]',
            ],
            timeout=5000,
        )

        if file_input is None:
            # Try hidden file inputs
            file_input = self.page.locator('input[type="file"]').first
            if file_input.count() == 0:
                raise DistroKidDriverError("Could not find file upload input")

        file_input.set_input_files(file_path)
        logger.info("Audio file uploaded")
        self.page.wait_for_timeout(2000)

    def upload_cover_art(self, art_path: str):
        """Upload cover art to the upload form.

        Args:
            art_path: Absolute path to the cover art image (JPG/PNG).

        Raises:
            DistroKidDriverError: If the art upload input cannot be found.
        """
        logger.info(f"Uploading cover art: {art_path}")

        if not Path(art_path).is_file():
            raise DistroKidDriverError(f"Cover art file not found: {art_path}")

        # Cover art file input — often a separate input[type="file"]
        art_inputs = self.page.locator('input[type="file"]')
        count = art_inputs.count()

        if count >= 2:
            # Typically the second file input is for cover art
            art_inputs.nth(1).set_input_files(art_path)
            logger.info("Cover art uploaded (second file input)")
        elif count == 1:
            # Only one input — may need to look for art-specific one
            art_input = self._find_visible(
                [
                    'input[type="file"][accept*="image"]',
                    'input[type="file"][accept*=".jpg"]',
                    'input[type="file"][accept*=".png"]',
                ],
                timeout=3000,
            )
            if art_input:
                art_input.set_input_files(art_path)
                logger.info("Cover art uploaded (image-specific input)")
            else:
                logger.warning("Could not find a dedicated cover art input")
        else:
            raise DistroKidDriverError("No file inputs found for cover art")

        self.page.wait_for_timeout(2000)

    def set_instrumental(self, is_instrumental: bool = False):
        """Set the instrumental checkbox."""
        logger.info(f"Setting instrumental: {is_instrumental}")

        checkbox = self._find_visible(
            [
                'input[type="checkbox"][name*="instrumental"]',
                'input[type="checkbox"]:near(:text("Instrumental"))',
                'label:has-text("Instrumental") input[type="checkbox"]',
            ],
            timeout=3000,
        )

        if checkbox:
            is_checked = checkbox.is_checked()
            if is_instrumental and not is_checked:
                checkbox.click()
            elif not is_instrumental and is_checked:
                checkbox.click()
            logger.info(f"Instrumental set to {is_instrumental}")
        else:
            logger.warning("Could not find instrumental checkbox")

    def set_ai_disclosure(self, ai_generated: bool = True):
        """Check the AI-generated content disclosure checkbox."""
        logger.info(f"Setting AI disclosure: {ai_generated}")

        checkbox = self._find_visible(
            [
                'input[type="checkbox"][name*="ai"]',
                'input[type="checkbox"]:near(:text("AI"))',
                'label:has-text("AI") input[type="checkbox"]',
                'input[type="checkbox"]:near(:text("artificial"))',
            ],
            timeout=3000,
        )

        if checkbox:
            is_checked = checkbox.is_checked()
            if ai_generated and not is_checked:
                checkbox.click()
            elif not ai_generated and is_checked:
                checkbox.click()
            logger.info(f"AI disclosure set to {ai_generated}")
        else:
            logger.warning(
                "Could not find AI disclosure checkbox — "
                "it may appear later in the upload flow"
            )

    def click_upload(self):
        """Click the final upload/submit button.

        Raises:
            DistroKidDriverError: If the upload button cannot be found.
        """
        logger.info("Clicking upload button...")

        upload_btn = self._find_visible(
            [
                "button:has-text('Upload')",
                "button:has-text('Submit')",
                "button[type='submit']",
                "input[type='submit']",
                "a:has-text('Upload')",
                "button:has-text('Continue')",
            ],
            timeout=5000,
        )

        if upload_btn is None:
            raise DistroKidDriverError("Could not find upload/submit button")

        upload_btn.click()
        logger.info("Upload button clicked")

    def wait_for_upload_complete(self, timeout_s: int = 300, stop_flag=None) -> bool:
        """Wait for the upload to complete by monitoring the page.

        Polls for success indicators (confirmation message, redirect to
        mymusic page, etc.).

        Args:
            timeout_s: Max seconds to wait.
            stop_flag: Optional callable returning True to abort.

        Returns:
            True when upload appears complete.

        Raises:
            DistroKidDriverError: On timeout or error detection.
        """
        logger.info(f"Waiting for upload to complete (timeout: {timeout_s}s)...")
        start = time.time()

        while time.time() - start < timeout_s:
            if stop_flag and stop_flag():
                raise DistroKidDriverError("Upload wait cancelled by user")

            url = self.page.url

            # Success indicators
            if "/mymusic" in url.lower():
                logger.info("Upload complete — redirected to mymusic")
                return True

            # Check for success messages on the page
            success_sel = self._find_visible(
                [
                    'text=/success/i',
                    'text=/uploaded/i',
                    'text=/congratulations/i',
                    'text=/your release/i',
                ],
                timeout=1000,
            )
            if success_sel:
                logger.info("Upload complete — success message detected")
                return True

            # Check for error messages
            error_sel = self._find_visible(
                [
                    'text=/error/i',
                    'text=/failed/i',
                    'text=/problem/i',
                ],
                timeout=500,
            )
            if error_sel:
                try:
                    text = error_sel.text_content()
                except Exception:
                    text = "(unreadable)"
                raise DistroKidDriverError(f"Upload error: {text}")

            self.page.wait_for_timeout(3000)

        raise DistroKidDriverError(
            f"Upload timed out after {timeout_s}s"
        )

    # ------------------------------------------------------------------
    # Full upload pipeline
    # ------------------------------------------------------------------

    def fill_upload_form(self, release: dict):
        """Fill the entire DistroKid upload form from a distribution record.

        Args:
            release: dict with keys matching the distributions table columns:
                artist_name, album_title, songwriter, primary_genre,
                language, cover_art_path, is_instrumental, ai_disclosure,
                and the song's file_path_1 for the audio file.
        """
        logger.info("=== Filling DistroKid upload form ===")

        self.navigate_to_upload()
        self.page.wait_for_timeout(3000)

        # Artist
        artist = release.get("artist_name", "Yakima Finds")
        try:
            self.select_artist(artist)
        except DistroKidDriverError:
            logger.warning(f"Artist '{artist}' not found — may need manual selection")

        # Release title
        title = release.get("album_title") or release.get("title", "")
        if title:
            self.fill_release_title(title)

        # Genre
        sf_genre = release.get("primary_genre", "Pop")
        dk_genre = map_genre(sf_genre)
        try:
            self.select_genre(dk_genre)
        except DistroKidDriverError:
            logger.warning(f"Genre '{dk_genre}' select failed — may need manual selection")

        # Language
        language = release.get("language", "English")
        self.select_language(language)

        # Songwriter
        songwriter = release.get("songwriter", "")
        if songwriter:
            self.fill_songwriter(songwriter)

        # Audio file
        audio_path = release.get("audio_path", "")
        if audio_path and Path(audio_path).is_file():
            self.upload_audio_file(audio_path)
        else:
            logger.warning(f"No valid audio file path: {audio_path}")

        # Cover art
        art_path = release.get("cover_art_path", "")
        if art_path and Path(art_path).is_file():
            self.upload_cover_art(art_path)
        else:
            logger.warning(f"No valid cover art path: {art_path}")

        # Instrumental flag
        self.set_instrumental(bool(release.get("is_instrumental", False)))

        # AI disclosure
        self.set_ai_disclosure(bool(release.get("ai_disclosure", True)))

        logger.info("=== Upload form filled ===")

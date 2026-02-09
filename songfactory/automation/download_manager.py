"""Download manager for Song Factory — handles file downloads and organization."""

import re
import logging
import urllib.request
import urllib.error
from pathlib import Path

logger = logging.getLogger("songfactory.automation")


class DownloadManager:
    """Handles file downloads and organization for generated songs."""

    def __init__(self, base_dir: str):
        """
        Args:
            base_dir: Root download directory, e.g. ~/Music/SongFactory/
        """
        self.base_dir = Path(base_dir).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _slugify(self, text: str) -> str:
        """Convert a song title to a filesystem-safe slug.

        Example: "Treasure on Second Street" -> "treasure-on-second-street"
        """
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)  # remove non-alphanumeric except hyphens
        text = re.sub(r'[\s_]+', '-', text)    # replace spaces/underscores with hyphens
        text = re.sub(r'-+', '-', text)        # collapse multiple hyphens
        text = text.strip('-')
        return text or "untitled"

    def get_song_dir(self, song_title: str) -> Path:
        """Create and return a directory for this song's files.

        Example: ~/Music/SongFactory/treasure-on-second-street/
        """
        slug = self._slugify(song_title)
        song_dir = self.base_dir / slug
        song_dir.mkdir(parents=True, exist_ok=True)
        return song_dir

    def get_track_file_path(self, song_title: str, track_type: str, extension: str = ".mp3") -> Path:
        """Get the target file path for a specific track type.

        Args:
            song_title: The song title
            track_type: Track type label (e.g. "vocals", "instrumental", "full_song")
            extension: File extension including dot (e.g. ".mp3")

        Returns:
            Path like ~/Music/SongFactory/treasure-on-second-street/treasure-on-second-street_vocals.mp3
        """
        slug = self._slugify(song_title)
        song_dir = self.get_song_dir(song_title)
        # Sanitize track_type for filename
        safe_type = re.sub(r'[^\w]', '_', track_type.lower().strip())
        filename = f"{slug}_{safe_type}{extension}"
        return song_dir / filename

    def get_file_path(self, song_title: str, version: int, extension: str = ".mp3") -> Path:
        """Get the target file path for a song version.

        Args:
            song_title: The song title
            version: Version number (1 or 2)
            extension: File extension including dot (e.g. ".mp3", ".wav")

        Returns:
            Path like ~/Music/SongFactory/treasure-on-second-street/treasure-on-second-street_v1.mp3
        """
        slug = self._slugify(song_title)
        song_dir = self.get_song_dir(song_title)
        filename = f"{slug}_v{version}{extension}"
        return song_dir / filename

    def save_playwright_download(self, download, song_title: str, version: int) -> Path:
        """Save a Playwright download object to the proper location.

        Args:
            download: Playwright Download object
            song_title: The song title
            version: Version number (1 or 2)

        Returns:
            Path to the saved file
        """
        # Detect extension from the suggested filename
        suggested = download.suggested_filename
        extension = Path(suggested).suffix if suggested else ".mp3"
        if not extension:
            extension = ".mp3"

        target_path = self.get_file_path(song_title, version, extension)
        logger.info(f"Saving download to: {target_path}")
        download.save_as(str(target_path))
        return target_path

    def get_existing_files(self, song_title: str) -> list[Path]:
        """Get list of already-downloaded files for a song."""
        song_dir = self.get_song_dir(song_title)
        if song_dir.exists():
            return sorted(song_dir.iterdir())
        return []

    def save_from_url(self, url: str, song_title: str, version: int) -> Path:
        """Download audio directly from a URL (S3/CloudFront) without browser.

        Args:
            url: Direct audio file URL.
            song_title: The song title (used for directory/filename).
            version: Version number (1 or 2).

        Returns:
            Path to the saved file.

        Raises:
            urllib.error.URLError: If the download fails.
        """
        # Detect extension from URL path
        from urllib.parse import urlparse
        parsed = urlparse(url)
        url_path = parsed.path
        suffix = Path(url_path).suffix if url_path else ""
        if suffix not in (".mp3", ".wav", ".ogg", ".flac", ".m4a"):
            suffix = ".mp3"  # default

        target_path = self.get_file_path(song_title, version, suffix)
        logger.info(f"Downloading v{version} from URL to: {target_path}")
        logger.info(f"  URL: {url[:120]}...")

        try:
            urllib.request.urlretrieve(url, str(target_path))
            file_size = target_path.stat().st_size
            logger.info(f"  Downloaded {file_size:,} bytes")
        except urllib.error.URLError as e:
            logger.error(f"  Download failed: {e}")
            raise

        return target_path

    def save_playwright_download_track(self, download, song_title: str, track_type: str) -> Path:
        """Save a Playwright download object with a track-type suffix.

        Args:
            download: Playwright Download object
            song_title: The song title
            track_type: Track type label (e.g. "vocals", "instrumental", "full_song")

        Returns:
            Path to the saved file
        """
        suggested = download.suggested_filename
        extension = Path(suggested).suffix if suggested else ".mp3"
        if not extension:
            extension = ".mp3"

        target_path = self.get_track_file_path(song_title, track_type, extension)
        logger.info(f"Saving {track_type} download to: {target_path}")
        download.save_as(str(target_path))
        return target_path

    def save_from_url_track(self, url: str, song_title: str, track_type: str) -> Path:
        """Download audio from a URL and save with a track-type suffix.

        Args:
            url: Direct audio file URL.
            song_title: The song title (used for directory/filename).
            track_type: Track type label (e.g. "vocals", "instrumental", "full_song").

        Returns:
            Path to the saved file.

        Raises:
            urllib.error.URLError: If the download fails.
        """
        from urllib.parse import urlparse
        parsed = urlparse(url)
        url_path = parsed.path
        suffix = Path(url_path).suffix if url_path else ""
        if suffix not in (".mp3", ".wav", ".ogg", ".flac", ".m4a"):
            suffix = ".mp3"

        target_path = self.get_track_file_path(song_title, track_type, suffix)
        logger.info(f"Downloading {track_type} from URL to: {target_path}")
        logger.info(f"  URL: {url[:120]}...")

        try:
            urllib.request.urlretrieve(url, str(target_path))
            file_size = target_path.stat().st_size
            logger.info(f"  Downloaded {file_size:,} bytes")
        except urllib.error.URLError as e:
            logger.error(f"  Download failed: {e}")
            raise

        return target_path

"""Download manager for Song Factory — handles file downloads and organization."""

import re
import logging
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

from automation.atomic_io import atomic_write_fn

logger = logging.getLogger("songfactory.automation")

# Minimum file size for a valid audio file (10 KB)
MIN_AUDIO_BYTES = 10240


class DownloadVerificationError(Exception):
    """Raised when a downloaded file fails audio validation."""

    def __init__(self, message: str, actual_size: int = 0, expected_size: int = 0):
        super().__init__(message)
        self.actual_size = actual_size
        self.expected_size = expected_size


class DownloadManager:
    """Handles file downloads and organization for generated songs."""

    def __init__(self, base_dir: str):
        """
        Args:
            base_dir: Root download directory, e.g. ~/Music/SongFactory/
        """
        self.base_dir = Path(base_dir).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.last_download_size = 0

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

    def get_song_dir(self, song_title: str, date_prefix: str = "") -> Path:
        """Create and return a directory for this song's files.

        Args:
            song_title: The song title.
            date_prefix: Date string prefix for the directory name.
                When empty (default), uses today's date (YYYY-MM-DD).

        Example: ~/Music/SongFactory/2026-02-12_treasure-on-second-street/
        """
        slug = self._slugify(song_title)
        prefix = date_prefix or date.today().isoformat()
        song_dir = self.base_dir / f"{prefix}_{slug}"
        song_dir.mkdir(parents=True, exist_ok=True)
        return song_dir

    def get_track_file_path(self, song_title: str, track_type: str, extension: str = ".mp3",
                            date_prefix: str = "") -> Path:
        """Get the target file path for a specific track type.

        Args:
            song_title: The song title
            track_type: Track type label (e.g. "vocals", "instrumental", "full_song")
            extension: File extension including dot (e.g. ".mp3")
            date_prefix: Date string prefix for the directory name.

        Returns:
            Path like ~/Music/SongFactory/2026-02-12_treasure-on-second-street/treasure-on-second-street_vocals.mp3
        """
        slug = self._slugify(song_title)
        song_dir = self.get_song_dir(song_title, date_prefix=date_prefix)
        # Sanitize track_type for filename
        safe_type = re.sub(r'[^\w]', '_', track_type.lower().strip())
        filename = f"{slug}_{safe_type}{extension}"
        return song_dir / filename

    def get_file_path(self, song_title: str, version: int, extension: str = ".mp3",
                      date_prefix: str = "") -> Path:
        """Get the target file path for a song version.

        Args:
            song_title: The song title
            version: Version number (1 or 2)
            extension: File extension including dot (e.g. ".mp3", ".wav")
            date_prefix: Date string prefix for the directory name.

        Returns:
            Path like ~/Music/SongFactory/2026-02-12_treasure-on-second-street/treasure-on-second-street_v1.mp3
        """
        slug = self._slugify(song_title)
        song_dir = self.get_song_dir(song_title, date_prefix=date_prefix)
        filename = f"{slug}_v{version}{extension}"
        return song_dir / filename

    def save_playwright_download(self, download, song_title: str, version: int) -> Path:
        """Save a Playwright download object to the proper location.

        Uses atomic write: Playwright saves to a temp file first, then the
        temp file is renamed to the target path so partial files never appear.

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
        atomic_write_fn(str(target_path), lambda tmp: download.save_as(tmp))

        file_size = target_path.stat().st_size
        self.last_download_size = file_size

        validation = self.validate_audio_file(target_path)
        if not validation["valid"]:
            errors = "; ".join(validation["errors"])
            logger.error(f"  Playwright download validation failed: {errors}")
            try:
                target_path.unlink()
            except OSError:
                pass
            raise DownloadVerificationError(
                f"Invalid audio file from browser download: {errors}",
                actual_size=validation["size"],
            )

        return target_path

    def get_existing_files(self, song_title: str, date_prefix: str = "") -> list[Path]:
        """Get list of already-downloaded files for a song."""
        song_dir = self.get_song_dir(song_title, date_prefix=date_prefix)
        if song_dir.exists():
            return sorted(song_dir.iterdir())
        return []

    @staticmethod
    def validate_audio_file(path) -> dict:
        """Check that a file is a valid audio file by size and header.

        Args:
            path: Path to the file (str or Path).

        Returns:
            dict with keys: valid (bool), size (int), format (str|None),
            errors (list[str]).
        """
        path = Path(path)
        result = {"valid": False, "size": 0, "format": None, "errors": []}

        if not path.exists():
            result["errors"].append("File does not exist")
            return result

        size = path.stat().st_size
        result["size"] = size

        if size < MIN_AUDIO_BYTES:
            result["errors"].append(
                f"File too small ({size} bytes, minimum {MIN_AUDIO_BYTES})"
            )
            return result

        try:
            with open(path, "rb") as f:
                header = f.read(4)
        except OSError as e:
            result["errors"].append(f"Cannot read file: {e}")
            return result

        if len(header) < 4:
            result["errors"].append(f"File too short to identify ({len(header)} bytes header)")
            return result

        # MP3: sync word 0xFF followed by byte with top 3 bits set (0xE0)
        if header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
            result["valid"] = True
            result["format"] = "mp3"
            return result

        # ID3 tag (MP3 with metadata header)
        if header[:3] == b"ID3":
            result["valid"] = True
            result["format"] = "mp3/id3"
            return result

        # WAV/RIFF
        if header[:4] == b"RIFF":
            result["valid"] = True
            result["format"] = "wav"
            return result

        # OGG
        if header[:4] == b"OggS":
            result["valid"] = True
            result["format"] = "ogg"
            return result

        # FLAC
        if header[:4] == b"fLaC":
            result["valid"] = True
            result["format"] = "flac"
            return result

        # Check if it looks like HTML or JSON (common error responses)
        try:
            text_start = header[:4].decode("ascii", errors="ignore")
            if text_start.startswith(("<", "{", "[")):
                result["errors"].append(
                    f"File appears to be text/markup, not audio (starts with {text_start!r})"
                )
                return result
        except Exception:
            pass

        result["errors"].append(
            f"Unrecognized audio header: {header[:4].hex()}"
        )
        return result

    @staticmethod
    def get_remote_file_size(url: str) -> int | None:
        """Get file size from a URL via HTTP HEAD request.

        Args:
            url: The URL to check.

        Returns:
            File size in bytes, or None on any error.
        """
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=10) as resp:
                cl = resp.headers.get("Content-Length")
                if cl:
                    return int(cl)
        except Exception:
            pass
        return None

    def save_from_url(self, url: str, song_title: str, version: int,
                      expected_size: int | None = None) -> Path:
        """Download audio directly from a URL (S3/CloudFront) without browser.

        Uses atomic write: urlretrieve streams to a temp file first, then
        the temp file is renamed to the target path.

        Args:
            url: Direct audio file URL.
            song_title: The song title (used for directory/filename).
            version: Version number (1 or 2).
            expected_size: Optional expected file size in bytes. If given
                and the actual size differs by more than 5%, raises
                DownloadVerificationError.

        Returns:
            Path to the saved file.

        Raises:
            urllib.error.URLError: If the download fails.
            DownloadVerificationError: If the file fails audio validation.
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
            atomic_write_fn(
                str(target_path),
                lambda tmp: urllib.request.urlretrieve(url, tmp),
            )
            file_size = target_path.stat().st_size
            self.last_download_size = file_size
            logger.info(f"  Downloaded {file_size:,} bytes")
        except urllib.error.URLError as e:
            logger.error(f"  Download failed: {e}")
            raise

        # Validate the downloaded file
        validation = self.validate_audio_file(target_path)
        if not validation["valid"]:
            errors = "; ".join(validation["errors"])
            logger.error(f"  Audio validation failed: {errors}")
            try:
                target_path.unlink()
            except OSError:
                pass
            raise DownloadVerificationError(
                f"Invalid audio file: {errors}",
                actual_size=validation["size"],
                expected_size=expected_size or 0,
            )

        # Check expected size (allow 5% tolerance)
        if expected_size and expected_size > 0:
            diff_pct = abs(file_size - expected_size) / expected_size
            if diff_pct > 0.05:
                logger.error(
                    f"  Size mismatch: expected {expected_size:,}, "
                    f"got {file_size:,} ({diff_pct:.1%} difference)"
                )
                try:
                    target_path.unlink()
                except OSError:
                    pass
                raise DownloadVerificationError(
                    f"File size mismatch: expected {expected_size}, got {file_size}",
                    actual_size=file_size,
                    expected_size=expected_size,
                )

        return target_path

    def save_playwright_download_track(self, download, song_title: str, track_type: str) -> Path:
        """Save a Playwright download object with a track-type suffix.

        Uses atomic write: Playwright saves to a temp file first, then the
        temp file is renamed to the target path.

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
        atomic_write_fn(str(target_path), lambda tmp: download.save_as(tmp))

        file_size = target_path.stat().st_size
        self.last_download_size = file_size

        validation = self.validate_audio_file(target_path)
        if not validation["valid"]:
            errors = "; ".join(validation["errors"])
            logger.error(f"  Playwright track download validation failed: {errors}")
            try:
                target_path.unlink()
            except OSError:
                pass
            raise DownloadVerificationError(
                f"Invalid audio file from browser track download: {errors}",
                actual_size=validation["size"],
            )

        return target_path

    def save_from_url_track(self, url: str, song_title: str, track_type: str) -> Path:
        """Download audio from a URL and save with a track-type suffix.

        Uses atomic write: urlretrieve streams to a temp file first, then
        the temp file is renamed to the target path.

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
            atomic_write_fn(
                str(target_path),
                lambda tmp: urllib.request.urlretrieve(url, tmp),
            )
            file_size = target_path.stat().st_size
            self.last_download_size = file_size
            logger.info(f"  Downloaded {file_size:,} bytes")
        except urllib.error.URLError as e:
            logger.error(f"  Download failed: {e}")
            raise

        # Validate the downloaded file
        validation = self.validate_audio_file(target_path)
        if not validation["valid"]:
            errors = "; ".join(validation["errors"])
            logger.error(f"  Track audio validation failed: {errors}")
            try:
                target_path.unlink()
            except OSError:
                pass
            raise DownloadVerificationError(
                f"Invalid audio track file: {errors}",
                actual_size=validation["size"],
            )

        return target_path

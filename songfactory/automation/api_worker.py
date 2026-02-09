"""MusicGPT direct API worker for Song Factory — browserless song processing.

Submits songs via HTTP POST, polls for completion, downloads via direct URLs.
Drop-in replacement for LalalsWorker when using API mode (no browser needed).
"""

import json
import time
import logging
import urllib.request
import urllib.error
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger("songfactory.automation")

# Set up file logging (same as browser_worker)
LOG_DIR = Path.home() / ".songfactory"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "automation.log"

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

# MusicGPT API base
API_BASE = "https://api.musicgpt.com/api/public/v1"


class MusicGptApiError(Exception):
    """Raised when a MusicGPT API call fails."""
    pass


def extract_metadata(api_response: dict) -> dict:
    """Parse a MusicGPT API response into a flat dict for DB storage.

    Standalone copy of LalalsDriver.extract_metadata() to avoid importing
    playwright. Handles documented response shapes:
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

    # Conversion IDs
    cid1 = data.get("conversion_id_1") or data.get("conversion_id")
    cid2 = data.get("conversion_id_2")
    if cid1:
        metadata["conversion_id_1"] = str(cid1)
    if cid2:
        metadata["conversion_id_2"] = str(cid2)

    # Audio URLs — numbered fields from byId COMPLETED response
    # The API returns conversion_path_1, conversion_path_2, etc.
    url_1 = (
        data.get("conversion_path_1")
        or data.get("audio_url_1")
        or data.get("audio_url")
        or data.get("conversion_path")
        or data.get("conversionPath")
        or data.get("track_url")
        or data.get("download_url")
        or data.get("url")
    )
    # Filter out incomplete S3 base URLs (no actual file path)
    if url_1 and url_1.rstrip("/") != "https://lalals.s3.amazonaws.com":
        metadata["audio_url_1"] = url_1

    url_2 = (
        data.get("conversion_path_2")
        or data.get("audio_url_2")
        or data.get("conversion_path_wav")
        or data.get("download_url_2")
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
        or data.get("conversion_duration_1")
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


def fetch_by_task_id(api_key: str, task_id: str) -> dict:
    """Fetch song metadata and download URLs from the MusicGPT byId API.

    Standalone function for recovering songs after the fact.  Given a
    task_id, calls the byId endpoint and returns parsed metadata including
    audio_url_1/audio_url_2 for downloading.

    Args:
        api_key: MusicGPT API key.
        task_id: The task UUID to look up.

    Returns:
        Parsed metadata dict with keys like task_id, status, audio_url_1,
        audio_url_2, conversion_id_1, etc.

    Raises:
        MusicGptApiError: On HTTP errors, invalid key, or network failure.
    """
    url = (
        f"{API_BASE}/byId"
        f"?conversionType=MUSIC_AI&task_id={task_id}"
    )
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )

    logger.info(f"fetch_by_task_id: GET {url}")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise MusicGptApiError(f"Invalid API key (HTTP {e.code})")
        raise MusicGptApiError(f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise MusicGptApiError(f"Network error: {e.reason}")

    # Extract status
    status = ""
    if isinstance(data, dict):
        status = data.get("status", "")
        if not status and isinstance(data.get("conversion"), dict):
            status = data["conversion"].get("status", "")
        elif not status and isinstance(data.get("data"), dict):
            status = data["data"].get("status", "")

    metadata = extract_metadata(data)
    metadata["api_status"] = status.upper() if status else ""

    logger.info(
        f"fetch_by_task_id: status={metadata.get('api_status')}, "
        f"url_1={'yes' if metadata.get('audio_url_1') else 'no'}, "
        f"url_2={'yes' if metadata.get('audio_url_2') else 'no'}"
    )
    return metadata


class MusicGptApiWorker(QThread):
    """Background worker that processes the song queue via MusicGPT HTTP API.

    Signal-compatible with LalalsWorker so the Library tab can use either
    worker interchangeably.
    """

    # Signals — identical to LalalsWorker (minus login_required, awaiting_refresh)
    song_started = pyqtSignal(int, str)         # song_id, song_title
    song_completed = pyqtSignal(int, str, str)  # song_id, file_path_1, file_path_2
    song_error = pyqtSignal(int, str)           # song_id, error_message
    progress_update = pyqtSignal(str)           # status message
    queue_finished = pyqtSignal()               # all done

    def __init__(self, db_path: str, config: dict, song_ids: list = None):
        """
        Args:
            db_path: Path to SQLite database.
            config: Dict with keys:
                - musicgpt_api_key: str (required)
                - download_dir: str (default ~/Music/SongFactory/)
                - delay_between_songs: int seconds (default 30)
                - max_songs_per_session: int (default 20)
                - poll_interval: int seconds (default 10)
                - poll_timeout: int seconds (default 600)
                - dry_run: bool (default False)
            song_ids: Optional list of specific song IDs to process.
                      If None, processes all songs with status='queued'.
        """
        super().__init__()
        self.db_path = db_path
        self.config = config
        self.song_ids = song_ids
        self._stop_flag = False

    def stop(self):
        """Signal graceful stop after current song finishes."""
        self._stop_flag = True
        logger.info("API worker: stop requested")

    def run(self):
        """Main loop: for each queued song, submit → poll → download."""
        import sqlite3
        from automation.download_manager import DownloadManager

        api_key = self.config.get("musicgpt_api_key", "")
        if not api_key:
            self.progress_update.emit("No MusicGPT API key configured")
            self.queue_finished.emit()
            return

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        download_dir = self.config.get(
            "download_dir", str(Path.home() / "Music" / "SongFactory")
        )
        dm = DownloadManager(download_dir)
        dry_run = self.config.get("dry_run", False)
        delay = self.config.get("delay_between_songs", 30)
        max_songs = self.config.get("max_songs_per_session", 20)
        poll_interval = self.config.get("poll_interval", 10)
        poll_timeout = self.config.get("poll_timeout", 600)

        # Fetch queued songs
        if self.song_ids:
            placeholders = ",".join("?" for _ in self.song_ids)
            cursor = conn.execute(
                f"SELECT * FROM songs WHERE id IN ({placeholders}) ORDER BY id",
                self.song_ids,
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
        self.progress_update.emit(f"Starting API queue: {total} song(s) to process")
        logger.info(f"API queue started: {total} songs, dry_run={dry_run}")

        if dry_run:
            self._run_dry(songs[:total], conn, dm)
            conn.close()
            return

        for i, song in enumerate(songs[:total]):
            if self._stop_flag:
                self.progress_update.emit("Stopped by user")
                logger.info("API queue stopped by user")
                break

            song_id = song["id"]
            title = song["title"]
            prompt = song["prompt"]
            lyrics = song["lyrics"]

            self.song_started.emit(song_id, title)
            self.progress_update.emit(
                f"Submitting '{title}' via API ({i + 1}/{total})"
            )
            logger.info(f"API submitting song {song_id}: {title}")

            # Mark as processing
            conn.execute(
                "UPDATE songs SET status='processing' WHERE id=?", (song_id,)
            )
            conn.commit()

            try:
                # ---- SUBMIT ----
                task_id, response_data = self._submit_song(api_key, prompt, lyrics)

                # Store task_id, set status to "submitted"
                set_parts = ["status='submitted'"]
                vals = []
                if task_id:
                    set_parts.append("task_id=?")
                    vals.append(task_id)
                cid1 = response_data.get("conversion_id_1", "")
                cid2 = response_data.get("conversion_id_2", "")
                if cid1:
                    set_parts.append("conversion_id_1=?")
                    vals.append(cid1)
                if cid2:
                    set_parts.append("conversion_id_2=?")
                    vals.append(cid2)
                vals.append(song_id)
                conn.execute(
                    f"UPDATE songs SET {', '.join(set_parts)} WHERE id=?", vals
                )
                conn.commit()

                if not task_id:
                    raise MusicGptApiError(
                        "No task_id returned from submit — API may have changed"
                    )

                # ---- POLL until complete ----
                self.progress_update.emit(
                    f"'{title}' submitted — polling for completion..."
                )
                metadata = self._poll_until_complete(
                    api_key, task_id, poll_interval, poll_timeout
                )

                # ---- DOWNLOAD ----
                self.progress_update.emit(f"Downloading '{title}'...")
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
                            logger.info(f"API downloaded v{version}: {path}")
                        except Exception as e:
                            logger.warning(f"API download v{version} failed: {e}")

                # If primary download failed, try S3 fallback
                if not file_path_1:
                    S3_BASE = "https://lalals.s3.amazonaws.com/conversions/standard"
                    fallback_cid = metadata.get("conversion_id_1") or cid1
                    if fallback_cid:
                        fallback_url = f"{S3_BASE}/{fallback_cid}/{fallback_cid}.mp3"
                        try:
                            path = dm.save_from_url(fallback_url, title, 1)
                            file_path_1 = str(path)
                            logger.info(f"API S3 fallback download: {path}")
                        except Exception as e:
                            logger.warning(f"API S3 fallback failed: {e}")

                # ---- UPDATE DB ----
                update_kwargs = {
                    "status": "completed" if file_path_1 else "error",
                    "file_path_1": file_path_1,
                    "file_path_2": file_path_2,
                }
                metadata_cols = {
                    "task_id", "conversion_id_1", "conversion_id_2",
                    "audio_url_1", "audio_url_2", "music_style",
                    "duration_seconds", "file_format", "file_size_1",
                    "file_size_2", "voice_used", "lalals_created_at",
                    "lyrics_timestamped",
                }
                for key in metadata_cols:
                    if key in metadata:
                        update_kwargs[key] = metadata[key]

                set_parts = []
                values = []
                for k, v in update_kwargs.items():
                    set_parts.append(f"{k}=?")
                    values.append(v)
                set_parts.append("updated_at=CURRENT_TIMESTAMP")
                values.append(song_id)

                conn.execute(
                    f"UPDATE songs SET {', '.join(set_parts)} WHERE id=?", values
                )
                conn.commit()

                if file_path_1:
                    self.song_completed.emit(song_id, file_path_1, file_path_2)
                    logger.info(f"API completed: {title}")
                else:
                    notes = "No download files captured from API"
                    conn.execute(
                        "UPDATE songs SET notes=? WHERE id=?", (notes, song_id)
                    )
                    conn.commit()
                    self.song_error.emit(song_id, notes)
                    logger.warning(f"API no files for: {title}")

            except MusicGptApiError as e:
                error_msg = str(e)
                logger.error(f"API error for {title}: {error_msg}")
                conn.execute(
                    "UPDATE songs SET status='error', notes=? WHERE id=?",
                    (error_msg, song_id),
                )
                conn.commit()
                self.song_error.emit(song_id, error_msg)

            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                logger.error(f"API error for {title}: {error_msg}")
                conn.execute(
                    "UPDATE songs SET status='error', notes=? WHERE id=?",
                    (error_msg, song_id),
                )
                conn.commit()
                self.song_error.emit(song_id, error_msg)

            # Delay between songs
            if i < total - 1 and not self._stop_flag:
                self.progress_update.emit(
                    f"Waiting {delay}s before next song..."
                )
                for _ in range(delay):
                    if self._stop_flag:
                        break
                    time.sleep(1)

        self.progress_update.emit("API queue processing complete")
        conn.close()
        self.queue_finished.emit()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _submit_song(self, api_key: str, prompt: str, lyrics: str) -> tuple:
        """Submit a song via POST to MusicGPT API.

        Args:
            api_key: MusicGPT API key.
            prompt: Song description prompt.
            lyrics: Song lyrics text.

        Returns:
            Tuple of (task_id, response_data_dict).

        Raises:
            MusicGptApiError: On HTTP or parse errors.
        """
        url = f"{API_BASE}/MusicAI"
        payload = {
            "prompt": prompt,
            "lyrics": lyrics,
        }
        body = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        logger.info(f"API POST {url} (prompt: {len(prompt)} chars, lyrics: {len(lyrics)} chars)")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            status = e.code
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                err_msg = err_body.get("error") or err_body.get("message") or str(err_body)
            except Exception:
                err_msg = e.reason
            if status in (401, 403):
                raise MusicGptApiError(f"Invalid API key (HTTP {status}): {err_msg}")
            elif status == 429:
                raise MusicGptApiError(f"Rate limited (HTTP 429): {err_msg}")
            else:
                raise MusicGptApiError(f"HTTP {status}: {err_msg}")
        except urllib.error.URLError as e:
            raise MusicGptApiError(f"Network error: {e.reason}")

        # Parse response
        src = data
        if isinstance(data.get("data"), dict):
            src = data["data"]

        task_id = str(src.get("task_id") or src.get("taskId") or "")
        response_data = {
            "task_id": task_id,
            "conversion_id_1": str(src.get("conversion_id_1", "")),
            "conversion_id_2": str(src.get("conversion_id_2", "")),
            "eta": src.get("eta"),
            "response": data,
        }

        logger.info(
            f"API submit response: task_id={task_id}, "
            f"cid1={response_data['conversion_id_1']}, "
            f"cid2={response_data['conversion_id_2']}"
        )
        return task_id, response_data

    def _poll_until_complete(
        self, api_key: str, task_id: str, interval: int, timeout: int
    ) -> dict:
        """Poll the byId endpoint until the task reaches COMPLETED/ERROR/FAILED.

        Args:
            api_key: MusicGPT API key.
            task_id: The task UUID to poll.
            interval: Seconds between polls.
            timeout: Max seconds to poll before giving up.

        Returns:
            Parsed metadata dict from extract_metadata().

        Raises:
            MusicGptApiError: On error status, timeout, or network failure.
        """
        url = (
            f"{API_BASE}/byId"
            f"?conversionType=MUSIC_AI&task_id={task_id}"
        )
        start = time.time()
        retries_left = 3  # for transient network errors
        last_status = ""

        logger.info(f"API polling {url} (interval={interval}s, timeout={timeout}s)")

        while time.time() - start < timeout:
            if self._stop_flag:
                raise MusicGptApiError("Polling cancelled by user")

            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                method="GET",
            )

            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                retries_left = 3  # reset on success
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise MusicGptApiError(f"Invalid API key during poll (HTTP {e.code})")
                elif e.code == 429:
                    # Rate limit — exponential backoff
                    wait = interval * (4 - retries_left)
                    logger.warning(f"Rate limited during poll, waiting {wait}s")
                    self.progress_update.emit(f"Rate limited — waiting {wait}s...")
                    for _ in range(wait):
                        if self._stop_flag:
                            raise MusicGptApiError("Polling cancelled by user")
                        time.sleep(1)
                    retries_left -= 1
                    if retries_left <= 0:
                        raise MusicGptApiError("Rate limited too many times")
                    continue
                else:
                    retries_left -= 1
                    if retries_left <= 0:
                        raise MusicGptApiError(f"Poll HTTP error: {e.code} {e.reason}")
                    logger.warning(f"Poll HTTP {e.code}, retrying ({retries_left} left)")
                    time.sleep(interval)
                    continue
            except urllib.error.URLError as e:
                retries_left -= 1
                if retries_left <= 0:
                    raise MusicGptApiError(f"Poll network error: {e.reason}")
                logger.warning(f"Poll network error, retrying ({retries_left} left)")
                time.sleep(interval)
                continue

            status = self._get_status(data)

            if status and status != last_status:
                elapsed = int(time.time() - start)
                self.progress_update.emit(
                    f"Status: {status} ({elapsed}s elapsed)"
                )
                logger.info(f"API poll status: {status} ({elapsed}s)")
                last_status = status

            if status == "COMPLETED":
                logger.info(f"API COMPLETED raw response: {json.dumps(data, indent=2, default=str)[:3000]}")
                return extract_metadata(data)
            elif status in ("ERROR", "FAILED"):
                # Try to extract error message
                err = data
                if isinstance(data.get("conversion"), dict):
                    err = data["conversion"]
                elif isinstance(data.get("data"), dict):
                    err = data["data"]
                msg = err.get("error") or err.get("message") or f"Generation {status}"
                raise MusicGptApiError(msg)

            # Sleep with interruptibility
            for _ in range(interval):
                if self._stop_flag:
                    raise MusicGptApiError("Polling cancelled by user")
                time.sleep(1)

        raise MusicGptApiError(
            f"Poll timeout — task {task_id} did not complete within {timeout}s"
        )

    @staticmethod
    def _get_status(data: dict) -> str:
        """Extract the status string from various response shapes.

        Handles:
        - {status: "COMPLETED"}
        - {conversion: {status: "COMPLETED"}}
        - {data: {status: "COMPLETED"}}
        """
        if isinstance(data, dict):
            status = data.get("status")
            if status and isinstance(status, str):
                return status.upper()
            if isinstance(data.get("conversion"), dict):
                s = data["conversion"].get("status")
                if s:
                    return str(s).upper()
            if isinstance(data.get("data"), dict):
                s = data["data"].get("status")
                if s:
                    return str(s).upper()
        return ""

    # ------------------------------------------------------------------
    # Dry run
    # ------------------------------------------------------------------

    def _run_dry(self, songs: list, conn, dm) -> None:
        """Dry run mode — simulate API processing without HTTP calls."""
        total = len(songs)
        for i, song in enumerate(songs):
            if self._stop_flag:
                self.progress_update.emit("Stopped by user")
                break

            song_id = song["id"]
            title = song["title"]
            self.song_started.emit(song_id, title)
            self.progress_update.emit(
                f"[DRY RUN / API] Processing '{title}' ({i + 1}/{total})"
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
            p1.write_text("[dry run placeholder — API mode]")
            p2.write_text("[dry run placeholder — API mode]")

            conn.execute(
                "UPDATE songs SET status='completed', "
                "file_path_1=?, file_path_2=? WHERE id=?",
                (str(p1), str(p2), song_id),
            )
            conn.commit()

            self.song_completed.emit(song_id, str(p1), str(p2))
            logger.info(f"[DRY RUN / API] Completed: {title}")

        self.progress_update.emit("[DRY RUN / API] Queue complete")
        self.queue_finished.emit()

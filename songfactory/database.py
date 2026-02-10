"""
Song Factory - SQLite Database Module

Provides a Database class that manages all persistence for the Song Factory
PyQt6 application, including lore entries, genre definitions, songs, and
application configuration.

Database location: ~/.songfactory/songfactory.db
"""

import glob as _glob
import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Optional


DB_DIR = Path.home() / ".songfactory"
DB_PATH = DB_DIR / "songfactory.db"

# ---------------------------------------------------------------------------
# SQL: Table creation
# ---------------------------------------------------------------------------

_CREATE_LORE = """
CREATE TABLE IF NOT EXISTS lore (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    category   TEXT DEFAULT 'general',
    active     BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_GENRES = """
CREATE TABLE IF NOT EXISTS genres (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    prompt_template TEXT NOT NULL,
    description     TEXT,
    bpm_range       TEXT,
    active          BOOLEAN DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_SONGS = """
CREATE TABLE IF NOT EXISTS songs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    genre_id      INTEGER REFERENCES genres(id),
    genre_label   TEXT,
    prompt        TEXT NOT NULL,
    lyrics        TEXT NOT NULL,
    user_input    TEXT,
    lore_snapshot TEXT,
    status        TEXT DEFAULT 'draft',
    file_path_1   TEXT,
    file_path_2   TEXT,
    notes         TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_CONFIG = """
CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

_CREATE_CD_PROJECTS = """
CREATE TABLE IF NOT EXISTS cd_projects (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    artist           TEXT DEFAULT 'Yakima Finds',
    album_title      TEXT DEFAULT '',
    songwriter       TEXT DEFAULT '',
    message          TEXT DEFAULT '',
    total_duration   REAL DEFAULT 0,
    status           TEXT DEFAULT 'draft',
    include_data     BOOLEAN DEFAULT 1,
    include_source   BOOLEAN DEFAULT 1,
    include_lyrics   BOOLEAN DEFAULT 1,
    include_mp3      BOOLEAN DEFAULT 1,
    disc_art_path    TEXT,
    cover_art_path   TEXT,
    back_art_path    TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_LORE_PRESETS = """
CREATE TABLE IF NOT EXISTS lore_presets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    lore_ids   TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_CD_TRACKS = """
CREATE TABLE IF NOT EXISTS cd_tracks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id       INTEGER NOT NULL REFERENCES cd_projects(id) ON DELETE CASCADE,
    song_id          INTEGER REFERENCES songs(id),
    track_number     INTEGER NOT NULL,
    title            TEXT NOT NULL,
    performer        TEXT DEFAULT 'Yakima Finds',
    songwriter       TEXT DEFAULT '',
    source_path      TEXT NOT NULL,
    wav_path         TEXT,
    duration_seconds REAL DEFAULT 0,
    pregap_seconds   REAL DEFAULT 2.0,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_DISTRIBUTIONS = """
CREATE TABLE IF NOT EXISTS distributions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id           INTEGER NOT NULL REFERENCES songs(id),
    distributor       TEXT NOT NULL DEFAULT 'distrokid',
    release_type      TEXT DEFAULT 'single',
    artist_name       TEXT DEFAULT 'Yakima Finds',
    album_title       TEXT,
    songwriter        TEXT NOT NULL,
    language          TEXT DEFAULT 'English',
    primary_genre     TEXT,
    cover_art_path    TEXT,
    is_instrumental   BOOLEAN DEFAULT 0,
    lyrics_submitted  TEXT,
    release_date      TEXT,
    record_label      TEXT,
    ai_disclosure     BOOLEAN DEFAULT 1,
    distrokid_url     TEXT,
    status            TEXT DEFAULT 'draft',
    error_message     TEXT,
    notes             TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    """SQLite database interface for the Song Factory application."""

    def __init__(self) -> None:
        """Initialise the database: create the storage directory, open a
        connection, and ensure all tables exist."""
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self._db_path = str(DB_PATH)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._create_tables()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        """Create all tables if they do not already exist."""
        with self._cursor() as cur:
            cur.execute(_CREATE_LORE)
            cur.execute(_CREATE_GENRES)
            cur.execute(_CREATE_SONGS)
            cur.execute(_CREATE_CONFIG)
            cur.execute(_CREATE_LORE_PRESETS)
            cur.execute(_CREATE_CD_PROJECTS)
            cur.execute(_CREATE_CD_TRACKS)
            cur.execute(_CREATE_DISTRIBUTIONS)
        self._migrate_songs_table()

    def _migrate_songs_table(self) -> None:
        """Add metadata columns to the songs table if they don't exist yet.

        Uses PRAGMA table_info to check which columns are present, then
        ALTER TABLE ADD COLUMN for each missing one.  Safe to call repeatedly.
        """
        new_columns = {
            "task_id":            "TEXT",
            "conversion_id_1":    "TEXT",
            "conversion_id_2":    "TEXT",
            "audio_url_1":        "TEXT",
            "audio_url_2":        "TEXT",
            "music_style":        "TEXT",
            "duration_seconds":   "REAL",
            "file_format":        "TEXT",
            "file_size_1":        "INTEGER",
            "file_size_2":        "INTEGER",
            "voice_used":         "TEXT",
            "lalals_created_at":  "TEXT",
            "lyrics_timestamped": "TEXT",
            "file_path_vocals":       "TEXT",
            "file_path_instrumental": "TEXT",
        }

        with self._cursor() as cur:
            cur.execute("PRAGMA table_info(songs);")
            existing = {row["name"] for row in cur.fetchall()}

            for col_name, col_type in new_columns.items():
                if col_name not in existing:
                    cur.execute(
                        f"ALTER TABLE songs ADD COLUMN {col_name} {col_type};"
                    )

    @contextmanager
    def _cursor(self):
        """Yield a cursor inside a transaction.  Commits on success,
        rolls back on failure."""
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except sqlite3.Error:
            self._conn.rollback()
            raise
        finally:
            cur.close()

    @staticmethod
    def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
        """Convert a sqlite3.Row to a plain dict, or return None."""
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
        """Convert a list of sqlite3.Row objects to a list of dicts."""
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Backup & Restore
    # ------------------------------------------------------------------

    def backup_to(self, directory: str) -> str:
        """Create a timestamped backup of the live database.

        Uses the SQLite ``conn.backup()`` API so it is safe to call while
        the database is open and being written to.

        Returns the full path to the created backup file.
        """
        os.makedirs(directory, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"songfactory_backup_{timestamp}.db"
        dest_path = os.path.join(directory, filename)

        dest_conn = sqlite3.connect(dest_path)
        try:
            self._conn.backup(dest_conn)
        finally:
            dest_conn.close()

        return dest_path

    def restore_from(self, backup_path: str) -> None:
        """Replace the current database with the contents of *backup_path*.

        Before overwriting, creates a safety copy of the current database
        as ``songfactory_pre_restore.db`` in the database directory.
        After copying, removes any leftover WAL/SHM files, reopens the
        connection, and runs table creation / migration.
        """
        if not os.path.isfile(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        # Close current connection
        if self._conn:
            self._conn.close()
            self._conn = None

        # Safety copy of current database
        safety_path = os.path.join(str(DB_DIR), "songfactory_pre_restore.db")
        if os.path.isfile(self._db_path):
            shutil.copy2(self._db_path, safety_path)

        # Overwrite with backup
        shutil.copy2(backup_path, self._db_path)

        # Remove stale WAL/SHM files (they belong to the old database)
        for suffix in ("-wal", "-shm"):
            wal_path = self._db_path + suffix
            if os.path.exists(wal_path):
                os.remove(wal_path)

        # Reopen and ensure schema is up to date
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._create_tables()

    @staticmethod
    def detect_backups(directory: str) -> list[dict]:
        """Scan *directory* for Song Factory backup files.

        Returns a list of dicts sorted newest-first, each containing:
        ``path``, ``filename``, ``date`` (human-readable), ``size`` (bytes).
        """
        if not os.path.isdir(directory):
            return []

        pattern = os.path.join(directory, "songfactory_backup_*.db")
        matches = _glob.glob(pattern)

        results: list[dict] = []
        for path in matches:
            filename = os.path.basename(path)
            # Extract date from filename: songfactory_backup_YYYYMMDD_HHMMSS.db
            try:
                parts = filename.replace("songfactory_backup_", "").replace(".db", "")
                dt = datetime.strptime(parts, "%Y%m%d_%H%M%S")
                date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                date_str = "Unknown"
            results.append({
                "path": path,
                "filename": filename,
                "date": date_str,
                "size": os.path.getsize(path),
            })

        results.sort(key=lambda r: r["filename"], reverse=True)
        return results

    # ==================================================================
    # LORE
    # ==================================================================

    def get_all_lore(self) -> list[dict]:
        """Return every lore entry, ordered by most-recently created."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM lore ORDER BY created_at DESC;")
            return self._rows_to_dicts(cur.fetchall())

    def get_active_lore(self) -> list[dict]:
        """Return only lore entries where active = 1."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM lore WHERE active = 1 ORDER BY created_at DESC;"
            )
            return self._rows_to_dicts(cur.fetchall())

    def get_lore(self, lore_id: int) -> Optional[dict]:
        """Return a single lore entry by id, or None."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM lore WHERE id = ?;", (lore_id,))
            return self._row_to_dict(cur.fetchone())

    def add_lore(
        self,
        title: str,
        content: str,
        category: str = "general",
        active: bool = True,
    ) -> int:
        """Insert a new lore entry and return its id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO lore (title, content, category, active)
                VALUES (?, ?, ?, ?);
                """,
                (title, content, category, int(active)),
            )
            return cur.lastrowid

    def update_lore(self, lore_id: int, **kwargs: Any) -> bool:
        """Update one or more columns of a lore entry.

        Accepted keyword arguments correspond to column names (title,
        content, category, active).  Returns True if a row was updated.
        """
        if not kwargs:
            return False
        allowed = {"title", "content", "category", "active"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False

        # Always bump updated_at when the row changes.
        set_clause = ", ".join(f"{col} = ?" for col in fields)
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        values = list(fields.values()) + [lore_id]

        with self._cursor() as cur:
            cur.execute(
                f"UPDATE lore SET {set_clause} WHERE id = ?;",
                values,
            )
            return cur.rowcount > 0

    def delete_lore(self, lore_id: int) -> bool:
        """Delete a lore entry by id.  Returns True if a row was deleted."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM lore WHERE id = ?;", (lore_id,))
            return cur.rowcount > 0

    def toggle_lore_active(self, lore_id: int) -> bool:
        """Flip the active flag on a lore entry.  Returns True if updated."""
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE lore
                SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (lore_id,),
            )
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Lore bulk toggles
    # ------------------------------------------------------------------

    def set_all_lore_active(self, active: bool) -> None:
        """Set the active flag on every lore entry."""
        with self._cursor() as cur:
            cur.execute(
                "UPDATE lore SET active = ?, updated_at = CURRENT_TIMESTAMP;",
                (int(active),),
            )

    def set_category_lore_active(self, category: str, active: bool) -> None:
        """Set the active flag on all lore entries in *category*."""
        with self._cursor() as cur:
            cur.execute(
                "UPDATE lore SET active = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE category = ?;",
                (int(active), category),
            )

    def set_lore_active_bulk(self, lore_ids: list[int], active: bool) -> None:
        """Set the active flag on the lore entries whose ids are in *lore_ids*."""
        if not lore_ids:
            return
        placeholders = ", ".join("?" for _ in lore_ids)
        with self._cursor() as cur:
            cur.execute(
                f"UPDATE lore SET active = ?, updated_at = CURRENT_TIMESTAMP "
                f"WHERE id IN ({placeholders});",
                [int(active)] + list(lore_ids),
            )

    # ------------------------------------------------------------------
    # Lore presets
    # ------------------------------------------------------------------

    def get_all_lore_presets(self) -> list[dict]:
        """Return every lore preset, ordered by name."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM lore_presets ORDER BY name ASC;")
            rows = self._rows_to_dicts(cur.fetchall())
            for row in rows:
                row["lore_ids"] = json.loads(row["lore_ids"])
            return rows

    def add_lore_preset(self, name: str, lore_ids: list[int]) -> int:
        """Insert a new lore preset and return its id."""
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO lore_presets (name, lore_ids) VALUES (?, ?);",
                (name, json.dumps(lore_ids)),
            )
            return cur.lastrowid

    def update_lore_preset(self, preset_id: int, **kwargs: Any) -> bool:
        """Update a lore preset.  Allowed keys: name, lore_ids."""
        if not kwargs:
            return False
        allowed = {"name", "lore_ids"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        if "lore_ids" in fields:
            fields["lore_ids"] = json.dumps(fields["lore_ids"])
        set_clause = ", ".join(f"{col} = ?" for col in fields)
        values = list(fields.values()) + [preset_id]
        with self._cursor() as cur:
            cur.execute(
                f"UPDATE lore_presets SET {set_clause} WHERE id = ?;",
                values,
            )
            return cur.rowcount > 0

    def delete_lore_preset(self, preset_id: int) -> bool:
        """Delete a lore preset.  Returns True if a row was deleted."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM lore_presets WHERE id = ?;", (preset_id,))
            return cur.rowcount > 0

    def apply_lore_preset(self, preset_id: int) -> None:
        """Deactivate all lore, then activate only the IDs in *preset_id*."""
        preset = None
        with self._cursor() as cur:
            cur.execute(
                "SELECT lore_ids FROM lore_presets WHERE id = ?;", (preset_id,),
            )
            row = cur.fetchone()
            if row is None:
                return
            preset = json.loads(row["lore_ids"])

        self.set_all_lore_active(False)
        if preset:
            self.set_lore_active_bulk(preset, True)

    # ==================================================================
    # GENRES
    # ==================================================================

    def get_all_genres(self) -> list[dict]:
        """Return every genre, ordered by name."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM genres ORDER BY name ASC;")
            return self._rows_to_dicts(cur.fetchall())

    def get_active_genres(self) -> list[dict]:
        """Return only genres where active = 1."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM genres WHERE active = 1 ORDER BY name ASC;"
            )
            return self._rows_to_dicts(cur.fetchall())

    def get_genre(self, genre_id: int) -> Optional[dict]:
        """Return a single genre by id, or None."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM genres WHERE id = ?;", (genre_id,))
            return self._row_to_dict(cur.fetchone())

    def add_genre(
        self,
        name: str,
        prompt_template: str,
        description: str = None,
        bpm_range: str = None,
        active: bool = True,
    ) -> int:
        """Insert a new genre and return its id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO genres (name, prompt_template, description,
                                    bpm_range, active)
                VALUES (?, ?, ?, ?, ?);
                """,
                (name, prompt_template, description, bpm_range, int(active)),
            )
            return cur.lastrowid

    def update_genre(self, genre_id: int, **kwargs: Any) -> bool:
        """Update one or more columns of a genre.

        Returns True if a row was updated.
        """
        if not kwargs:
            return False
        allowed = {"name", "prompt_template", "description", "bpm_range", "active"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False

        set_clause = ", ".join(f"{col} = ?" for col in fields)
        values = list(fields.values()) + [genre_id]

        with self._cursor() as cur:
            cur.execute(
                f"UPDATE genres SET {set_clause} WHERE id = ?;",
                values,
            )
            return cur.rowcount > 0

    def delete_genre(self, genre_id: int) -> bool:
        """Delete a genre by id.  Returns True if a row was deleted."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM genres WHERE id = ?;", (genre_id,))
            return cur.rowcount > 0

    def toggle_genre_active(self, genre_id: int) -> bool:
        """Flip the active flag on a genre.  Returns True if updated."""
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE genres
                SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END
                WHERE id = ?;
                """,
                (genre_id,),
            )
            return cur.rowcount > 0

    # ==================================================================
    # SONGS
    # ==================================================================

    def get_all_songs(self) -> list[dict]:
        """Return every song, most recent first."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM songs ORDER BY created_at DESC;")
            return self._rows_to_dicts(cur.fetchall())

    def get_songs_by_status(self, status: str) -> list[dict]:
        """Return songs filtered by status (e.g. 'draft', 'complete')."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM songs WHERE status = ? ORDER BY created_at DESC;",
                (status,),
            )
            return self._rows_to_dicts(cur.fetchall())

    def get_songs_by_genre(self, genre_id: int) -> list[dict]:
        """Return songs that belong to a given genre."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM songs WHERE genre_id = ? ORDER BY created_at DESC;",
                (genre_id,),
            )
            return self._rows_to_dicts(cur.fetchall())

    def search_songs(self, query: str) -> list[dict]:
        """Search songs by title, lyrics, prompt, or notes (case-insensitive)."""
        like = f"%{query}%"
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM songs
                WHERE title   LIKE ?
                   OR lyrics  LIKE ?
                   OR prompt  LIKE ?
                   OR notes   LIKE ?
                ORDER BY created_at DESC;
                """,
                (like, like, like, like),
            )
            return self._rows_to_dicts(cur.fetchall())

    def get_song(self, song_id: int) -> Optional[dict]:
        """Return a single song by id, or None."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM songs WHERE id = ?;", (song_id,))
            return self._row_to_dict(cur.fetchone())

    def add_song(
        self,
        title: str,
        genre_id: int,
        genre_label: str,
        prompt: str,
        lyrics: str,
        user_input: str = None,
        lore_snapshot: str = None,
        status: str = "draft",
    ) -> int:
        """Insert a new song and return its id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO songs (title, genre_id, genre_label, prompt,
                                   lyrics, user_input, lore_snapshot, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    title,
                    genre_id,
                    genre_label,
                    prompt,
                    lyrics,
                    user_input,
                    lore_snapshot,
                    status,
                ),
            )
            return cur.lastrowid

    def update_song(self, song_id: int, **kwargs: Any) -> bool:
        """Update one or more columns of a song.

        Returns True if a row was updated.
        """
        if not kwargs:
            return False
        allowed = {
            "title",
            "genre_id",
            "genre_label",
            "prompt",
            "lyrics",
            "user_input",
            "lore_snapshot",
            "status",
            "file_path_1",
            "file_path_2",
            "notes",
            "task_id",
            "conversion_id_1",
            "conversion_id_2",
            "audio_url_1",
            "audio_url_2",
            "music_style",
            "duration_seconds",
            "file_format",
            "file_size_1",
            "file_size_2",
            "voice_used",
            "lalals_created_at",
            "lyrics_timestamped",
            "file_path_vocals",
            "file_path_instrumental",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False

        set_clause = ", ".join(f"{col} = ?" for col in fields)
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        values = list(fields.values()) + [song_id]

        with self._cursor() as cur:
            cur.execute(
                f"UPDATE songs SET {set_clause} WHERE id = ?;",
                values,
            )
            return cur.rowcount > 0

    def delete_song(self, song_id: int) -> bool:
        """Delete a song by id.  Returns True if a row was deleted."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM songs WHERE id = ?;", (song_id,))
            return cur.rowcount > 0

    def get_song_count(self) -> int:
        """Return the total number of songs."""
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM songs;")
            row = cur.fetchone()
            return row["cnt"] if row else 0

    # ==================================================================
    # CONFIG
    # ==================================================================

    def get_config(self, key: str, default: Any = None) -> Optional[str]:
        """Retrieve a configuration value by key, or *default* if missing."""
        with self._cursor() as cur:
            cur.execute("SELECT value FROM config WHERE key = ?;", (key,))
            row = cur.fetchone()
            return row["value"] if row else default

    def set_config(self, key: str, value: str) -> None:
        """Insert or update a configuration key/value pair."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO config (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
                """,
                (key, value),
            )

    def get_all_config(self) -> dict[str, str]:
        """Return every configuration entry as a plain dict."""
        with self._cursor() as cur:
            cur.execute("SELECT key, value FROM config ORDER BY key;")
            return {row["key"]: row["value"] for row in cur.fetchall()}

    # ==================================================================
    # CD PROJECTS
    # ==================================================================

    def get_all_cd_projects(self) -> list[dict]:
        """Return every CD project, most recent first."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM cd_projects ORDER BY updated_at DESC;")
            return self._rows_to_dicts(cur.fetchall())

    def get_cd_project(self, project_id: int) -> Optional[dict]:
        """Return a single CD project by id, or None."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM cd_projects WHERE id = ?;", (project_id,))
            return self._row_to_dict(cur.fetchone())

    def add_cd_project(self, name: str, **kwargs: Any) -> int:
        """Insert a new CD project and return its id."""
        allowed = {
            "artist", "album_title", "songwriter", "message",
            "include_data", "include_source", "include_lyrics", "include_mp3",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        columns = ["name"] + list(fields.keys())
        placeholders = ", ".join("?" for _ in columns)
        col_str = ", ".join(columns)
        values = [name] + list(fields.values())

        with self._cursor() as cur:
            cur.execute(
                f"INSERT INTO cd_projects ({col_str}) VALUES ({placeholders});",
                values,
            )
            return cur.lastrowid

    def update_cd_project(self, project_id: int, **kwargs: Any) -> bool:
        """Update one or more columns of a CD project.  Returns True if updated."""
        if not kwargs:
            return False
        allowed = {
            "name", "artist", "album_title", "songwriter", "message",
            "total_duration", "status", "include_data", "include_source",
            "include_lyrics", "include_mp3", "disc_art_path",
            "cover_art_path", "back_art_path",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False

        set_clause = ", ".join(f"{col} = ?" for col in fields)
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        values = list(fields.values()) + [project_id]

        with self._cursor() as cur:
            cur.execute(
                f"UPDATE cd_projects SET {set_clause} WHERE id = ?;",
                values,
            )
            return cur.rowcount > 0

    def delete_cd_project(self, project_id: int) -> bool:
        """Delete a CD project and its tracks.  Returns True if deleted."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM cd_projects WHERE id = ?;", (project_id,))
            return cur.rowcount > 0

    # ==================================================================
    # CD TRACKS
    # ==================================================================

    def get_cd_tracks(self, project_id: int) -> list[dict]:
        """Return all tracks for a CD project, ordered by track_number."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM cd_tracks WHERE project_id = ? ORDER BY track_number;",
                (project_id,),
            )
            return self._rows_to_dicts(cur.fetchall())

    def add_cd_track(
        self,
        project_id: int,
        track_number: int,
        title: str,
        source_path: str,
        **kwargs: Any,
    ) -> int:
        """Insert a new CD track and return its id."""
        allowed = {
            "song_id", "performer", "songwriter", "wav_path",
            "duration_seconds", "pregap_seconds",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        columns = ["project_id", "track_number", "title", "source_path"] + list(fields.keys())
        placeholders = ", ".join("?" for _ in columns)
        col_str = ", ".join(columns)
        values = [project_id, track_number, title, source_path] + list(fields.values())

        with self._cursor() as cur:
            cur.execute(
                f"INSERT INTO cd_tracks ({col_str}) VALUES ({placeholders});",
                values,
            )
            return cur.lastrowid

    def update_cd_track(self, track_id: int, **kwargs: Any) -> bool:
        """Update one or more columns of a CD track.  Returns True if updated."""
        if not kwargs:
            return False
        allowed = {
            "track_number", "title", "performer", "songwriter",
            "source_path", "wav_path", "duration_seconds", "pregap_seconds",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False

        set_clause = ", ".join(f"{col} = ?" for col in fields)
        values = list(fields.values()) + [track_id]

        with self._cursor() as cur:
            cur.execute(
                f"UPDATE cd_tracks SET {set_clause} WHERE id = ?;",
                values,
            )
            return cur.rowcount > 0

    def delete_cd_track(self, track_id: int) -> bool:
        """Delete a CD track.  Returns True if deleted."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM cd_tracks WHERE id = ?;", (track_id,))
            return cur.rowcount > 0

    def reorder_cd_tracks(self, project_id: int, track_ids: list[int]) -> None:
        """Reorder tracks by assigning track_number 1..N in the given id order."""
        with self._cursor() as cur:
            for idx, tid in enumerate(track_ids, start=1):
                cur.execute(
                    "UPDATE cd_tracks SET track_number = ? WHERE id = ? AND project_id = ?;",
                    (idx, tid, project_id),
                )

    # ==================================================================
    # DISTRIBUTIONS
    # ==================================================================

    def get_all_distributions(self) -> list[dict]:
        """Return every distribution, most recent first."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM distributions ORDER BY created_at DESC;"
            )
            return self._rows_to_dicts(cur.fetchall())

    def get_distribution(self, dist_id: int) -> Optional[dict]:
        """Return a single distribution by id, or None."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM distributions WHERE id = ?;", (dist_id,)
            )
            return self._row_to_dict(cur.fetchone())

    def get_distributions_for_song(self, song_id: int) -> list[dict]:
        """Return all distributions for a given song."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM distributions WHERE song_id = ? "
                "ORDER BY created_at DESC;",
                (song_id,),
            )
            return self._rows_to_dicts(cur.fetchall())

    def get_distributions_by_status(self, status: str) -> list[dict]:
        """Return distributions filtered by status."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM distributions WHERE status = ? "
                "ORDER BY created_at DESC;",
                (status,),
            )
            return self._rows_to_dicts(cur.fetchall())

    def add_distribution(self, song_id: int, songwriter: str, **kwargs: Any) -> int:
        """Insert a new distribution and return its id."""
        allowed = {
            "distributor", "release_type", "artist_name", "album_title",
            "language", "primary_genre", "cover_art_path", "is_instrumental",
            "lyrics_submitted", "release_date", "record_label",
            "ai_disclosure", "distrokid_url", "status", "error_message",
            "notes",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        columns = ["song_id", "songwriter"] + list(fields.keys())
        placeholders = ", ".join("?" for _ in columns)
        col_str = ", ".join(columns)
        values = [song_id, songwriter] + list(fields.values())

        with self._cursor() as cur:
            cur.execute(
                f"INSERT INTO distributions ({col_str}) VALUES ({placeholders});",
                values,
            )
            return cur.lastrowid

    def update_distribution(self, dist_id: int, **kwargs: Any) -> bool:
        """Update one or more columns of a distribution.  Returns True if updated."""
        if not kwargs:
            return False
        allowed = {
            "song_id", "distributor", "release_type", "artist_name",
            "album_title", "songwriter", "language", "primary_genre",
            "cover_art_path", "is_instrumental", "lyrics_submitted",
            "release_date", "record_label", "ai_disclosure",
            "distrokid_url", "status", "error_message", "notes",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False

        set_clause = ", ".join(f"{col} = ?" for col in fields)
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        values = list(fields.values()) + [dist_id]

        with self._cursor() as cur:
            cur.execute(
                f"UPDATE distributions SET {set_clause} WHERE id = ?;",
                values,
            )
            return cur.rowcount > 0

    def delete_distribution(self, dist_id: int) -> bool:
        """Delete a distribution by id.  Returns True if deleted."""
        with self._cursor() as cur:
            cur.execute(
                "DELETE FROM distributions WHERE id = ?;", (dist_id,)
            )
            return cur.rowcount > 0

    # ==================================================================
    # UTILITY
    # ==================================================================

    def is_seeded(self) -> bool:
        """Return True if the genres table contains at least one row."""
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM genres;")
            row = cur.fetchone()
            return (row["cnt"] if row else 0) > 0

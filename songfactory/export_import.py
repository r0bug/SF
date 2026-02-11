"""Export and import Song Factory data (songs, lore, genres).

Supports:
- JSON export/import (round-trip, includes all fields)
- CSV export for songs (flat format for spreadsheet use)
- Personal bundle export/import (lore, genres, presets, artists, config)

Usage:
    from export_import import export_json, import_json, export_songs_csv
    from export_import import export_personal_bundle, import_personal_bundle

    export_json(db, "/path/to/backup.json", songs=True, lore=True, genres=True)
    report = import_json(db, "/path/to/backup.json")
    export_songs_csv(db, "/path/to/songs.csv")

    export_personal_bundle(db, "/path/to/bundle.json")
    report = import_personal_bundle(db, "/path/to/bundle.json")
"""

import csv
import json
import logging
import os
from datetime import datetime
from typing import Optional

from secure_config import SENSITIVE_KEYS

logger = logging.getLogger("songfactory.export_import")

EXPORT_VERSION = 1
BUNDLE_VERSION = 1

# Config keys safe to include in personal bundles
_BUNDLE_CONFIG_KEYS = {
    "ai_model", "submission_mode", "browser_path", "download_dir",
    "max_prompt_length", "use_xvfb", "dk_artist", "dk_songwriter",
    "lalals_username",
}


def export_json(
    db,
    path: str,
    songs: bool = True,
    lore: bool = True,
    genres: bool = True,
    song_ids: Optional[list[int]] = None,
) -> str:
    """Export data to a JSON file.

    Args:
        db: Database instance.
        path: Output file path.
        songs: Include songs in export.
        lore: Include lore entries in export.
        genres: Include genres in export.
        song_ids: If provided, only export these specific song IDs.

    Returns:
        The absolute path to the written file.
    """
    data = {
        "version": EXPORT_VERSION,
        "exported_at": datetime.now().isoformat(),
        "app": "Song Factory",
    }

    if genres:
        data["genres"] = db.get_all_genres()

    if lore:
        data["lore"] = db.get_all_lore()

    if songs:
        all_songs = db.get_all_songs()
        if song_ids is not None:
            id_set = set(song_ids)
            all_songs = [s for s in all_songs if s["id"] in id_set]
        # Remove internal fields that shouldn't be exported
        for s in all_songs:
            s.pop("id", None)
        data["songs"] = all_songs

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    logger.info("Exported data to %s", path)
    return os.path.abspath(path)


def export_songs_csv(db, path: str, song_ids: Optional[list[int]] = None) -> str:
    """Export songs to a flat CSV file.

    Args:
        db: Database instance.
        path: Output file path.
        song_ids: If provided, only export these specific song IDs.

    Returns:
        The absolute path to the written file.
    """
    all_songs = db.get_all_songs()
    if song_ids is not None:
        id_set = set(song_ids)
        all_songs = [s for s in all_songs if s["id"] in id_set]

    if not all_songs:
        raise ValueError("No songs to export")

    # Use all keys from the first song as CSV columns
    fieldnames = list(all_songs[0].keys())

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for song in all_songs:
            writer.writerow(song)

    logger.info("Exported %d songs to CSV: %s", len(all_songs), path)
    return os.path.abspath(path)


def import_json(db, path: str) -> dict:
    """Import data from a JSON file.

    Performs duplicate detection by title for songs and genres,
    and by title for lore entries.

    Args:
        db: Database instance.
        path: Path to the JSON file.

    Returns:
        dict with keys:
            songs_created, songs_skipped,
            lore_created, lore_skipped,
            genres_created, genres_skipped
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    version = data.get("version", 0)
    if version > EXPORT_VERSION:
        raise ValueError(
            f"Export file version {version} is newer than supported ({EXPORT_VERSION})"
        )

    report = {
        "songs_created": 0,
        "songs_skipped": 0,
        "lore_created": 0,
        "lore_skipped": 0,
        "genres_created": 0,
        "genres_skipped": 0,
    }

    # Import genres first (songs may reference them)
    if "genres" in data:
        existing_genres = {g["name"].lower(): g for g in db.get_all_genres()}
        for genre in data["genres"]:
            name = genre.get("name", "")
            if name.lower() in existing_genres:
                report["genres_skipped"] += 1
                continue
            db.add_genre(
                name=name,
                prompt_template=genre.get("prompt_template", ""),
                description=genre.get("description", ""),
                bpm_range=genre.get("bpm_range", ""),
                active=genre.get("active", True),
            )
            report["genres_created"] += 1

    # Import lore
    if "lore" in data:
        existing_lore = {l["title"].lower() for l in db.get_all_lore()}
        for entry in data["lore"]:
            title = entry.get("title", "")
            if title.lower() in existing_lore:
                report["lore_skipped"] += 1
                continue
            db.add_lore(
                title=title,
                content=entry.get("content", ""),
                category=entry.get("category", "general"),
                active=entry.get("active", True),
            )
            report["lore_created"] += 1

    # Import songs
    if "songs" in data:
        existing_songs = {s["title"].lower() for s in db.get_all_songs()}
        # Build genre name->id mapping for resolving genre_label
        genre_map = {g["name"].lower(): g["id"] for g in db.get_all_genres()}

        for song in data["songs"]:
            title = song.get("title", "")
            if title.lower() in existing_songs:
                report["songs_skipped"] += 1
                continue

            # Try to resolve genre_id from genre_label
            genre_label = song.get("genre_label", "")
            genre_id = song.get("genre_id")
            if genre_id is None and genre_label:
                genre_id = genre_map.get(genre_label.lower())

            db.add_song(
                title=title,
                genre_id=genre_id,
                genre_label=genre_label,
                prompt=song.get("prompt", ""),
                lyrics=song.get("lyrics", ""),
                user_input=song.get("user_input"),
                lore_snapshot=song.get("lore_snapshot"),
                status=song.get("status", "draft"),
            )
            report["songs_created"] += 1

    logger.info(
        "Import complete: %d songs (%d skipped), %d lore (%d skipped), %d genres (%d skipped)",
        report["songs_created"], report["songs_skipped"],
        report["lore_created"], report["lore_skipped"],
        report["genres_created"], report["genres_skipped"],
    )
    return report


def preview_import(path: str) -> dict:
    """Preview what would be imported without actually importing.

    Args:
        path: Path to the JSON file.

    Returns:
        dict with keys: song_count, lore_count, genre_count,
                        exported_at, version
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "version": data.get("version", 0),
        "exported_at": data.get("exported_at", "unknown"),
        "song_count": len(data.get("songs", [])),
        "lore_count": len(data.get("lore", [])),
        "genre_count": len(data.get("genres", [])),
    }


# ======================================================================
# Personal Bundle — portable export/import of lore, genres, presets,
# artists, and non-sensitive config for cloud sync.
# ======================================================================


def export_personal_bundle(
    db,
    path: str,
    lore_only: bool = False,
) -> str:
    """Export a personal data bundle to a JSON file.

    Includes lore, genres, presets, artists, and non-sensitive config.
    Sensitive keys (API keys, passwords) are never included.

    Args:
        db: Database instance.
        path: Output file path.
        lore_only: If True, only export lore entries.

    Returns:
        The absolute path to the written file.
    """
    data: dict = {
        "bundle_version": BUNDLE_VERSION,
        "exported_at": datetime.now().isoformat(),
        "app": "Song Factory",
    }

    # Lore — strip internal id
    all_lore = db.get_all_lore()
    data["lore"] = [
        {
            "title": e["title"],
            "content": e["content"],
            "category": e.get("category", "general"),
            "active": bool(e.get("active", True)),
        }
        for e in all_lore
    ]

    if not lore_only:
        # Genres — strip internal id
        data["genres"] = [
            {
                "name": g["name"],
                "prompt_template": g.get("prompt_template", ""),
                "description": g.get("description", ""),
                "bpm_range": g.get("bpm_range", ""),
                "active": bool(g.get("active", True)),
            }
            for g in db.get_all_genres()
        ]

        # Presets — resolve lore IDs to titles for portability
        lore_id_to_title = {e["id"]: e["title"] for e in all_lore}
        data["presets"] = [
            {
                "name": p["name"],
                "lore_titles": [
                    lore_id_to_title[lid]
                    for lid in p["lore_ids"]
                    if lid in lore_id_to_title
                ],
            }
            for p in db.get_all_lore_presets()
        ]

        # Artists — strip internal id
        data["artists"] = [
            {
                "name": a["name"],
                "is_default": bool(a.get("is_default", False)),
            }
            for a in db.get_all_artists()
        ]

        # Non-sensitive config
        all_config = db.get_all_config()
        data["config"] = {
            k: v for k, v in all_config.items()
            if k in _BUNDLE_CONFIG_KEYS and k not in SENSITIVE_KEYS
        }

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    logger.info("Exported personal bundle to %s", path)
    return os.path.abspath(path)


def import_personal_bundle(db, path: str) -> dict:
    """Import a personal data bundle, upserting by name/title.

    Unlike ``import_json`` which skips duplicates, this function updates
    existing entries when names match, making it suitable for cloud sync.

    Args:
        db: Database instance.
        path: Path to the bundle JSON file.

    Returns:
        dict with counts: genres_created, genres_updated, lore_created,
        lore_updated, presets_created, presets_updated, artists_created,
        artists_updated, config_updated.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    bundle_ver = data.get("bundle_version", 0)
    if bundle_ver > BUNDLE_VERSION:
        raise ValueError(
            f"Bundle version {bundle_ver} is newer than supported ({BUNDLE_VERSION})"
        )

    report = {
        "genres_created": 0,
        "genres_updated": 0,
        "lore_created": 0,
        "lore_updated": 0,
        "presets_created": 0,
        "presets_updated": 0,
        "artists_created": 0,
        "artists_updated": 0,
        "config_updated": 0,
    }

    # --- Genres: upsert by name ---
    if "genres" in data:
        existing = {g["name"].lower(): g for g in db.get_all_genres()}
        for genre in data["genres"]:
            name = genre.get("name", "")
            key = name.lower()
            if key in existing:
                db.update_genre(
                    existing[key]["id"],
                    prompt_template=genre.get("prompt_template", ""),
                    description=genre.get("description", ""),
                    bpm_range=genre.get("bpm_range", ""),
                    active=genre.get("active", True),
                )
                report["genres_updated"] += 1
            else:
                db.add_genre(
                    name=name,
                    prompt_template=genre.get("prompt_template", ""),
                    description=genre.get("description", ""),
                    bpm_range=genre.get("bpm_range", ""),
                    active=genre.get("active", True),
                )
                report["genres_created"] += 1

    # --- Lore: upsert by title ---
    if "lore" in data:
        existing = {e["title"].lower(): e for e in db.get_all_lore()}
        for entry in data["lore"]:
            title = entry.get("title", "")
            key = title.lower()
            if key in existing:
                db.update_lore(
                    existing[key]["id"],
                    content=entry.get("content", ""),
                    category=entry.get("category", "general"),
                    active=entry.get("active", True),
                )
                report["lore_updated"] += 1
            else:
                db.add_lore(
                    title=title,
                    content=entry.get("content", ""),
                    category=entry.get("category", "general"),
                    active=entry.get("active", True),
                )
                report["lore_created"] += 1

    # --- Presets: upsert by name, resolve lore titles to IDs ---
    if "presets" in data:
        # Build current title→id map after lore import
        lore_title_to_id = {e["title"].lower(): e["id"] for e in db.get_all_lore()}
        existing = {p["name"].lower(): p for p in db.get_all_lore_presets()}

        for preset in data["presets"]:
            name = preset.get("name", "")
            lore_titles = preset.get("lore_titles", [])
            lore_ids = [
                lore_title_to_id[t.lower()]
                for t in lore_titles
                if t.lower() in lore_title_to_id
            ]

            key = name.lower()
            if key in existing:
                db.update_lore_preset(existing[key]["id"], lore_ids=lore_ids)
                report["presets_updated"] += 1
            else:
                db.add_lore_preset(name, lore_ids)
                report["presets_created"] += 1

    # --- Artists: upsert by name ---
    if "artists" in data:
        existing = {a["name"].lower(): a for a in db.get_all_artists()}
        for artist in data["artists"]:
            name = artist.get("name", "")
            key = name.lower()
            if key in existing:
                db.update_artist(
                    existing[key]["id"],
                    is_default=artist.get("is_default", False),
                )
                report["artists_updated"] += 1
            else:
                db.add_artist(
                    name=name,
                    is_default=artist.get("is_default", False),
                )
                report["artists_created"] += 1

    # --- Config: merge non-sensitive keys ---
    if "config" in data:
        for key, value in data["config"].items():
            if key in SENSITIVE_KEYS:
                continue
            if key in _BUNDLE_CONFIG_KEYS:
                db.set_config(key, str(value))
                report["config_updated"] += 1

    logger.info(
        "Personal bundle import complete: %s",
        ", ".join(f"{k}={v}" for k, v in report.items() if v > 0),
    )
    return report


def preview_personal_bundle(path: str) -> dict:
    """Preview a personal bundle without importing.

    Args:
        path: Path to the bundle JSON file.

    Returns:
        dict with counts and metadata.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "bundle_version": data.get("bundle_version", 0),
        "exported_at": data.get("exported_at", "unknown"),
        "lore_count": len(data.get("lore", [])),
        "genre_count": len(data.get("genres", [])),
        "preset_count": len(data.get("presets", [])),
        "artist_count": len(data.get("artists", [])),
        "config_keys": list(data.get("config", {}).keys()),
    }

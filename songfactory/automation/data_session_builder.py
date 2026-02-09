"""
Song Factory - Data Session Builder

Assembles the data directory for the CD-Extra data session (Session 2),
containing MP3 files, lyrics text files, and Song Factory source code.
Pure functions, no QThread.
"""

import os
import shutil
from pathlib import Path


SONGFACTORY_DIR = Path(__file__).resolve().parent.parent
CD_PROJECTS_DIR = Path.home() / ".songfactory" / "cd_projects"


def build_data_directory(
    project: dict,
    tracks: list[dict],
    songs: list[dict],
    output_dir: str | None = None,
) -> str:
    """Build the data directory structure for the CD-Extra ISO.

    Args:
        project: CD project dict.
        tracks:  List of track dicts (with source_path, title, track_number).
        songs:   List of song dicts from the DB (matching tracks by song_id).
        output_dir: Base dir for the project.  Defaults to
                    ~/.songfactory/cd_projects/{id}/

    Returns:
        Path to the data directory root.
    """
    project_id = project.get("id", 0)
    if output_dir is None:
        output_dir = str(CD_PROJECTS_DIR / str(project_id))

    data_dir = os.path.join(output_dir, "data")

    # Clean previous data dir if it exists
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)

    # Build song lookup by id
    song_map = {s["id"]: s for s in songs if s.get("id")}

    # --- MP3 directory ---
    if project.get("include_mp3", True):
        mp3_dir = os.path.join(data_dir, "MP3")
        os.makedirs(mp3_dir, exist_ok=True)

        for track in tracks:
            src = track.get("source_path", "")
            if not src or not os.path.exists(src):
                continue
            num = track.get("track_number", 0)
            title = _safe_filename(track.get("title", f"Track {num}"))
            ext = os.path.splitext(src)[1] or ".mp3"
            dest = os.path.join(mp3_dir, f"{num:02d} - {title}{ext}")
            shutil.copy2(src, dest)

    # --- Lyrics directory ---
    if project.get("include_lyrics", True):
        lyrics_dir = os.path.join(data_dir, "Lyrics")
        os.makedirs(lyrics_dir, exist_ok=True)

        for track in tracks:
            song_id = track.get("song_id")
            if not song_id:
                continue
            song = song_map.get(song_id)
            if not song:
                continue
            lyrics = song.get("lyrics", "")
            if not lyrics or not lyrics.strip():
                continue

            num = track.get("track_number", 0)
            title = _safe_filename(track.get("title", f"Track {num}"))
            dest = os.path.join(lyrics_dir, f"{num:02d} - {title}.txt")
            with open(dest, "w", encoding="utf-8") as f:
                f.write(f"{track.get('title', '')}\n")
                f.write(f"Performed by {track.get('performer', 'Yakima Finds')}\n")
                f.write(f"{'=' * 40}\n\n")
                f.write(lyrics)

    # --- Source code directory ---
    if project.get("include_source", True):
        sf_dir = os.path.join(data_dir, "SongFactory", "songfactory")
        os.makedirs(sf_dir, exist_ok=True)

        _copy_source_tree(SONGFACTORY_DIR, sf_dir)

        # README
        readme_path = os.path.join(data_dir, "SongFactory", "README.txt")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("Song Factory — Yakima Finds\n")
            f.write("=" * 40 + "\n\n")
            f.write("AI-powered song generation desktop app.\n\n")
            f.write("Requirements:\n")
            f.write("  - Python 3.10+\n")
            f.write("  - PyQt6\n")
            f.write("  - Anthropic API key\n\n")
            f.write("Quick Start:\n")
            f.write("  cd songfactory\n")
            f.write("  python main.py\n")

    # --- Album info ---
    _write_album_info(project, tracks, data_dir)

    return data_dir


def _safe_filename(name: str) -> str:
    """Strip characters that are invalid in filenames."""
    invalid = '<>:"/\\|?*'
    result = "".join(c if c not in invalid else "_" for c in name)
    return result.strip(". ")[:80]


def _copy_source_tree(src_dir: Path, dest_dir: str) -> None:
    """Copy the songfactory source tree, skipping __pycache__ and .pyc."""
    for item in src_dir.iterdir():
        if item.name.startswith("__pycache__") or item.name.startswith("."):
            continue
        dest_path = os.path.join(dest_dir, item.name)
        if item.is_dir():
            os.makedirs(dest_path, exist_ok=True)
            _copy_source_tree(item, dest_path)
        elif item.suffix in (".py", ".txt", ".md", ".json", ".toml", ".cfg"):
            shutil.copy2(str(item), dest_path)


def _write_album_info(project: dict, tracks: list[dict], data_dir: str) -> None:
    """Write album_info.txt with metadata and track listing."""
    info_path = os.path.join(data_dir, "album_info.txt")
    os.makedirs(data_dir, exist_ok=True)

    with open(info_path, "w", encoding="utf-8") as f:
        album = project.get("album_title") or project.get("name", "Untitled")
        f.write(f"Album: {album}\n")
        f.write(f"Artist: {project.get('artist', 'Yakima Finds')}\n")
        if project.get("songwriter"):
            f.write(f"Songwriter: {project['songwriter']}\n")
        f.write(f"Tracks: {len(tracks)}\n")

        total = sum(t.get("duration_seconds", 0) for t in tracks)
        mins = int(total) // 60
        secs = int(total) % 60
        f.write(f"Total Duration: {mins}:{secs:02d}\n")
        f.write("\n" + "=" * 40 + "\n\n")

        for track in tracks:
            num = track.get("track_number", 0)
            title = track.get("title", "")
            dur = track.get("duration_seconds", 0)
            m = int(dur) // 60
            s = int(dur) % 60
            f.write(f"  {num:2d}. {title:<40s} {m}:{s:02d}\n")

        f.write(f"\n{'=' * 40}\n")
        f.write("Created with Song Factory — Yakima Finds\n")

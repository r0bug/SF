#!/usr/bin/env python3
"""Export every song with a given tag to a Google Drive folder.

Layout produced (one sub-folder per song):

    <dest>/
      Fresh Hop/
        Fresh Hop.txt            prompt, genre + metadata, then lyrics
        Fresh Hop - Version 1.mp3
        Fresh Hop - Version 2.mp3

History-imported songs are stored as two rows ("Title (V1)" / "Title (V2)");
those are merged into one folder. Non-MP3 audio is converted with ffmpeg.

The folder is staged locally, then pushed with ``rclone copy`` (never
``sync``), so files others add to the Drive folder are left alone.

Usage:
    scripts/export_tag_to_drive.py                       # FreshHop -> Drive:FreshHop
    scripts/export_tag_to_drive.py --tag FreshHop --dry-run
    scripts/export_tag_to_drive.py --no-upload           # stage locally only
    scripts/export_tag_to_drive.py --web                 # also refresh the web page

--web rebuilds the review page at yfevents.yakimafinds.com/freshhop
(backoffice ~/yakima): data/freshhop.json + uploads/freshhop/<song>/*.mp3.
Lore shown on the page is WEB_LORE below. Feedback and favorites on the
server are left untouched.
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys

DB_PATH = os.path.expanduser("~/.songfactory/songfactory.db")
STAGE_ROOT = os.path.expanduser("~/.songfactory/exports")
REMOTE = "songfactory-gdrive:"
# The remote is rooted at the SongFactory folder; this ID is the Drive root
# that contains it, so the export lands beside SongFactory, not inside it.
DRIVE_ROOT_ID = "0AAq_G8mSc9QiUk9PVA"

WEB_HOST = "backoffice"
WEB_ROOT = "yakima"
WEB_TITLE = "Fresh Hop Ale Festival Songs"
WEB_INTRO = ("Draft songs for the Fresh Hop Ale Festival. Have a listen, follow along "
             "with the lyrics, and leave requests or criticism under each song.")
# (lore id, page slug, display title)
WEB_LORE = [
    (74, "lore-fresh-hop-festival", "Fresh Hop Ale Festival"),
    (58, "lore-bert-grant", "Bert Grant & Yakima Brewing"),
    (16, "lore-songwriting-rules", "Songwriting Rules"),
    (1, "lore-pronunciation", "Pronunciation"),
]

_VERSION_RE = re.compile(r"\s*\(V(\d)\)\s*$", re.IGNORECASE)
_UNSAFE_RE = re.compile(r'[\\/:*?"<>|]+')


def safe_name(name: str) -> str:
    return _UNSAFE_RE.sub("", name).strip(" .") or "Untitled"


def load_tagged_songs(conn, tag):
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """SELECT s.* FROM songs s
           JOIN song_tags st ON st.song_id = s.id
           JOIN tags t ON t.id = st.tag_id
           WHERE t.name = ? COLLATE NOCASE
           ORDER BY s.id""",
        (tag,),
    ).fetchall()


def _norm_lyrics(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def audio_fingerprint(path):
    """Hash of the decoded audio, so re-tagged copies of one recording match."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-map", "0:a", "-f", "md5", "-"],
        capture_output=True, text=True,
    ).stdout.strip()
    return out or path


def group_songs(rows):
    """Group rows into songs by lyrics.

    Returns {title: {"rows": [...], "recordings": [(label, path), ...]}}.

    Every re-generation of the same lyrics (same-title retries, history
    "(V1)"/"(V2)" row pairs, or a retitled copy like "Hop Crowns") becomes one
    song; each generation is a "take" with its two versions. Recordings whose
    audio is identical are kept once.
    """
    groups = {}
    for r in rows:
        title = (r["title"] or "").strip()
        key = _norm_lyrics(r["lyrics"]) or ("title:" + _VERSION_RE.sub("", title).lower())
        groups.setdefault(key, []).append(r)

    songs = {}
    for grp in groups.values():
        grp.sort(key=lambda x: x["id"])
        # A take is one generation: a plain row with file_path_1/2, or the
        # (V1)/(V2) rows a history import split it into.
        takes = {}
        for r in grp:
            title = (r["title"] or "").strip()
            m = _VERSION_RE.search(title)
            if m:
                take = takes.setdefault(("v", _VERSION_RE.sub("", title)), {})
                if r["file_path_1"]:
                    take.setdefault(int(m.group(1)), r["file_path_1"])
            else:
                take = takes.setdefault(("row", r["id"]), {})
                for n, col in ((1, "file_path_1"), (2, "file_path_2")):
                    if r[col]:
                        take.setdefault(n, r[col])
        song_title = _VERSION_RE.sub("", (grp[0]["title"] or "").strip())
        multi = len(takes) > 1
        recordings, seen = [], set()
        for k, (_, take) in enumerate(takes.items(), start=1):
            for n in sorted(take):
                path = take[n]
                if not os.path.exists(path):
                    continue
                fp = audio_fingerprint(path)
                if fp in seen:
                    continue
                seen.add(fp)
                label = f"Take {k} · Version {n}" if multi else f"Version {n}"
                recordings.append((label, path))
        songs.setdefault(song_title, []).append({"rows": grp, "recordings": recordings})

    # Different lyrics under one title: tell them apart by genre ("Hip-Hop")
    named = {}
    for title, entries in songs.items():
        for e in entries:
            name = title
            if len(entries) > 1:
                genre = next((r["genre_label"] for r in e["rows"] if r["genre_label"]), "")
                tag = genre.split("(")[0].strip().title()
                name = f"{title} ({tag})" if tag else title
            while name in named:
                name += " (alt)"
            named[name] = e
    return named


def _fmt_duration(seconds):
    if not seconds:
        return None
    s = int(round(float(seconds)))
    return f"{s // 60}:{s % 60:02d}"


def _sibling(conn, row):
    """Another song generated from the same prompt that still has its genre.

    History-imported rows carry no genre/song idea; the original Song Creator
    row (or a re-generation of it) does."""
    if not row["prompt"]:
        return None
    return conn.execute(
        "SELECT * FROM songs WHERE prompt=? AND COALESCE(genre_label,'')<>'' "
        "ORDER BY id LIMIT 1",
        (row["prompt"],),
    ).fetchone()


def build_text(title, rows, conn):
    r = rows[0]
    if not r["genre_label"] and not r["genre_id"]:
        r = _sibling(conn, r) or r
    genre = r["genre_label"]
    if not genre and r["genre_id"]:
        g = conn.execute("SELECT name FROM genres WHERE id=?", (r["genre_id"],)).fetchone()
        genre = g[0] if g else None
    durations = [_fmt_duration(x["duration_seconds"]) for x in rows if x["duration_seconds"]]

    meta = [
        ("Genre", genre),
        ("Music style", r["music_style"]),
        ("Song idea", r["user_input"] or rows[0]["user_input"]),
        ("Voice", r["voice_used"]),
        ("Duration", " / ".join(durations) if durations else None),
        ("Created", rows[0]["lalals_created_at"] or rows[0]["created_at"]),
    ]

    out = [title, "=" * len(title), "", "PROMPT", "------", (rows[0]["prompt"] or "").strip(), ""]
    out += ["DETAILS", "-------"]
    out += [f"{k}: {v}" for k, v in meta if v]
    lyrics = next((x["lyrics"] for x in rows if x["lyrics"]), "")
    out += ["", "LYRICS", "------", lyrics.strip(), ""]
    return "\n".join(out)


def copy_as_mp3(src, dst):
    if src.lower().endswith(".mp3"):
        shutil.copy2(src, dst)
    else:
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", src,
             "-codec:a", "libmp3lame", "-q:a", "2", dst],
            check=True,
        )


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def publish_web(conn, songs):
    """Build data/freshhop.json + uploads and rsync them to the web host."""
    stage = os.path.join(STAGE_ROOT, "web")
    shutil.rmtree(stage, ignore_errors=True)
    page = {"title": WEB_TITLE, "intro": WEB_INTRO, "songs": [], "lore": []}
    for title, song in sorted(songs.items()):
        slug = slugify(title)
        r = song["rows"][0]
        src_row = r if (r["genre_label"] or r["genre_id"]) else (_sibling(conn, r) or r)
        os.makedirs(os.path.join(stage, "uploads/freshhop", slug))
        versions = []
        for i, (label, src) in enumerate(song["recordings"], start=1):
            fn = f"{slug}-{i}-r1.mp3"
            copy_as_mp3(src, os.path.join(stage, "uploads/freshhop", slug, fn))
            versions.append({"id": f"{slug}-{i}", "label": label, "src": f"/uploads/freshhop/{slug}/{fn}"})
        page["songs"].append({
            "slug": slug, "title": title, "genre": src_row["genre_label"] or "",
            "versions": versions,
            "lyrics": (next((x["lyrics"] for x in song["rows"] if x["lyrics"]), "") or "").strip(),
        })
    for lore_id, slug, title in WEB_LORE:
        row = conn.execute("SELECT content FROM lore WHERE id=?", (lore_id,)).fetchone()
        if row:
            page["lore"].append({"slug": slug, "title": title, "content": row[0].strip()})
    os.makedirs(os.path.join(stage, "data"))
    with open(os.path.join(stage, "data/freshhop.json"), "w", encoding="utf-8") as f:
        json.dump(page, f, indent=2, ensure_ascii=False)

    # Scratch dirs can be 0700; the web server must be able to read the audio
    subprocess.run(["chmod", "-R", "u=rwX,go=rX", stage], check=True)
    dest = f"{WEB_HOST}:{WEB_ROOT}"
    # --delete: uploads/freshhop holds only what this script generates
    subprocess.run(["rsync", "-a", "--delete", f"{stage}/uploads/freshhop/", f"{dest}/uploads/freshhop/"], check=True)
    subprocess.run(["rsync", "-a", f"{stage}/data/freshhop.json", f"{dest}/data/freshhop.json"], check=True)
    print(f"Web page updated: {len(page['songs'])} songs, {len(page['lore'])} lore entries")


def prune_drive(stage, dest, rclone_opts):
    """Delete files on Drive that an earlier export wrote and this one did not.

    Only names this script produces ("<Song>.txt", "<Song> - <label>.mp3")
    are candidates, so anything the board adds to the folder is left alone.
    """
    listing = subprocess.run(
        ["rclone", "lsjson", "-R", "--files-only", dest, *rclone_opts],
        capture_output=True, text=True, check=True,
    ).stdout
    current = set()
    for root, _, files in os.walk(stage):
        for f in files:
            current.add(os.path.relpath(os.path.join(root, f), stage))
    removed = 0
    for item in json.loads(listing or "[]"):
        path = item["Path"]
        parts = path.split("/")
        if len(parts) != 2 or path in current:
            continue
        folder, fname = parts
        ours = fname == f"{folder}.txt" or (
            fname.startswith(f"{folder} - ") and fname.endswith(".mp3"))
        if ours:
            subprocess.run(["rclone", "deletefile", f"{dest}/{path}", *rclone_opts], check=True)
            print(f"   removed stale: {path}")
            removed += 1
    if removed:
        subprocess.run(["rclone", "rmdirs", "--leave-root", dest, *rclone_opts], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tag", default="FreshHop")
    ap.add_argument("--folder", help="Drive folder name (default: the tag)")
    ap.add_argument("--dry-run", action="store_true", help="show plan only")
    ap.add_argument("--no-upload", action="store_true", help="stage locally only")
    ap.add_argument("--web", action="store_true", help="also refresh the /freshhop web page")
    args = ap.parse_args()
    folder = args.folder or args.tag

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    rows = load_tagged_songs(conn, args.tag)
    if not rows:
        sys.exit(f"No songs tagged '{args.tag}'.")
    songs = group_songs(rows)

    stage = os.path.join(STAGE_ROOT, safe_name(folder))
    if not args.dry_run:
        shutil.rmtree(stage, ignore_errors=True)
        os.makedirs(stage)

    problems = []
    for title, song in sorted(songs.items()):
        name = safe_name(title)
        print(f"{name}/  (ids {', '.join(str(r['id']) for r in song['rows'])})")
        song_dir = os.path.join(stage, name)
        if not args.dry_run:
            os.makedirs(song_dir)
            with open(os.path.join(song_dir, f"{name}.txt"), "w", encoding="utf-8") as f:
                f.write(build_text(title, song["rows"], conn))
        if not song["recordings"]:
            problems.append(f"{title}: no audio files found")
            print("   ! no audio")
        for label, src in song["recordings"]:
            dst_name = f"{name} - {label.replace(' · ', ' ')}.mp3"
            print(f"   {dst_name}  <- {src}")
            if not args.dry_run:
                copy_as_mp3(src, os.path.join(song_dir, dst_name))

    if problems:
        print("\nWarnings:\n  " + "\n  ".join(problems))
    if args.dry_run:
        return
    print(f"\nStaged: {stage}")
    if args.no_upload:
        return

    dest = f"{REMOTE}{folder}"
    print(f"Uploading to Drive: {folder}/ ...")
    rclone_opts = ["--drive-root-folder-id", DRIVE_ROOT_ID, "--tpslimit", "8", "--retries", "5"]
    subprocess.run(["rclone", "copy", stage, dest, *rclone_opts], check=True)
    prune_drive(stage, dest, rclone_opts)
    print("Done.")
    if args.web:
        publish_web(conn, songs)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Publish the whole Song Factory library to yfevents.yakimafinds.com/music.

Every song with audio on disk is grouped by lyrics (re-generations, retitled
history imports and lyric-less early copies of the same title become takes on
one card), sorted into theme pages, and pushed to backoffice:

    data/music.json            page content (read per request by the site)
    uploads/music/<song>/*.mp3 audio (WAV converted to MP3)

Songs tagged FreshHop are left out (they live on /freshhop). Theme placement is
keyword rules below plus explicit overrides; HIDDEN ids never publish.

Usage:
    scripts/export_music_site.py --dry-run     # print the page plan
    scripts/export_music_site.py               # build + publish
"""

import argparse
import collections
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_tag_to_drive import (  # noqa: E402
    DB_PATH, STAGE_ROOT, WEB_HOST, WEB_ROOT, audio_fingerprint, copy_as_mp3, slugify,
)

GITHUB_URL = "https://github.com/r0bug/SF"
TITLE = "Yakima Finds Music"
INTRO = (
    "Here is the music we created with Yakima Finds Song Factory, our homegrown "
    "songwriting tool, to help promote Yakima Finds, our neighbors on Second Street, "
    "local businesses and Yakima in general. Pick a page, press play, and enjoy."
)

# (slug, title, description) in display order
PAGES = [
    ("yakima-finds", "Yakima Finds & Second Street",
     "Anthems for the store and the block, in just about every genre we could think of."),
    ("churchills-books", "Churchill's Books",
     "Our neighbors at Churchill's Book Lovers, from quiet stacks to secret caverns."),
    ("downtown-nights", "Downtown Nights",
     "Brews & Cues, the Lotus Room and Friday nights downtown."),
    ("hops-and-beer", "Hops & Beer",
     "The valley that grows most of America's hops, and the beer history behind it."),
    ("valley-stories", "Valley Stories",
     "Yakima history, Kamiakin, and tales from around the valley."),
    ("tall-tales", "Halloween & Tall Tales",
     "Jerry's dinosaur suit, giant rats and other things that definitely happened."),
    ("friends-and-family", "Friends & Family",
     "Songs about the people who make Yakima Finds what it is."),
    ("early-cd-tracks", "Early CD Tracks",
     "Our first experiments, made for the Yakima Finds CD before Song Factory saved lyrics."),
    ("other", "Other",
     "Everything else: experiments, road trips and songs that wandered off topic."),
]

# Song ids (any row in the group) that never publish.
HIDDEN = {
    159, 367, 160, 368, 161, 369,      # B: John travel
    288, 289, 290, 291, 292, 293,      # D: Trent Johnson
    318, 319, 320, 321, 322, 323,      # test clips
    191,                               # untitled "Possible CD Track"
    392,                               # untagged Fresh Hop October retake
}

# Explicit placement: song id (any row in the group) -> page slug. Wins over rules.
OVERRIDES = {
    36: "friends-and-family", 40: "friends-and-family", 46: "friends-and-family",
    149: "friends-and-family", 150: "friends-and-family", 151: "friends-and-family",
    152: "friends-and-family", 153: "friends-and-family", 154: "friends-and-family",
    171: "friends-and-family", 363: "friends-and-family", 364: "friends-and-family",
    205: "friends-and-family",
    38: "tall-tales", 193: "tall-tales",
    16: "yakima-finds", 66: "yakima-finds", 276: "yakima-finds",
    148: "churchills-books",
    232: "other", 233: "other", 234: "other", 235: "other", 236: "other",
    237: "other", 238: "other", 239: "other", 240: "other",
    110: "other", 111: "other", 112: "other", 113: "other",
    350: "other", 389: "other", 384: "other", 376: "other", 375: "other",
    378: "other", 304: "other",
}

# Display titles for songs whose stored title is a placeholder ("Imported-…").
TITLE_OVERRIDES = {36: "Telly Knows", 38: "Dinosaur Suit For Sale"}

# Ordered keyword rules on title (+ lyrics where noted). First match wins.
RULES = [
    ("friends-and-family", r"next gen thrift|storage locker|buffalo wild|box and stack|giant dollar|dollar sale|treasure hunt saturday", False),
    ("other", r"sounders|seattle|rave green|match day|south end", True),
    ("churchills-books", r"churchill|paper paradise|paper garden|heavy paper|heavy spine|weight of (the )?ink|archaic inventory|bookstore|tunnels beneath|caverns", False),
    ("tall-tales", r"dino|xavier|rat parade|song machine|quest for yakima", False),
    ("hops-and-beer", r"\bhop|grant's gold|beer|brewing americana|foam", False),
    ("valley-stories", r"kamiakin|yak-eh-mah valley|keys road|historia|irrigation", False),
    ("downtown-nights", r"brews|downtown|friday night|lotusized|second street (family|heart)|on second street|the break", False),
    ("early-cd-tracks", r"^(possible )?cd track", False),
]

_V_RE = re.compile(r"\s*\(V(\d)\)\s*$", re.I)


def clean_title(t):
    t = _V_RE.sub("", t or "")
    t = re.sub(r"\b(possible\s+)?cd track\b\s*", "", t, flags=re.I)
    t = re.sub(r"\s+v\d\s*$", "", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


def title_key(t):
    return re.sub(r"[^a-z0-9]", "", clean_title(t).lower().replace("’", "'"))


def lyric_key(text):
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", text or "").lower()
    t = re.sub(r"[^a-z0-9]", "", t)
    return t[:160] if len(t) >= 40 else ""


def good_title(t, lkey):
    if not t or t.startswith("(") or re.match(r"(imported-|untitled)", t, re.I):
        return False
    # History imports name songs after the lyric's first line, cut at ~40 chars
    k = re.sub(r"[^a-z0-9]", "", t.lower())
    return not (lkey and len(t) >= 34 and lkey.startswith(k))


def group_library(rows):
    groups = collections.OrderedDict()
    by_title = {}
    for r in rows:
        k = lyric_key(r["lyrics"])
        if k:
            groups.setdefault(k, []).append(r)
            by_title.setdefault(title_key(r["title"]), k)
    for r in rows:
        if lyric_key(r["lyrics"]):
            continue
        k = by_title.get(title_key(r["title"])) or "t:" + title_key(r["title"])
        groups.setdefault(k, []).append(r)
    return groups


def build_song(key, grp):
    grp = sorted(grp, key=lambda x: x["id"])
    lkey = key if not key.startswith("t:") else ""
    # Prefer Song Creator rows (they have a genre) for the display title
    ordered = sorted(grp, key=lambda x: (not x["genre_label"], x["id"]))
    title = next((TITLE_OVERRIDES[r["id"]] for r in grp if r["id"] in TITLE_OVERRIDES), None)
    title = title or next((clean_title(r["title"]) for r in ordered
                           if good_title(clean_title(r["title"]), lkey)), None)
    if not title:
        first = next((l for l in (grp[0]["lyrics"] or "").splitlines()
                      if l.strip() and not l.startswith("[")), "Untitled")
        title = first.strip(" ,.")[:50]

    takes = collections.OrderedDict()
    for r in grp:
        t = r["title"] or ""
        m = _V_RE.search(t) if not r["file_path_2"] else None
        if m:
            take = takes.setdefault(("v", clean_title(t)), {})
            if r["file_path_1"]:
                take.setdefault(int(m.group(1)), r["file_path_1"])
        else:
            take = takes.setdefault(("row", r["id"]), {})
            for n, col in ((1, "file_path_1"), (2, "file_path_2")):
                if r[col]:
                    take.setdefault(n, r[col])
    multi = len(takes) > 1
    recordings, seen, fps = [], set(), {}
    for k, take in enumerate(takes.values(), start=1):
        for n in sorted(take):
            p = take[n]
            if not os.path.exists(p):
                continue
            fp = fps[p] = audio_fingerprint(p)
            if fp in seen:
                continue
            seen.add(fp)
            recordings.append((f"Take {k} · Version {n}" if multi else f"Version {n}", p))
    lyr = next((r["lyrics"] for r in grp if r["lyrics"]), "") or ""
    genre = next((r["genre_label"] for r in grp if r["genre_label"]), "") or ""
    return {"ids": [r["id"] for r in grp], "title": title, "genre": genre,
            "lyrics": lyr.strip(), "recordings": recordings,
            "raw_titles": [r["title"] or "" for r in grp], "fps": fps}


def classify(song):
    ids = set(song["ids"])
    for i in song["ids"]:
        if i in OVERRIDES:
            return OVERRIDES[i]
    hay_t = " ".join([song["title"]] + song["raw_titles"]).lower()
    for page, pat, use_lyrics in RULES:
        hay = hay_t + (" " + song["lyrics"].lower() if use_lyrics else "")
        if re.search(pat, hay, re.I):
            return page
    if ids and max(ids) <= 200 and not song["lyrics"]:
        return "early-cd-tracks"
    return "yakima-finds"


# Spellings tried for "Yakima": (spelling, song id whose recording demonstrates it)
SPELLINGS = [
    ("Yak-uh-Ma", 185), ("Yak-imah", 183), ("Yah-Ka-Mah", 366), ("YakEmah", 158),
    ("Yak-i-mah", 356), ("Yah-Ka-Ma", 352), ("Yah Kah Mah", 351), ("Yak-i-Mah", 107),
    ("Yahkima", 298), ("Yahkuhma", 300), ("Yak-eh-Mah", 57),
]

PRONUNCIATION = [
    ("The problem",
     "AI singers read text, not intent. Given the word \"Yakima\", they said it a "
     "different way from one song to the next, and usually not the way anyone here says it."),
    ("What we tried",
     "From January to March 2026 we spelled the name phonetically in the lyrics and "
     "listened to what came back: Yah-Ka-Ma, Yah Kah Mah, Yak-uh-Ma, Yak-imah, YakEmah, "
     "Yak-i-Mah, Yahkima, Yahkuhma. Every attempt is still in this library; many song "
     "titles carry the spelling being tested. Hear a few of them below."),
    ("What worked",
     "Yak-eh-Mah. It became Song Factory's rule: every lyric spells it that way."),
    ("The second problem: names",
     "The AI kept proper names like \"Yakima Finds\" and \"Yakima River\" in normal "
     "spelling, so a single song would pronounce the town two different ways. Song "
     "Factory now rewrites every \"Yakima\" to Yak-eh-Mah automatically before anything "
     "is sung."),
    ("Rhymes",
     "When Yakima ends a line, it has to rhyme with how it is sung, not how it is spelled."),
    ("It's not just Yakima",
     "Local names trip it up too. For the Fresh Hop songs the festival committee flagged "
     "pFriem (now written \"Freem\") and Cowiche (\"Cow-itch-ee\")."),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    fresh = {r[0] for r in conn.execute(
        "SELECT st.song_id FROM song_tags st JOIN tags t ON t.id=st.tag_id "
        "WHERE t.name='FreshHop' COLLATE NOCASE")}
    rows = [r for r in conn.execute("SELECT * FROM songs ORDER BY id")
            if r["id"] not in fresh
            and any(r[c] and os.path.exists(r[c]) for c in ("file_path_1", "file_path_2"))]

    songs = []
    for key, grp in group_library(rows).items():
        if any(r["id"] in HIDDEN for r in grp):
            continue
        s = build_song(key, grp)
        if s["recordings"]:
            s["page"] = classify(s)
            songs.append(s)

    # Same title, different lyrics: add the genre, then II/III if still equal
    by_title = collections.defaultdict(list)
    for s in songs:
        by_title[s["title"].lower().replace("’", "'")].append(s)
    for dupes in by_title.values():
        if len(dupes) < 2:
            continue
        dupes.sort(key=lambda s: min(s["ids"]))
        for s in dupes:
            tag = s["genre"].split("(")[0].strip().title()
            if tag:
                s["title"] = f"{s['title']} ({tag})"
        counts = collections.Counter(s["title"] for s in dupes)
        seen_n = collections.Counter()
        for s in dupes:
            if counts[s["title"]] > 1:
                seen_n[s["title"]] += 1
                if seen_n[s["title"]] > 1:
                    s["title"] += " " + ["", "", "II", "III", "IV", "V"][seen_n[s["title"]]]
    by_page = collections.defaultdict(list)
    for s in songs:
        by_page[s["page"]].append(s)
    used_slugs = set()
    for slug, title, _ in PAGES:
        lst = sorted(by_page[slug], key=lambda s: s["title"].lower())
        by_page[slug] = lst
        print(f"\n== {title} ({len(lst)})")
        for s in lst:
            base = slugify(s["title"]) or "song"
            sslug, n = base, 2
            while sslug in used_slugs:
                sslug, n = f"{base}-{n}", n + 1
            used_slugs.add(sslug)
            s["slug"] = sslug
            print(f"   {s['title']}  [{len(s['recordings'])} rec] ids={s['ids']}")
    print(f"\n{len(songs)} songs, {sum(len(s['recordings']) for s in songs)} recordings")
    if args.dry_run:
        return

    stage = os.path.join(STAGE_ROOT, "music")
    shutil.rmtree(stage, ignore_errors=True)
    out = {"title": TITLE, "intro": INTRO, "githubUrl": GITHUB_URL, "pages": [],
           "pronunciation": {"sections": [{"heading": h, "body": b} for h, b in PRONUNCIATION],
                             "examples": []}}
    url_by_fp = {}
    for slug, title, desc in PAGES:
        page = {"slug": slug, "title": title, "description": desc, "songs": []}
        for s in by_page[slug]:
            d = os.path.join(stage, "uploads/music", s["slug"])
            os.makedirs(d)
            versions = []
            for i, (label, path) in enumerate(s["recordings"], start=1):
                fn = f"{s['slug']}-{i}-r1.mp3"
                copy_as_mp3(path, os.path.join(d, fn))
                url = f"/uploads/music/{s['slug']}/{fn}"
                versions.append({"label": label, "src": url})
                url_by_fp[s["fps"][path]] = url
            page["songs"].append({"slug": s["slug"], "title": s["title"], "genre": s["genre"],
                                  "lyrics": s["lyrics"], "versions": versions})
        out["pages"].append(page)

    examples = []
    for spelling, sid in SPELLINGS:
        r = conn.execute("SELECT title, file_path_1, lalals_created_at, created_at FROM songs WHERE id=?",
                         (sid,)).fetchone()
        if not r or not r["file_path_1"] or not os.path.exists(r["file_path_1"]):
            continue
        url = url_by_fp.get(audio_fingerprint(r["file_path_1"]))
        if url:
            examples.append({
                "spelling": spelling, "song": clean_title(r["title"]),
                "date": (r["lalals_created_at"] or r["created_at"] or "")[:7], "src": url})
    # Oldest attempt first; the spelling that stuck goes last
    examples.sort(key=lambda e: (e["spelling"] == "Yak-eh-Mah", e["date"]))
    out["pronunciation"]["examples"] = examples

    os.makedirs(os.path.join(stage, "data"))
    with open(os.path.join(stage, "data/music.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    subprocess.run(["chmod", "-R", "u=rwX,go=rX", stage], check=True)
    dest = f"{WEB_HOST}:{WEB_ROOT}"
    subprocess.run(["rsync", "-a", "--delete", f"{stage}/uploads/music/", f"{dest}/uploads/music/"], check=True)
    subprocess.run(["rsync", "-a", f"{stage}/data/music.json", f"{dest}/data/music.json"], check=True)
    print(f"Published {len(songs)} songs, {len(out['pronunciation']['examples'])} pronunciation examples")


if __name__ == "__main__":
    main()

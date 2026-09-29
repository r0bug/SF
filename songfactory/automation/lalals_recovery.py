"""Recover missing downloads for library songs from the lalals projects API.

Used by the Library's "Recover Downloads", "Recover Error Songs" and the
per-song "Recover from Lalals" action — e.g. after "Song is Done - Refresh"
errored.  Two lookup strategies, in order:

1. Stored version IDs (``conversion_id_1/2``, or ``task_id`` for history
   imports) → ``projects/front/get-one-by-id``.
2. No usable IDs (the submit itself failed to capture them) → find the
   song in the history by its prompt and take the newest finished pair.
"""

import logging
from collections import defaultdict

from automation.lalals_api import (
    LalalsApiError, LEGACY_S3_BASE, project_audio_url, version_number,
)

logger = logging.getLogger("songfactory.automation")


def _audio_url(project: dict) -> str:
    url = project_audio_url(project)
    if not url and project.get("conversion_status") == "SUCCESS" and project.get("id"):
        # Early-2026 projects: broken track_url, audio still at legacy path
        url = f"{LEGACY_S3_BASE}/{project['id']}/{project['id']}.mp3"
    return url


def _prompt_of(project: dict) -> str:
    ip = (project.get("queue_task") or {}).get("input_payload") or {}
    return (ip.get("prompt") if isinstance(ip, dict) else "") or ""


def find_by_prompt(prompt: str, history: list[dict]) -> list[dict]:
    """Newest finished generation (1-2 versions) whose prompt matches."""
    prompt = (prompt or "").strip()
    if not prompt:
        return []
    groups = defaultdict(list)
    for p in history:
        if (p.get("conversionType") == "MUSIC_AI"
                and p.get("conversion_status") == "SUCCESS"
                and _prompt_of(p).strip() == prompt):
            op = (p.get("queue_task") or {}).get("output_payload") or {}
            key = (op.get("taskId") if isinstance(op, dict) else None) or p.get("id")
            groups[key].append(p)
    if not groups:
        return []
    newest = max(groups.values(),
                 key=lambda g: max(str(p.get("date_added", "")) for p in g))
    return sorted(newest, key=version_number)[:2]


def locate_versions(api, song: dict, history: list[dict] | None = None) -> list[dict]:
    """Return the song's lalals projects (version 1 first), possibly empty."""
    ids = [song.get("conversion_id_1"), song.get("conversion_id_2")]
    if not any(ids) and song.get("task_id"):
        ids = [song["task_id"]]  # history imports store the project id here
    found = []
    for pid in (i for i in ids if i):
        try:
            detail = api.get_project(pid)
        except LalalsApiError:
            continue
        if detail.get("conversion_status") == "SUCCESS" and _audio_url(detail):
            found.append(detail)
    if found:
        return found
    if history is not None:
        return find_by_prompt(song.get("prompt", ""), history)
    return []


def recover_song(api, dm, song: dict, history: list[dict] | None = None) -> dict:
    """Download a song's versions; return DB update kwargs ({} if not found).

    Args:
        api: ``LalalsApi`` on a logged-in page.
        dm: ``DownloadManager``.
        song: Library song row (dict).
        history: Optional full project list for the prompt fallback.
    """
    title = song.get("title") or "Untitled"
    versions = locate_versions(api, song, history)
    update = {}
    for idx, project in enumerate(versions[:2], start=1):
        url = _audio_url(project)
        try:
            path = dm.save_from_url(url, title, idx)
        except Exception as e:
            logger.warning(f"Recovery download failed for '{title}' v{idx}: {e}")
            continue
        update[f"file_path_{idx}"] = str(path)
        update[f"file_size_{idx}"] = path.stat().st_size
        update[f"audio_url_{idx}"] = url
        update[f"conversion_id_{idx}"] = project["id"]
    if update.get("file_path_1") or update.get("file_path_2"):
        if not update.get("file_path_1"):
            update["file_path_1"] = update.pop("file_path_2")
        update["status"] = "completed"
        update["notes"] = None
        logger.info(f"Recovered '{title}': {len(versions)} version(s)")
    else:
        update = {}
    return update

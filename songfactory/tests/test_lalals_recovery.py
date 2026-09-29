"""Recovering missing downloads from the lalals projects API."""

from pathlib import Path

from automation.lalals_api import LalalsApiError
from automation.lalals_recovery import find_by_prompt, recover_song


def proj(pid, prompt="p", ver="Version 1", task="t1", status="SUCCESS",
         added="2026-09-28T10:00:00Z", url=None):
    return {
        "id": pid, "conversionType": "MUSIC_AI", "conversion_status": status,
        "version_number": ver, "date_added": added,
        "track_url": url if url is not None else f"https://cdn/x/{pid}.mp3",
        "queue_task": {"input_payload": {"prompt": prompt},
                       "output_payload": {"taskId": task}},
    }


class FakeApi:
    def __init__(self, projects):
        self.projects = {p["id"]: p for p in projects}

    def get_project(self, pid):
        if pid not in self.projects:
            raise LalalsApiError("404", 404)
        return self.projects[pid]


class FakeDM:
    def __init__(self, tmp):
        self.tmp, self.saved = tmp, []

    def save_from_url(self, url, title, version):
        p = Path(self.tmp) / f"{title}_v{version}.mp3"
        p.write_bytes(b"x" * 10)
        self.saved.append(url)
        return p


def test_recovers_by_stored_ids(tmp_path):
    api = FakeApi([proj("a"), proj("b", ver="Version 2")])
    dm = FakeDM(tmp_path)
    song = {"title": "S", "conversion_id_1": "a", "conversion_id_2": "b"}
    up = recover_song(api, dm, song)
    assert up["status"] == "completed"
    assert up["file_path_1"].endswith("S_v1.mp3")
    assert up["file_path_2"].endswith("S_v2.mp3")
    assert dm.saved == ["https://cdn/x/a.mp3", "https://cdn/x/b.mp3"]


def test_task_id_used_for_history_imports(tmp_path):
    up = recover_song(FakeApi([proj("a")]), FakeDM(tmp_path),
                      {"title": "S", "task_id": "a"})
    assert up["conversion_id_1"] == "a"


def test_broken_track_url_uses_legacy_s3(tmp_path):
    dm = FakeDM(tmp_path)
    recover_song(FakeApi([proj("a", url="https://lalals.s3.amazonaws.com/")]), dm,
                 {"title": "S", "conversion_id_1": "a"})
    assert dm.saved == ["https://lalals.s3.amazonaws.com/conversions/standard/a/a.mp3"]


def test_prompt_fallback_when_no_ids(tmp_path):
    history = [proj("a", prompt="rock song"), proj("b", prompt="rock song", ver="Version 2"),
               proj("c", prompt="other")]
    up = recover_song(FakeApi(history), FakeDM(tmp_path),
                      {"title": "S", "prompt": " rock song "}, history)
    assert (up["conversion_id_1"], up["conversion_id_2"]) == ("a", "b")


def test_prompt_match_picks_newest_generation():
    history = [
        proj("old1", task="t-old", added="2026-09-01T00:00:00Z"),
        proj("old2", task="t-old", ver="Version 2", added="2026-09-01T00:00:00Z"),
        proj("new2", task="t-new", ver="Version 2", added="2026-09-28T00:00:00Z"),
        proj("new1", task="t-new", added="2026-09-28T00:00:00Z"),
        proj("fail", task="t-f", status="FAILED", added="2026-09-29T00:00:00Z"),
    ]
    assert [p["id"] for p in find_by_prompt("p", history)] == ["new1", "new2"]


def test_not_found_returns_empty(tmp_path):
    assert recover_song(FakeApi([]), FakeDM(tmp_path),
                        {"title": "S", "conversion_id_1": "zzz", "prompt": "p"}, []) == {}
    # still generating → nothing to download yet
    assert recover_song(FakeApi([proj("a", status="ONGOING", url="")]), FakeDM(tmp_path),
                        {"title": "S", "conversion_id_1": "a"}) == {}

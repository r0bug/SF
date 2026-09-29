"""Tests for the lalals.com /api/backend client and history normalization."""

from datetime import datetime, timedelta, timezone

import pytest

from automation.lalals_api import (
    LalalsApi, LalalsApiError, project_audio_url, version_number,
)


class FakePage:
    """Stands in for a Playwright page; routes in-page fetches to *handler*."""

    url = "https://lalals.com/produce"

    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def evaluate(self, js, args):
        self.calls.append(args)
        return self.handler(args)

    def goto(self, url, **kw):
        self.url = url

    def wait_for_load_state(self, *a, **kw):
        pass

    def wait_for_timeout(self, ms):
        pass


def ok(data, status=200):
    return {"ok": True, "status": status, "data": data}


SESSION = ok({"user": {"id": "uid-1"}, "csrfToken": "tok"})


def project(pid, name="Song", ver="Version 1", status="SUCCESS",
            ctype="MUSIC_AI", prompt="a prompt", added=None,
            url="https://lalals.s3.amazonaws.com/conversions/web/standard/x/x.mp3"):
    return {
        "id": pid, "track_name": name, "version_number": ver,
        "conversion_status": status, "conversionType": ctype,
        "date_added": added or "2026-09-28T12:00:00.000Z",
        "track_url": url, "audio_link": url,
        "queue_task": {"input_payload": {"prompt": prompt}},
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_audio_url_prefers_track_url(self):
        item = {"track_url": "https://b.s3.amazonaws.com/a/b.mp3",
                "audio_link": "https://b.s3.amazonaws.com/c/d.mp3"}
        assert project_audio_url(item).endswith("/a/b.mp3")

    def test_audio_url_skips_bare_bucket(self):
        item = {"track_url": "", "audio_link": "https://lalals.s3.amazonaws.com",
                "source": "https://lalals.s3.amazonaws.com/x/y.wav"}
        assert project_audio_url(item) == "https://lalals.s3.amazonaws.com/x/y.wav"

    def test_audio_url_empty(self):
        assert project_audio_url({}) == ""
        assert project_audio_url({"track_url": None}) == ""

    def test_version_number(self):
        assert version_number({"version_number": "Version 2"}) == 2
        assert version_number({}) == 1


# ---------------------------------------------------------------------------
# Transport / session
# ---------------------------------------------------------------------------

class TestTransport:

    def test_request_raises_on_http_error(self):
        page = FakePage(lambda a: {"ok": False, "status": 500,
                                   "data": {"message": "boom"}})
        with pytest.raises(LalalsApiError) as exc:
            LalalsApi(page).request("GET", "x")
        assert exc.value.status == 500
        assert "boom" in str(exc.value)

    def test_logged_out_is_none(self):
        page = FakePage(lambda a: {"ok": False, "status": 401, "data": {}})
        api = LalalsApi(page)
        assert api.get_session_user() is None
        assert api.is_logged_in() is False

    def test_user_id_from_session(self):
        page = FakePage(lambda a: SESSION)
        assert LalalsApi(page).get_user_id() == "uid-1"

    def test_ensure_origin_navigates_off_site(self):
        page = FakePage(lambda a: SESSION)
        page.url = "about:blank"
        LalalsApi(page).get_session_user()
        assert page.url.startswith("https://lalals.com")


# ---------------------------------------------------------------------------
# History pagination
# ---------------------------------------------------------------------------

class TestIterProjects:

    def test_paginates_with_top_level_cursor(self):
        pages = {
            1: ok({"data": [project("a"), project("b")], "hasMore": True,
                   "nextCursor": {"page": 2, "limit": 50}}),
            2: ok({"data": [project("c")], "hasMore": False, "nextCursor": None}),
        }

        def handler(a):
            if a["path"] == "auth/session":
                return SESSION
            body = a["body"]
            assert "cursor" not in body  # wrapping silently returns page 1
            return pages[body["page"]]

        ids = [p["id"] for p in LalalsApi(FakePage(handler)).iter_projects()]
        assert ids == ["a", "b", "c"]

    def test_stops_when_page_repeats(self):
        def handler(a):
            if a["path"] == "auth/session":
                return SESSION
            return ok({"data": [project("a")], "hasMore": True,
                       "nextCursor": {"page": 2, "limit": 50}})

        ids = [p["id"] for p in LalalsApi(FakePage(handler)).iter_projects()]
        assert ids == ["a"]


# ---------------------------------------------------------------------------
# Workflow submission
# ---------------------------------------------------------------------------

class TestSubmitMusicAi:

    def test_create_then_generate(self):
        seen = []

        def handler(a):
            seen.append((a["method"], a["path"], a["body"]))
            if a["path"] == "v1/workflows":
                return ok({"projectId": "wf-1", "state": "INITIAL",
                           "allowedActions": ["generate_music_ai", "start_produce"]})
            if a["path"] == "v1/workflows/wf-1/action":
                return ok({"projectId": "wf-1", "state": "GENERATING_AUDIO",
                           "allowedActions": []})
            raise AssertionError(a)

        snap = LalalsApi(FakePage(handler)).submit_music_ai("p", "l")
        assert snap["state"] == "GENERATING_AUDIO"

        create, action = seen
        assert create[2]["workflowId"] == "produce_track_v1"
        assert create[2]["initialContext"]["workflow_mode"] == "MUSIC_AI"
        assert create[2]["initialContext"]["lyrics"] == "l"
        assert action[2]["action"] == "generate_music_ai"
        assert action[2]["payload"]["prompt"] == "p"

    def test_raises_when_generate_not_allowed(self):
        def handler(a):
            return ok({"projectId": "wf-1", "state": "WAITING_FOR_LYRICS_APPROVAL",
                       "allowedActions": ["edit_lyrics"]})

        with pytest.raises(LalalsApiError):
            LalalsApi(FakePage(handler)).submit_music_ai("p", "l")

    def test_retries_errored_workflow(self):
        actions = []

        def handler(a):
            if a["path"] == "v1/workflows":
                return ok({"projectId": "wf", "state": "ERROR",
                           "allowedActions": ["retry"]})
            actions.append(a["body"]["action"])
            return ok({"projectId": "wf", "state": "INITIAL",
                       "allowedActions": ["generate_music_ai"]})

        LalalsApi(FakePage(handler)).submit_music_ai("p", "l")
        assert actions == ["retry", "generate_music_ai"]


class TestFindGeneratedProjects:

    def test_matches_prompt_and_time(self):
        since = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        items = [
            project("v2", ver="Version 2", prompt="mine", added="2026-09-28T12:01:00Z"),
            project("v1", ver="Version 1", prompt="mine", added="2026-09-28T12:01:00Z"),
            project("other", prompt="someone else", added="2026-09-28T12:01:00Z"),
            project("old", prompt="mine", added="2026-09-27T12:00:00Z"),
            project("lyr", ctype="LYRICS_GENERATION", prompt="mine",
                    added="2026-09-28T12:01:00Z"),
        ]

        def handler(a):
            if a["path"] == "auth/session":
                return SESSION
            return ok({"data": items})

        found = LalalsApi(FakePage(handler)).find_generated_projects("mine", since)
        assert [p["id"] for p in found] == ["v1", "v2"]


# ---------------------------------------------------------------------------
# History import normalization
# ---------------------------------------------------------------------------

class TestNormalizeProjectItem:

    def _norm(self, item):
        from automation.history_importer import HistoryImportWorker
        return HistoryImportWorker._normalize_project_item(item)

    def test_one_song_per_version(self):
        song = self._norm(project("pid-2", name="Lien", ver="Version 2"))
        assert song["title"] == "Lien (V2)"
        assert song["task_id"] == song["conversion_id_1"] == "pid-2"
        assert song["audio_url_1"].endswith("x.mp3")
        assert song["prompt"] == "a prompt"

    def test_skips_failed_and_non_music(self):
        assert self._norm(project("f", status="FAILED")) is None
        assert self._norm(project("l", ctype="LYRICS_GENERATION")) is None

    def test_metadata_roundtrip(self):
        """extract_metadata() keeps the real track_url, not a built S3 URL."""
        from automation.lalals_driver import LalalsDriver
        url = "https://lalals.s3.amazonaws.com/conversions/standard/old/old.mp3"
        meta = LalalsDriver.extract_metadata(self._norm(project("old", url=url)))
        assert meta["audio_url_1"] == url
        assert meta["conversion_id_1"] == "old"

    def test_broken_track_url_falls_back_to_legacy_s3(self):
        item = project("abc", url="https://lalals.s3.amazonaws.com/")
        item["audio_link"] = "https://lalals.s3.amazonaws.com/null"
        song = self._norm(item)
        assert song["audio_url_1"] == (
            "https://lalals.s3.amazonaws.com/conversions/standard/abc/abc.mp3"
        )

    def test_skips_unfinished(self):
        assert self._norm(project("g", status="ONGOING")) is None

    def test_prompt_as_track_name_is_shortened(self):
        long_name = "a song in the style of kris kristofferson " * 5 + "\nVerse 1\n..."
        song = self._norm(project("k", name=long_name))
        assert len(song["title"]) < 70
        assert song["title"].endswith("… (V1)")


def test_safe_title_caps_long_names(tmp_path):
    from automation.download_manager import DownloadManager
    dm = DownloadManager(str(tmp_path))
    path = dm.get_file_path("word " * 200, 1, date_prefix="2026-09-28")
    assert len(path.name.encode()) < 120
    assert len(path.parent.name.encode()) < 120

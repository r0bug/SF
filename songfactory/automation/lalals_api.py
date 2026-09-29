"""Thin client for the lalals.com backend API (post-2026 site redesign).

lalals.com retired ``devapi.lalals.com`` (DNS no longer resolves).  The
frontend now talks to a same-origin proxy at ``https://lalals.com/api/backend``
authenticated by the browser's session cookies.  Mutating requests also need
``X-Lalals-Auth-Version: 2`` and an ``X-Lalals-CSRF`` token obtained from
``GET /auth/session``.

Because auth lives in (httpOnly) cookies, every request is issued from inside
the Playwright page via ``page.evaluate(fetch(...))`` rather than from Python.

Song generation is a server-side workflow ("Co-Producer"):

1. ``POST v1/workflows`` ``{workflowId: "produce_track_v1", initialContext}``
   → snapshot ``{projectId, workflowId, state, context, allowedActions}``
2. ``POST v1/workflows/{projectId}/action``
   ``{action: "generate_music_ai", payload}`` → snapshot
3. ``GET v1/workflows/{projectId}`` until ``state`` is ``COMPLETED``/``ERROR``

Finished tracks show up in ``POST user/{uid}/projects`` (one entry per
version, each with its own ``id`` and a ready-to-download ``track_url``).
"""

import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

logger = logging.getLogger("songfactory.automation")

SITE = "https://lalals.com"
PRODUCE_URL = f"{SITE}/produce"
API_BASE = "/api/backend"
# Newer generations; older ones live under conversions/standard.  Always
# prefer a project's track_url over building a URL from this.
S3_BASE = "https://lalals.s3.amazonaws.com/conversions/web/standard"
# Early-2026 projects often have a broken track_url (bare bucket root) but
# their audio is still at LEGACY_S3_BASE/{id}/{id}.mp3.
LEGACY_S3_BASE = "https://lalals.s3.amazonaws.com/conversions/standard"

WORKFLOW_ID = "produce_track_v1"
WORKFLOW_TERMINAL_STATES = {"COMPLETED", "ERROR"}

# Slider defaults used by the Co-Producer UI (0-100 slider / 100).
DEFAULT_INTENSITY = 0.6


class LalalsApiError(Exception):
    """Raised when a lalals backend call fails."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


_REQUEST_JS = """
async ({ method, path, body, base }) => {
    const headers = { 'Content-Type': 'application/json',
                      'X-Lalals-Auth-Version': '2' };
    if (method !== 'GET') {
        if (!window.__sfCsrf) {
            try {
                const s = await fetch(base + '/auth/session',
                                      { credentials: 'include' });
                if (s.ok) window.__sfCsrf = (await s.json()).csrfToken || '';
            } catch (e) {}
        }
        if (window.__sfCsrf) headers['X-Lalals-CSRF'] = window.__sfCsrf;
    }
    try {
        const resp = await fetch(base + '/' + path.replace(/^\\/+/, ''), {
            method, headers, credentials: 'include',
            body: body === null ? undefined : JSON.stringify(body),
        });
        let data = null;
        try { data = await resp.json(); } catch (e) {}
        if (resp.status === 403) window.__sfCsrf = null;  // token rotated
        return { ok: resp.ok, status: resp.status, data };
    } catch (e) {
        return { ok: false, status: 0, data: null, error: String(e) };
    }
}
"""


def project_audio_url(item: dict) -> str:
    """Return the downloadable audio URL for a projects-list item.

    Mirrors the frontend: first of track_url / audio_link / source whose
    path ends in a filename (``audio_link`` is sometimes a bare bucket URL).
    """
    for key in ("track_url", "audio_link", "source"):
        url = (item or {}).get(key) or ""
        if not url.startswith("http"):
            continue
        path = urlparse(url).path.strip("/")
        if path and "." in path.rsplit("/", 1)[-1]:
            return url
    return ""


def version_number(item: dict) -> int:
    """Parse ``"Version 2"`` → 2 (defaults to 1)."""
    raw = str((item or {}).get("version_number") or "")
    digits = "".join(ch for ch in raw if ch.isdigit())
    return int(digits) if digits else 1


class LalalsApi:
    """Issue lalals backend calls through an authenticated Playwright page."""

    def __init__(self, page):
        self.page = page
        self._user_id = ""

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def ensure_origin(self):
        """Make sure the page is on lalals.com so relative fetches work."""
        try:
            url = self.page.url or ""
        except Exception:
            url = ""
        if not url.startswith(SITE):
            self.page.goto(PRODUCE_URL, wait_until="domcontentloaded")
            try:
                self.page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

    def request(self, method: str, path: str, body=None) -> dict:
        """Call ``{API_BASE}/{path}`` and return the parsed JSON body.

        Raises:
            LalalsApiError: On network failure or non-2xx status.
        """
        self.ensure_origin()
        result = self.page.evaluate(_REQUEST_JS, {
            "method": method.upper(), "path": path,
            "body": body, "base": API_BASE,
        })
        if not result or not result.get("ok"):
            status = (result or {}).get("status", 0)
            data = (result or {}).get("data") or {}
            msg = (data.get("message") if isinstance(data, dict) else None) \
                or (result or {}).get("error") or f"HTTP {status}"
            raise LalalsApiError(f"{method} {path} failed: {msg}", status)
        return result.get("data") or {}

    # ------------------------------------------------------------------
    # Session / user
    # ------------------------------------------------------------------

    def get_session_user(self) -> dict | None:
        """Return the logged-in user dict, or None when logged out."""
        try:
            data = self.request("GET", "auth/session")
        except LalalsApiError as e:
            if e.status in (401, 403):
                return None
            raise
        user = data.get("user") if isinstance(data, dict) else None
        return user if isinstance(user, dict) and user.get("id") else None

    def is_logged_in(self) -> bool:
        try:
            return self.get_session_user() is not None
        except LalalsApiError as e:
            logger.warning(f"Session check failed: {e}")
            return False

    def get_user_id(self) -> str:
        if not self._user_id:
            user = self.get_session_user()
            if not user:
                raise LalalsApiError("Not logged in to lalals.com", 401)
            self._user_id = str(user["id"])
        return self._user_id

    # ------------------------------------------------------------------
    # Projects (history)
    # ------------------------------------------------------------------

    def iter_projects(self, page_size: int = 50, include_failed: bool = True,
                      max_pages: int = 200, stop_flag=None):
        """Yield every project in the user's history, newest first.

        Pagination: the response's ``nextCursor`` (``{page, limit}``) must
        be sent back as top-level body fields — wrapping it in
        ``{"cursor": ...}`` silently returns page 1 again.
        """
        uid = self.get_user_id()
        cursor = {"page": 1, "limit": page_size}
        seen = set()
        for _ in range(max_pages):
            if stop_flag and stop_flag():
                return
            data = self.request(
                "POST", f"user/{uid}/projects",
                {**cursor, "includeFailedProjects": include_failed},
            )
            items = data.get("data") or []
            fresh = [i for i in items
                     if isinstance(i, dict) and i.get("id") not in seen]
            for item in fresh:
                seen.add(item["id"])
                yield item
            nxt = data.get("nextCursor")
            if not fresh or not data.get("hasMore") or not isinstance(nxt, dict):
                return
            cursor = nxt

    def list_projects(self, limit: int = 20, include_failed: bool = True) -> list[dict]:
        """Return the first *limit* (newest) projects."""
        uid = self.get_user_id()
        data = self.request(
            "POST", f"user/{uid}/projects",
            {"page": 1, "limit": limit, "includeFailedProjects": include_failed},
        )
        return [i for i in (data.get("data") or []) if isinstance(i, dict)]

    def get_project(self, project_id: str) -> dict:
        """Full project detail (includes ``lyrics_output``)."""
        return self.request("GET", f"projects/front/get-one-by-id/{project_id}")

    def get_projects_bulk(self, project_ids: list[str], concurrency: int = 8,
                          chunk: int = 40, progress_fn=None,
                          stop_flag=None) -> dict[str, dict]:
        """Fetch many project details, *concurrency* at a time in-page.

        Returns:
            ``{project_id: detail}`` for the ones that succeeded.
        """
        js = """
        async ({ ids, base, concurrency }) => {
            const out = {};
            let next = 0;
            const worker = async () => {
                while (next < ids.length) {
                    const id = ids[next++];
                    try {
                        const r = await fetch(
                            base + '/projects/front/get-one-by-id/' + id,
                            { credentials: 'include',
                              headers: { 'X-Lalals-Auth-Version': '2' } });
                        if (r.ok) out[id] = await r.json();
                    } catch (e) {}
                }
            };
            await Promise.all(Array.from({ length: concurrency }, worker));
            return out;
        }
        """
        self.ensure_origin()
        results: dict[str, dict] = {}
        for i in range(0, len(project_ids), chunk):
            if stop_flag and stop_flag():
                break
            batch = project_ids[i:i + chunk]
            got = self.page.evaluate(js, {
                "ids": batch, "base": API_BASE, "concurrency": concurrency,
            }) or {}
            results.update({k: v for k, v in got.items() if isinstance(v, dict)})
            if progress_fn:
                progress_fn(min(i + chunk, len(project_ids)), len(project_ids))
        return results

    # ------------------------------------------------------------------
    # Co-Producer workflow (song generation)
    # ------------------------------------------------------------------

    def create_workflow(self, context: dict) -> dict:
        return self.request("POST", "v1/workflows", {
            "workflowId": WORKFLOW_ID, "initialContext": context,
        })

    def get_workflow(self, project_id: str) -> dict:
        return self.request("GET", f"v1/workflows/{project_id}")

    def workflow_action(self, project_id: str, action: str,
                        payload: dict | None = None) -> dict:
        return self.request("POST", f"v1/workflows/{project_id}/action", {
            "action": action, "payload": payload or {},
        })

    def submit_music_ai(self, prompt: str, lyrics: str,
                        make_instrumental: bool = False,
                        title: str = "") -> dict:
        """Start a Music AI generation exactly as the Co-Producer UI does.

        Returns:
            The workflow snapshot after dispatching ``generate_music_ai``.

        Raises:
            LalalsApiError: If the workflow can't reach the generate step.
        """
        context = {
            "prompt": prompt, "lyrics": lyrics,
            "workflow_mode": "MUSIC_AI",
            "make_instrumental": make_instrumental,
            "extendDuration": 70,
        }
        if title:
            context["title"] = title

        snap = self.create_workflow(context)
        project_id = snap.get("projectId", "")
        logger.info(
            f"Workflow created: project={project_id} state={snap.get('state')} "
            f"actions={snap.get('allowedActions')}"
        )

        if snap.get("state") in ("ERROR", "PARTIAL_COMPLETED"):
            allowed = snap.get("allowedActions") or []
            retry = next((a for a in ("retry_from_lyrics", "retry") if a in allowed), None)
            if retry:
                snap = self.workflow_action(project_id, retry)

        if "generate_music_ai" not in (snap.get("allowedActions") or []):
            raise LalalsApiError(
                f"Workflow not ready to generate (state={snap.get('state')}, "
                f"actions={snap.get('allowedActions')})"
            )

        payload = {
            "prompt": prompt, "lyrics": lyrics,
            "workflow_mode": "MUSIC_AI",
            "make_instrumental": make_instrumental,
            "prompt_intensity": DEFAULT_INTENSITY,
            "lyrics_intensity": DEFAULT_INTENSITY,
            "uniqueness": DEFAULT_INTENSITY,
        }
        if title:
            payload["title"] = title
        snap = self.workflow_action(project_id, "generate_music_ai", payload)
        logger.info(f"generate_music_ai dispatched: state={snap.get('state')}")
        return snap

    def wait_for_workflow(self, project_id: str, timeout_s: int = 900,
                          poll_s: int = 10, stop_flag=None) -> dict:
        """Poll a workflow until it reaches a terminal state or times out."""
        start = time.time()
        snap = {}
        while time.time() - start < timeout_s:
            if stop_flag and stop_flag():
                break
            try:
                snap = self.get_workflow(project_id)
            except LalalsApiError as e:
                logger.warning(f"Workflow poll failed: {e}")
            if snap.get("state") in WORKFLOW_TERMINAL_STATES:
                break
            self.page.wait_for_timeout(poll_s * 1000)
        return snap

    def find_generated_projects(self, prompt: str, since: datetime,
                                limit: int = 30) -> list[dict]:
        """Find the history entries produced by a submission.

        Matches MUSIC_AI projects created at/after *since* whose queued
        prompt equals *prompt*.  Returns them sorted by version number.
        """
        since_utc = since.astimezone(timezone.utc)
        matches = []
        for item in self.list_projects(limit=limit):
            if item.get("conversionType") != "MUSIC_AI":
                continue
            try:
                added = datetime.fromisoformat(
                    str(item.get("date_added", "")).replace("Z", "+00:00")
                )
            except ValueError:
                continue
            # 60s slack for clock skew between this machine and lalals
            if (since_utc - added).total_seconds() > 60:
                continue
            ip = (item.get("queue_task") or {}).get("input_payload") or {}
            item_prompt = (ip.get("prompt") if isinstance(ip, dict) else "") or ""
            if item_prompt.strip() == prompt.strip() or not item_prompt:
                matches.append(item)
        return sorted(matches, key=version_number)

"""Auto-detecting finished/failed lalals generations and keeping old takes."""

import sqlite3
from unittest.mock import MagicMock

from automation.lalals_api import LalalsApiError


def _driver(details):
    from automation.lalals_driver import LalalsDriver
    d = LalalsDriver.__new__(LalalsDriver)
    d.api = MagicMock()
    d.api.get_project.side_effect = lambda pid: details[pid]
    return d


def test_success_when_all_finished():
    d = _driver({"a": {"conversion_status": "SUCCESS"},
                 "b": {"conversion_status": "SUCCESS"}})
    assert d.check_generation({"conversion_id_1": "a", "conversion_id_2": "b"}) \
        == ("success", "")


def test_pending_while_one_is_ongoing():
    d = _driver({"a": {"conversion_status": "SUCCESS"},
                 "b": {"conversion_status": "ONGOING"}})
    assert d.check_generation({"conversion_id_1": "a", "conversion_id_2": "b"})[0] \
        == "pending"


def test_failed_reports_lalals_reason():
    bad = {"conversion_status": "FAILED",
           "notes": "Failure info: Conversion timed out."}
    d = _driver({"a": bad, "b": bad})
    assert d.check_generation({"conversion_id_1": "a", "conversion_id_2": "b"}) \
        == ("failed", "Conversion timed out.")


def test_one_failed_one_succeeded_is_success():
    d = _driver({"a": {"conversion_status": "FAILED"},
                 "b": {"conversion_status": "SUCCESS"}})
    assert d.check_generation({"conversion_id_1": "a", "conversion_id_2": "b"})[0] \
        == "success"


def test_api_error_means_pending():
    from automation.lalals_driver import LalalsDriver
    d = LalalsDriver.__new__(LalalsDriver)
    d.api = MagicMock()
    d.api.get_project.side_effect = LalalsApiError("boom", 500)
    assert d.check_generation({"conversion_id_1": "a"})[0] == "pending"


def _db(tmp_path, **row):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("CREATE TABLE songs (id INTEGER PRIMARY KEY, status TEXT, "
                 "file_path_1 TEXT, file_path_2 TEXT, file_size_1 INT, file_size_2 INT, "
                 "task_id TEXT, conversion_id_1 TEXT, conversion_id_2 TEXT, "
                 "audio_url_1 TEXT, audio_url_2 TEXT, notes TEXT, updated_at TEXT)")
    conn.execute("INSERT INTO songs (id, status, file_path_1, conversion_id_1) "
                 "VALUES (1, 'submitted', '', 'new-take')")
    conn.commit()
    return conn


def test_failed_retry_keeps_previous_recording(tmp_path):
    from automation.browser_worker import _handle_failed_take
    old = tmp_path / "old_v1.mp3"
    old.write_bytes(b"x")
    conn = _db(tmp_path)
    previous = {"status": "completed", "file_path_1": str(old), "file_path_2": "",
                "file_size_1": 1, "file_size_2": 0, "task_id": "t0",
                "conversion_id_1": "old-take", "conversion_id_2": "old-2",
                "audio_url_1": "u1", "audio_url_2": "u2"}
    note = _handle_failed_take(conn, 1, previous, "lalals generation failed: timeout")
    status, fp1, cid1, notes = conn.execute(
        "SELECT status, file_path_1, conversion_id_1, notes FROM songs").fetchone()
    assert (status, fp1, cid1) == ("completed", str(old), "old-take")
    assert notes == note
    assert "kept the previous recording" in note


def test_failed_new_song_is_error(tmp_path):
    from automation.browser_worker import _handle_failed_take
    conn = _db(tmp_path)
    _handle_failed_take(conn, 1, {"file_path_1": ""}, "lalals generation failed: x")
    assert conn.execute("SELECT status, notes FROM songs").fetchone() == \
        ("error", "lalals generation failed: x")

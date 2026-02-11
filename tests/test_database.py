"""Tests for the Song Factory database module."""

import sqlite3
import pytest


class TestSchemaVersioning:
    """F-001: PRAGMA user_version migrations."""

    def test_fresh_db_has_current_version(self, temp_db):
        ver = temp_db._conn.execute("PRAGMA user_version").fetchone()[0]
        from database import _SCHEMA_VERSION
        assert ver == _SCHEMA_VERSION

    def test_indexes_exist(self, temp_db):
        rows = temp_db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        ).fetchall()
        names = {r[0] for r in rows}
        expected = {
            "idx_songs_status",
            "idx_songs_genre_id",
            "idx_songs_created_at",
            "idx_songs_task_id",
            "idx_lore_category",
            "idx_lore_active",
            "idx_distributions_status",
            "idx_distributions_song_id",
            "idx_cd_tracks_project_id",
        }
        assert expected.issubset(names)

    def test_fk_check_clean(self, temp_db):
        issues = temp_db._conn.execute("PRAGMA foreign_key_check").fetchall()
        assert len(issues) == 0


class TestForeignKeyBehavior:
    """F-003: FK cascade and SET NULL."""

    def test_delete_genre_sets_song_genre_null(self, temp_db):
        gid = temp_db.add_genre("TestGenre", "template")
        sid = temp_db.add_song("Song", gid, "TEST", "prompt", "lyrics")
        temp_db.delete_genre(gid)
        song = temp_db.get_song(sid)
        assert song["genre_id"] is None

    def test_delete_song_cascades_to_distributions(self, temp_db):
        gid = temp_db.add_genre("G", "t")
        sid = temp_db.add_song("S", gid, "G", "p", "l")
        did = temp_db.add_distribution(sid, "Writer")
        temp_db.delete_song(sid)
        assert temp_db.get_distribution(did) is None


class TestLoreCRUD:
    def test_add_and_get_lore(self, temp_db):
        lid = temp_db.add_lore("Title", "Content", "places")
        lore = temp_db.get_lore(lid)
        assert lore is not None
        assert lore["title"] == "Title"
        assert lore["category"] == "places"

    def test_update_lore(self, temp_db):
        lid = temp_db.add_lore("Old", "Content")
        temp_db.update_lore(lid, title="New")
        assert temp_db.get_lore(lid)["title"] == "New"

    def test_delete_lore(self, temp_db):
        lid = temp_db.add_lore("Del", "Content")
        assert temp_db.delete_lore(lid)
        assert temp_db.get_lore(lid) is None

    def test_toggle_lore_active(self, temp_db):
        lid = temp_db.add_lore("T", "C", active=True)
        temp_db.toggle_lore_active(lid)
        assert temp_db.get_lore(lid)["active"] == 0
        temp_db.toggle_lore_active(lid)
        assert temp_db.get_lore(lid)["active"] == 1

    def test_bulk_active(self, temp_db):
        ids = [temp_db.add_lore(f"L{i}", "C") for i in range(3)]
        temp_db.set_all_lore_active(False)
        for lid in ids:
            assert temp_db.get_lore(lid)["active"] == 0
        temp_db.set_lore_active_bulk(ids[:2], True)
        assert temp_db.get_lore(ids[0])["active"] == 1
        assert temp_db.get_lore(ids[2])["active"] == 0

    def test_get_active_lore(self, temp_db):
        temp_db.add_lore("Active", "C", active=True)
        temp_db.add_lore("Inactive", "C", active=False)
        active = temp_db.get_active_lore()
        assert all(l["active"] for l in active)


class TestGenreCRUD:
    def test_add_and_get_genre(self, temp_db):
        gid = temp_db.add_genre("Jazz", "smooth jazz", "desc", "100-120")
        genre = temp_db.get_genre(gid)
        assert genre["name"] == "Jazz"
        assert genre["bpm_range"] == "100-120"

    def test_unique_genre_name(self, temp_db):
        temp_db.add_genre("Unique", "t")
        with pytest.raises(sqlite3.IntegrityError):
            temp_db.add_genre("Unique", "t2")

    def test_update_genre(self, temp_db):
        gid = temp_db.add_genre("Old", "t")
        temp_db.update_genre(gid, name="New")
        assert temp_db.get_genre(gid)["name"] == "New"

    def test_delete_genre(self, temp_db):
        gid = temp_db.add_genre("Del", "t")
        assert temp_db.delete_genre(gid)
        assert temp_db.get_genre(gid) is None

    def test_toggle_genre_active(self, temp_db):
        gid = temp_db.add_genre("Tog", "t")
        temp_db.toggle_genre_active(gid)
        assert temp_db.get_genre(gid)["active"] == 0


class TestSongCRUD:
    def test_add_and_get_song(self, temp_db):
        gid = temp_db.add_genre("Pop", "pop")
        sid = temp_db.add_song("Song", gid, "POP", "prompt", "lyrics")
        song = temp_db.get_song(sid)
        assert song["title"] == "Song"
        assert song["status"] == "draft"

    def test_update_song_metadata(self, temp_db):
        gid = temp_db.add_genre("Rock", "rock")
        sid = temp_db.add_song("S", gid, "ROCK", "p", "l")
        temp_db.update_song(sid, task_id="abc-123", status="completed")
        song = temp_db.get_song(sid)
        assert song["task_id"] == "abc-123"
        assert song["status"] == "completed"

    def test_search_songs(self, temp_db):
        gid = temp_db.add_genre("G", "t")
        temp_db.add_song("Treasure Hunt", gid, "G", "find gold", "lyrics about gold")
        results = temp_db.search_songs("Treasure")
        assert len(results) == 1
        results = temp_db.search_songs("gold")
        assert len(results) == 1

    def test_get_songs_by_status(self, temp_db):
        gid = temp_db.add_genre("G", "t")
        temp_db.add_song("Draft", gid, "G", "p", "l", status="draft")
        temp_db.add_song("Done", gid, "G", "p", "l", status="completed")
        drafts = temp_db.get_songs_by_status("draft")
        assert all(s["status"] == "draft" for s in drafts)

    def test_delete_song(self, temp_db):
        gid = temp_db.add_genre("G", "t")
        sid = temp_db.add_song("Del", gid, "G", "p", "l")
        assert temp_db.delete_song(sid)
        assert temp_db.get_song(sid) is None

    def test_song_count(self, temp_db):
        assert temp_db.get_song_count() == 0
        gid = temp_db.add_genre("G", "t")
        temp_db.add_song("A", gid, "G", "p", "l")
        temp_db.add_song("B", gid, "G", "p", "l")
        assert temp_db.get_song_count() == 2


class TestConfigCRUD:
    def test_set_and_get_config(self, temp_db):
        temp_db.set_config("key1", "value1")
        assert temp_db.get_config("key1") == "value1"

    def test_get_config_default(self, temp_db):
        assert temp_db.get_config("nonexistent") is None
        assert temp_db.get_config("nonexistent", "fallback") == "fallback"

    def test_upsert_config(self, temp_db):
        temp_db.set_config("k", "v1")
        temp_db.set_config("k", "v2")
        assert temp_db.get_config("k") == "v2"

    def test_get_all_config(self, temp_db):
        temp_db.set_config("a", "1")
        temp_db.set_config("b", "2")
        cfg = temp_db.get_all_config()
        assert cfg["a"] == "1"
        assert cfg["b"] == "2"


class TestCDProjectCRUD:
    def test_add_and_get_project(self, temp_db):
        pid = temp_db.add_cd_project("Album1", artist="Yakima Finds")
        proj = temp_db.get_cd_project(pid)
        assert proj["name"] == "Album1"
        assert proj["artist"] == "Yakima Finds"

    def test_update_project(self, temp_db):
        pid = temp_db.add_cd_project("P")
        temp_db.update_cd_project(pid, status="ready")
        assert temp_db.get_cd_project(pid)["status"] == "ready"

    def test_delete_project_cascades_tracks(self, temp_db):
        pid = temp_db.add_cd_project("P")
        tid = temp_db.add_cd_track(pid, 1, "Track1", "/fake.mp3")
        temp_db.delete_cd_project(pid)
        # cd_tracks has ON DELETE CASCADE
        tracks = temp_db.get_cd_tracks(pid)
        assert len(tracks) == 0


class TestCDTrackCRUD:
    def test_add_and_get_tracks(self, temp_db):
        pid = temp_db.add_cd_project("P")
        temp_db.add_cd_track(pid, 1, "T1", "/a.mp3")
        temp_db.add_cd_track(pid, 2, "T2", "/b.mp3")
        tracks = temp_db.get_cd_tracks(pid)
        assert len(tracks) == 2
        assert tracks[0]["track_number"] == 1

    def test_reorder_tracks(self, temp_db):
        pid = temp_db.add_cd_project("P")
        t1 = temp_db.add_cd_track(pid, 1, "First", "/a.mp3")
        t2 = temp_db.add_cd_track(pid, 2, "Second", "/b.mp3")
        temp_db.reorder_cd_tracks(pid, [t2, t1])
        tracks = temp_db.get_cd_tracks(pid)
        assert tracks[0]["title"] == "Second"
        assert tracks[1]["title"] == "First"


class TestDistributionCRUD:
    def test_add_and_get_distribution(self, temp_db):
        gid = temp_db.add_genre("G", "t")
        sid = temp_db.add_song("S", gid, "G", "p", "l")
        did = temp_db.add_distribution(sid, "Writer Name", status="draft")
        dist = temp_db.get_distribution(did)
        assert dist["songwriter"] == "Writer Name"

    def test_get_distributions_for_song(self, temp_db):
        gid = temp_db.add_genre("G", "t")
        sid = temp_db.add_song("S", gid, "G", "p", "l")
        temp_db.add_distribution(sid, "W")
        dists = temp_db.get_distributions_for_song(sid)
        assert len(dists) == 1

    def test_update_distribution(self, temp_db):
        gid = temp_db.add_genre("G", "t")
        sid = temp_db.add_song("S", gid, "G", "p", "l")
        did = temp_db.add_distribution(sid, "W")
        temp_db.update_distribution(did, status="live")
        assert temp_db.get_distribution(did)["status"] == "live"


class TestLorePresets:
    def test_add_and_get_preset(self, temp_db):
        l1 = temp_db.add_lore("A", "C")
        l2 = temp_db.add_lore("B", "C")
        pid = temp_db.add_lore_preset("Preset1", [l1, l2])
        presets = temp_db.get_all_lore_presets()
        assert len(presets) == 1
        assert presets[0]["lore_ids"] == [l1, l2]

    def test_apply_preset(self, temp_db):
        l1 = temp_db.add_lore("A", "C", active=True)
        l2 = temp_db.add_lore("B", "C", active=True)
        l3 = temp_db.add_lore("C", "C", active=True)
        pid = temp_db.add_lore_preset("P", [l1, l3])
        temp_db.apply_lore_preset(pid)
        assert temp_db.get_lore(l1)["active"] == 1
        assert temp_db.get_lore(l2)["active"] == 0
        assert temp_db.get_lore(l3)["active"] == 1


class TestBackupRestore:
    def test_backup_and_restore(self, temp_db, tmp_path):
        gid = temp_db.add_genre("G", "t")
        sid = temp_db.add_song("Original", gid, "G", "p", "l")
        backup_path = temp_db.backup_to(str(tmp_path / "backups"))

        # Modify data
        temp_db.update_song(sid, title="Modified")

        # Restore
        temp_db.restore_from(backup_path)
        song = temp_db.get_song(sid)
        assert song["title"] == "Original"

    def test_detect_backups(self, temp_db, tmp_path):
        backup_dir = str(tmp_path / "backups")
        temp_db.backup_to(backup_dir)
        backups = temp_db.detect_backups(backup_dir)
        assert len(backups) == 1
        assert "songfactory_backup_" in backups[0]["filename"]


class TestDbPathOverride:
    def test_custom_db_path(self, tmp_path):
        from database import Database
        custom_path = str(tmp_path / "subdir" / "custom.db")
        db = Database(db_path=custom_path)
        assert db._db_path == custom_path
        db.add_genre("Test", "template")
        assert len(db.get_all_genres()) == 1
        db.close()

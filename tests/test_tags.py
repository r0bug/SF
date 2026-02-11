"""Tests for the Song Factory tags feature (schema v5)."""

import sqlite3
import pytest


class TestTagsSchemaV5:
    """Schema v5 migration creates tables, seeds defaults, and adds indexes."""

    def test_schema_version_is_5(self, temp_db):
        from database import _SCHEMA_VERSION
        ver = temp_db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert ver == _SCHEMA_VERSION
        assert _SCHEMA_VERSION == 5

    def test_tags_table_exists(self, temp_db):
        rows = temp_db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tags'"
        ).fetchall()
        assert len(rows) == 1

    def test_song_tags_table_exists(self, temp_db):
        rows = temp_db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='song_tags'"
        ).fetchall()
        assert len(rows) == 1

    def test_default_tags_seeded(self, temp_db):
        tags = temp_db.get_all_tags()
        assert len(tags) == 6
        names = {t["name"] for t in tags}
        assert "Favorite" in names
        assert "Released" in names
        assert "Needs Lyrics" in names
        assert "Halloween" in names
        assert "Love Song" in names
        assert "Instrumental" in names

    def test_default_tags_are_builtin(self, temp_db):
        tags = temp_db.get_all_tags()
        for tag in tags:
            assert tag["is_builtin"] == 1

    def test_default_tag_colors(self, temp_db):
        tags = temp_db.get_all_tags()
        color_map = {t["name"]: t["color"] for t in tags}
        assert color_map["Favorite"] == "#FFD700"
        assert color_map["Released"] == "#4CAF50"

    def test_song_tags_indexes_exist(self, temp_db):
        rows = temp_db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_song_tags%'"
        ).fetchall()
        names = {r[0] for r in rows}
        assert "idx_song_tags_song_id" in names
        assert "idx_song_tags_tag_id" in names


class TestTagCRUD:
    """Tag CRUD operations."""

    def test_add_tag(self, temp_db):
        tag_id = temp_db.add_tag("Custom Tag", "#FF0000")
        assert tag_id is not None
        tags = temp_db.get_all_tags()
        names = {t["name"] for t in tags}
        assert "Custom Tag" in names

    def test_add_tag_unique_constraint(self, temp_db):
        temp_db.add_tag("Unique Tag", "#FF0000")
        with pytest.raises(sqlite3.IntegrityError):
            temp_db.add_tag("Unique Tag", "#00FF00")

    def test_update_tag_name(self, temp_db):
        tag_id = temp_db.add_tag("Old Name", "#FF0000")
        result = temp_db.update_tag(tag_id, name="New Name")
        assert result is True
        tags = temp_db.get_all_tags()
        tag = next(t for t in tags if t["id"] == tag_id)
        assert tag["name"] == "New Name"

    def test_update_tag_color(self, temp_db):
        tag_id = temp_db.add_tag("Color Test", "#FF0000")
        temp_db.update_tag(tag_id, color="#00FF00")
        tags = temp_db.get_all_tags()
        tag = next(t for t in tags if t["id"] == tag_id)
        assert tag["color"] == "#00FF00"

    def test_delete_custom_tag(self, temp_db):
        tag_id = temp_db.add_tag("Deletable", "#FF0000")
        result = temp_db.delete_tag(tag_id)
        assert result is True
        tags = temp_db.get_all_tags()
        ids = {t["id"] for t in tags}
        assert tag_id not in ids

    def test_delete_builtin_tag_blocked(self, temp_db):
        tags = temp_db.get_all_tags()
        builtin = next(t for t in tags if t["is_builtin"])
        result = temp_db.delete_tag(builtin["id"])
        assert result is False
        # Tag should still exist
        tags_after = temp_db.get_all_tags()
        ids = {t["id"] for t in tags_after}
        assert builtin["id"] in ids

    def test_delete_nonexistent_tag(self, temp_db):
        result = temp_db.delete_tag(99999)
        assert result is False

    def test_update_empty_kwargs(self, temp_db):
        tag_id = temp_db.add_tag("No Change", "#FF0000")
        result = temp_db.update_tag(tag_id)
        assert result is False

    def test_add_tag_default_not_builtin(self, temp_db):
        tag_id = temp_db.add_tag("User Tag", "#AABBCC")
        tags = temp_db.get_all_tags()
        tag = next(t for t in tags if t["id"] == tag_id)
        assert tag["is_builtin"] == 0


class TestSongTagAssociations:
    """Song ↔ Tag association operations."""

    _genre_counter = 0

    def _make_song(self, db):
        TestSongTagAssociations._genre_counter += 1
        name = f"Test Genre {TestSongTagAssociations._genre_counter}"
        gid = db.add_genre(name, "template")
        return db.add_song("Test Song", gid, name, "prompt", "lyrics")

    def test_add_tag_to_song(self, temp_db):
        song_id = self._make_song(temp_db)
        tag_id = temp_db.add_tag("My Tag", "#FF0000")
        result = temp_db.add_tag_to_song(song_id, tag_id)
        assert result is True

    def test_get_tags_for_song(self, temp_db):
        song_id = self._make_song(temp_db)
        tag1 = temp_db.add_tag("Tag A", "#FF0000")
        tag2 = temp_db.add_tag("Tag B", "#00FF00")
        temp_db.add_tag_to_song(song_id, tag1)
        temp_db.add_tag_to_song(song_id, tag2)
        tags = temp_db.get_tags_for_song(song_id)
        assert len(tags) == 2
        names = {t["name"] for t in tags}
        assert names == {"Tag A", "Tag B"}

    def test_remove_tag_from_song(self, temp_db):
        song_id = self._make_song(temp_db)
        tag_id = temp_db.add_tag("Remove Me", "#FF0000")
        temp_db.add_tag_to_song(song_id, tag_id)
        result = temp_db.remove_tag_from_song(song_id, tag_id)
        assert result is True
        tags = temp_db.get_tags_for_song(song_id)
        assert len(tags) == 0

    def test_get_songs_by_tag(self, temp_db):
        s1 = self._make_song(temp_db)
        s2 = self._make_song(temp_db)
        tag_id = temp_db.add_tag("Shared Tag", "#FF0000")
        temp_db.add_tag_to_song(s1, tag_id)
        temp_db.add_tag_to_song(s2, tag_id)
        songs = temp_db.get_songs_by_tag(tag_id)
        assert len(songs) == 2
        song_ids = {s["id"] for s in songs}
        assert s1 in song_ids
        assert s2 in song_ids

    def test_set_song_tags(self, temp_db):
        song_id = self._make_song(temp_db)
        t1 = temp_db.add_tag("Set A", "#FF0000")
        t2 = temp_db.add_tag("Set B", "#00FF00")
        t3 = temp_db.add_tag("Set C", "#0000FF")
        temp_db.add_tag_to_song(song_id, t1)
        # Replace all with t2 and t3
        temp_db.set_song_tags(song_id, [t2, t3])
        tags = temp_db.get_tags_for_song(song_id)
        tag_ids = {t["id"] for t in tags}
        assert t1 not in tag_ids
        assert t2 in tag_ids
        assert t3 in tag_ids

    def test_duplicate_tag_assignment_ignored(self, temp_db):
        song_id = self._make_song(temp_db)
        tag_id = temp_db.add_tag("Dup Tag", "#FF0000")
        temp_db.add_tag_to_song(song_id, tag_id)
        # Second assignment should be ignored (INSERT OR IGNORE)
        result = temp_db.add_tag_to_song(song_id, tag_id)
        assert result is False
        tags = temp_db.get_tags_for_song(song_id)
        assert len(tags) == 1


class TestTagCascades:
    """Cascade behavior when deleting songs or tags."""

    def _make_song(self, db):
        gid = db.add_genre("Cascade Genre", "template")
        return db.add_song("Cascade Song", gid, "Cascade Genre", "prompt", "lyrics")

    def test_delete_song_removes_song_tags(self, temp_db):
        song_id = self._make_song(temp_db)
        tag_id = temp_db.add_tag("Cascade Tag", "#FF0000")
        temp_db.add_tag_to_song(song_id, tag_id)
        temp_db.delete_song(song_id)
        # song_tags row should be gone
        rows = temp_db._conn.execute(
            "SELECT * FROM song_tags WHERE song_id = ?", (song_id,)
        ).fetchall()
        assert len(rows) == 0

    def test_delete_tag_removes_song_tags(self, temp_db):
        song_id = self._make_song(temp_db)
        tag_id = temp_db.add_tag("Delete Tag Cascade", "#FF0000")
        temp_db.add_tag_to_song(song_id, tag_id)
        temp_db.delete_tag(tag_id)
        tags = temp_db.get_tags_for_song(song_id)
        assert len(tags) == 0

    def test_delete_song_doesnt_affect_tag(self, temp_db):
        song_id = self._make_song(temp_db)
        tag_id = temp_db.add_tag("Survive Tag", "#FF0000")
        temp_db.add_tag_to_song(song_id, tag_id)
        temp_db.delete_song(song_id)
        # Tag itself should still exist
        tags = temp_db.get_all_tags()
        tag_ids = {t["id"] for t in tags}
        assert tag_id in tag_ids

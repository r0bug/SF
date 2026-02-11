"""Tests for export/import functionality."""

import json
import os
import pytest


def test_export_json_all(seeded_db, tmp_path):
    from export_import import export_json
    path = str(tmp_path / "export.json")
    result = export_json(seeded_db, path)
    assert os.path.exists(result)

    with open(result, "r") as f:
        data = json.load(f)
    assert data["version"] == 1
    assert "songs" in data
    assert "lore" in data
    assert "genres" in data
    assert len(data["genres"]) > 0


def test_export_json_songs_only(seeded_db, tmp_path):
    from export_import import export_json
    path = str(tmp_path / "songs.json")
    export_json(seeded_db, path, songs=True, lore=False, genres=False)

    with open(path, "r") as f:
        data = json.load(f)
    assert "songs" in data
    assert "lore" not in data
    assert "genres" not in data


def test_export_json_specific_ids(seeded_db, tmp_path):
    from export_import import export_json
    songs = seeded_db.get_all_songs()
    if not songs:
        pytest.skip("No songs in seeded DB")
    first_id = songs[0]["id"]

    path = str(tmp_path / "one.json")
    export_json(seeded_db, path, song_ids=[first_id], lore=False, genres=False)

    with open(path, "r") as f:
        data = json.load(f)
    assert len(data["songs"]) == 1


def test_export_csv(seeded_db, tmp_path):
    from export_import import export_songs_csv
    songs = seeded_db.get_all_songs()
    if not songs:
        pytest.skip("No songs in seeded DB")

    path = str(tmp_path / "songs.csv")
    result = export_songs_csv(seeded_db, path)
    assert os.path.exists(result)
    # Should have header + data lines
    with open(result) as f:
        lines = f.readlines()
    assert len(lines) >= 2


def test_import_json_roundtrip(seeded_db, tmp_path):
    """Export from seeded DB, import into a fresh empty DB."""
    from database import Database
    from export_import import export_json, import_json

    path = str(tmp_path / "roundtrip.json")
    export_json(seeded_db, path)

    # Create a separate empty database for import target
    import_db = Database(db_path=str(tmp_path / "import_target.db"))
    try:
        report = import_json(import_db, path)
        assert report["genres_created"] > 0
        assert report["genres_skipped"] == 0
        assert report["songs_created"] > 0
    finally:
        import_db.close()


def test_import_json_duplicate_detection(seeded_db, tmp_path):
    """Importing into same DB should skip duplicates."""
    from export_import import export_json, import_json

    path = str(tmp_path / "dup.json")
    export_json(seeded_db, path)

    report = import_json(seeded_db, path)
    # Everything should be skipped since it already exists
    assert report["genres_created"] == 0
    assert report["genres_skipped"] > 0
    assert report["songs_created"] == 0
    assert report["songs_skipped"] > 0


def test_preview_import(seeded_db, tmp_path):
    from export_import import export_json, preview_import

    path = str(tmp_path / "preview.json")
    export_json(seeded_db, path)

    preview = preview_import(path)
    assert preview["version"] == 1
    assert preview["song_count"] > 0
    assert preview["genre_count"] > 0

"""Tests for personal bundle export/import functionality.

Verifies:
- Bundle JSON structure and version
- Sensitive keys exclusion
- Import creates new entries
- Import upserts existing entries
- Preset lore title resolution
- Preview without side effects
- Round-trip consistency
"""

import json
import os
import sys

import pytest

# Ensure the songfactory package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def bundle_db(tmp_path):
    """Provide a fresh Database with some test data."""
    from database import Database

    db = Database(db_path=str(tmp_path / "bundle_test.db"))

    # Add genres
    db.add_genre(name="Rock", prompt_template="rock template", description="Rock music", bpm_range="120-140")
    db.add_genre(name="Jazz", prompt_template="jazz template", description="Jazz music", bpm_range="80-120")

    # Add lore
    db.add_lore(title="Origin Story", content="The beginning of Yakima", category="events", active=True)
    db.add_lore(title="The Mountain", content="A sacred place", category="places", active=True)
    db.add_lore(title="Elder Wisdom", content="Ancient knowledge", category="people", active=False)

    # Add a preset (using the lore IDs)
    all_lore = db.get_all_lore()
    active_ids = [e["id"] for e in all_lore if e["active"]]
    db.add_lore_preset("Active Set", active_ids)

    # "Yakima Finds" artist is already created by the v4 migration,
    # so we just add a second artist for testing
    db.add_artist(name="Side Project", is_default=False)

    # Add some config
    db.set_config("ai_model", "claude-sonnet-4-5-20250929")
    db.set_config("max_prompt_length", "300")
    db.set_config("browser_path", "/usr/bin/chromium")

    yield db
    db.close()


class TestExportPersonalBundle:
    """Tests for export_personal_bundle."""

    def test_export_structure(self, bundle_db, tmp_path):
        """Exported JSON has correct structure and metadata."""
        from export_import import export_personal_bundle

        path = str(tmp_path / "bundle.json")
        result = export_personal_bundle(bundle_db, path)
        assert os.path.exists(result)

        with open(result) as f:
            data = json.load(f)

        assert data["bundle_version"] == 1
        assert data["app"] == "Song Factory"
        assert "exported_at" in data
        assert "lore" in data
        assert "genres" in data
        assert "presets" in data
        assert "artists" in data
        assert "config" in data

        # Verify counts
        assert len(data["lore"]) == 3
        assert len(data["genres"]) == 2
        assert len(data["presets"]) == 1
        assert len(data["artists"]) == 2

    def test_export_excludes_sensitive_keys(self, bundle_db, tmp_path):
        """Sensitive keys (API keys, passwords) are never exported."""
        from export_import import export_personal_bundle
        from secure_config import SENSITIVE_KEYS

        # Store some sensitive values
        bundle_db.set_config("api_key", "sk-ant-secret-key")
        bundle_db.set_config("lalals_password", "supersecret")

        path = str(tmp_path / "bundle.json")
        export_personal_bundle(bundle_db, path)

        with open(path) as f:
            data = json.load(f)

        config = data.get("config", {})
        for key in SENSITIVE_KEYS:
            assert key not in config, f"Sensitive key '{key}' found in export"

    def test_export_lore_only(self, bundle_db, tmp_path):
        """lore_only=True exports only lore, no genres/presets/etc."""
        from export_import import export_personal_bundle

        path = str(tmp_path / "lore_only.json")
        export_personal_bundle(bundle_db, path, lore_only=True)

        with open(path) as f:
            data = json.load(f)

        assert "lore" in data
        assert len(data["lore"]) == 3
        assert "genres" not in data
        assert "presets" not in data
        assert "artists" not in data
        assert "config" not in data

    def test_export_no_internal_ids(self, bundle_db, tmp_path):
        """Exported entries do not contain internal database IDs."""
        from export_import import export_personal_bundle

        path = str(tmp_path / "bundle.json")
        export_personal_bundle(bundle_db, path)

        with open(path) as f:
            data = json.load(f)

        for lore in data["lore"]:
            assert "id" not in lore
        for genre in data["genres"]:
            assert "id" not in genre
        for artist in data["artists"]:
            assert "id" not in artist

    def test_preset_lore_titles(self, bundle_db, tmp_path):
        """Presets resolve lore IDs to titles for portability."""
        from export_import import export_personal_bundle

        path = str(tmp_path / "bundle.json")
        export_personal_bundle(bundle_db, path)

        with open(path) as f:
            data = json.load(f)

        preset = data["presets"][0]
        assert preset["name"] == "Active Set"
        assert "lore_titles" in preset
        assert "lore_ids" not in preset
        # Our active lore is "Origin Story" and "The Mountain"
        assert set(preset["lore_titles"]) == {"Origin Story", "The Mountain"}


class TestImportPersonalBundle:
    """Tests for import_personal_bundle."""

    def test_import_creates_new_entries(self, bundle_db, tmp_path):
        """Import into an empty DB creates all entries."""
        from database import Database
        from export_import import export_personal_bundle, import_personal_bundle

        # Export from populated DB
        path = str(tmp_path / "bundle.json")
        export_personal_bundle(bundle_db, path)

        # Import into empty DB
        empty_db = Database(db_path=str(tmp_path / "empty.db"))
        try:
            report = import_personal_bundle(empty_db, path)

            assert report["genres_created"] == 2
            assert report["genres_updated"] == 0
            assert report["lore_created"] == 3
            assert report["lore_updated"] == 0
            assert report["presets_created"] == 1
            assert report["presets_updated"] == 0
            # "Yakima Finds" already exists from migration, "Side Project" is new
            assert report["artists_created"] == 1
            assert report["artists_updated"] == 1
            assert report["config_updated"] >= 2  # at least ai_model, max_prompt_length

            # Verify data actually exists
            assert len(empty_db.get_all_genres()) == 2
            assert len(empty_db.get_all_lore()) == 3
            assert len(empty_db.get_all_lore_presets()) == 1
            assert len(empty_db.get_all_artists()) == 2
        finally:
            empty_db.close()

    def test_import_upserts_existing(self, bundle_db, tmp_path):
        """Import with matching names updates content instead of creating duplicates."""
        from export_import import export_personal_bundle, import_personal_bundle

        path = str(tmp_path / "bundle.json")
        export_personal_bundle(bundle_db, path)

        # Modify the exported data to have different content
        with open(path) as f:
            data = json.load(f)

        # Find the specific entries by name (order may vary)
        for entry in data["lore"]:
            if entry["title"] == "Origin Story":
                entry["content"] = "UPDATED content for origin story"
        for entry in data["genres"]:
            if entry["name"] == "Rock":
                entry["description"] = "UPDATED rock description"

        with open(path, "w") as f:
            json.dump(data, f)

        # Import back into the same DB
        report = import_personal_bundle(bundle_db, path)

        assert report["lore_created"] == 0
        assert report["lore_updated"] == 3  # all 3 lore entries updated
        assert report["genres_created"] == 0
        assert report["genres_updated"] == 2  # both genres updated

        # Verify the content was actually updated
        all_lore = bundle_db.get_all_lore()
        origin = next(e for e in all_lore if e["title"] == "Origin Story")
        assert origin["content"] == "UPDATED content for origin story"

        all_genres = bundle_db.get_all_genres()
        rock = next(g for g in all_genres if g["name"] == "Rock")
        assert rock["description"] == "UPDATED rock description"

    def test_import_resolves_preset_lore_titles(self, tmp_path):
        """Preset lore_titles are mapped back to IDs in the target database."""
        from database import Database
        from export_import import import_personal_bundle

        # Create a bundle with a preset that references lore by title
        bundle = {
            "bundle_version": 1,
            "exported_at": "2026-01-01T00:00:00",
            "app": "Song Factory",
            "lore": [
                {"title": "Alpha Lore", "content": "A", "category": "general", "active": True},
                {"title": "Beta Lore", "content": "B", "category": "general", "active": True},
            ],
            "genres": [],
            "presets": [
                {"name": "Test Preset", "lore_titles": ["Alpha Lore", "Beta Lore"]},
            ],
            "artists": [],
            "config": {},
        }

        path = str(tmp_path / "preset_bundle.json")
        with open(path, "w") as f:
            json.dump(bundle, f)

        db = Database(db_path=str(tmp_path / "preset_test.db"))
        try:
            report = import_personal_bundle(db, path)

            assert report["lore_created"] == 2
            assert report["presets_created"] == 1

            # Verify preset has correct lore IDs
            presets = db.get_all_lore_presets()
            assert len(presets) == 1

            lore_map = {e["title"]: e["id"] for e in db.get_all_lore()}
            expected_ids = {lore_map["Alpha Lore"], lore_map["Beta Lore"]}
            actual_ids = set(presets[0]["lore_ids"])
            assert actual_ids == expected_ids
        finally:
            db.close()

    def test_import_skips_sensitive_config(self, tmp_path):
        """Even if sensitive keys appear in a bundle, they are skipped."""
        from database import Database
        from export_import import import_personal_bundle

        bundle = {
            "bundle_version": 1,
            "exported_at": "2026-01-01T00:00:00",
            "app": "Song Factory",
            "lore": [],
            "genres": [],
            "presets": [],
            "artists": [],
            "config": {
                "ai_model": "claude-opus-4-6",
                "api_key": "SHOULD_BE_SKIPPED",
                "lalals_password": "SHOULD_BE_SKIPPED",
            },
        }

        path = str(tmp_path / "sneaky.json")
        with open(path, "w") as f:
            json.dump(bundle, f)

        db = Database(db_path=str(tmp_path / "secure_test.db"))
        try:
            report = import_personal_bundle(db, path)

            # ai_model should be imported
            assert db.get_config("ai_model") == "claude-opus-4-6"

            # Sensitive keys should NOT have been set
            assert db.get_config("api_key") is None
            assert db.get_config("lalals_password") is None
        finally:
            db.close()


class TestPreviewPersonalBundle:
    """Tests for preview_personal_bundle."""

    def test_preview_returns_counts(self, bundle_db, tmp_path):
        """Preview returns counts and metadata without importing."""
        from export_import import export_personal_bundle, preview_personal_bundle

        path = str(tmp_path / "bundle.json")
        export_personal_bundle(bundle_db, path)

        preview = preview_personal_bundle(path)
        assert preview["bundle_version"] == 1
        assert preview["lore_count"] == 3
        assert preview["genre_count"] == 2
        assert preview["preset_count"] == 1
        assert preview["artist_count"] == 2
        assert "exported_at" in preview
        assert isinstance(preview["config_keys"], list)

    def test_preview_has_no_side_effects(self, bundle_db, tmp_path):
        """Preview does not modify the database."""
        from database import Database
        from export_import import export_personal_bundle, preview_personal_bundle

        path = str(tmp_path / "bundle.json")
        export_personal_bundle(bundle_db, path)

        empty_db = Database(db_path=str(tmp_path / "pristine.db"))
        try:
            # Get initial state
            initial_lore = len(empty_db.get_all_lore())
            initial_genres = len(empty_db.get_all_genres())

            # Preview should NOT change anything
            preview_personal_bundle(path)

            assert len(empty_db.get_all_lore()) == initial_lore
            assert len(empty_db.get_all_genres()) == initial_genres
        finally:
            empty_db.close()


class TestRoundTrip:
    """Test full export-then-import cycle."""

    def test_round_trip_produces_identical_data(self, bundle_db, tmp_path):
        """Export then import into a fresh DB produces equivalent data."""
        from database import Database
        from export_import import export_personal_bundle, import_personal_bundle

        # Export
        path = str(tmp_path / "roundtrip.json")
        export_personal_bundle(bundle_db, path)

        # Import into fresh DB
        target_db = Database(db_path=str(tmp_path / "target.db"))
        try:
            import_personal_bundle(target_db, path)

            # Compare lore
            orig_lore = sorted(
                [(e["title"], e["content"], e["category"]) for e in bundle_db.get_all_lore()]
            )
            target_lore = sorted(
                [(e["title"], e["content"], e["category"]) for e in target_db.get_all_lore()]
            )
            assert orig_lore == target_lore

            # Compare genres
            orig_genres = sorted(
                [(g["name"], g["prompt_template"], g["description"]) for g in bundle_db.get_all_genres()]
            )
            target_genres = sorted(
                [(g["name"], g["prompt_template"], g["description"]) for g in target_db.get_all_genres()]
            )
            assert orig_genres == target_genres

            # Compare presets by name and lore title mapping
            orig_presets = bundle_db.get_all_lore_presets()
            target_presets = target_db.get_all_lore_presets()
            assert len(orig_presets) == len(target_presets)
            assert orig_presets[0]["name"] == target_presets[0]["name"]

            # Compare artists
            orig_artists = sorted(
                [(a["name"], bool(a["is_default"])) for a in bundle_db.get_all_artists()]
            )
            target_artists = sorted(
                [(a["name"], bool(a["is_default"])) for a in target_db.get_all_artists()]
            )
            assert orig_artists == target_artists

            # Compare config
            assert target_db.get_config("ai_model") == bundle_db.get_config("ai_model")
            assert target_db.get_config("max_prompt_length") == bundle_db.get_config("max_prompt_length")
        finally:
            target_db.close()

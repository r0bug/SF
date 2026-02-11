"""
Song Factory Test Fixtures

Shared pytest fixtures for database, Qt application, and sample data.
"""

import os
import sys
import pytest

# Ensure the songfactory package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "songfactory"))

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qt_app():
    """Create a single QApplication instance for the entire test session."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def temp_db(tmp_path):
    """Provide a fresh Database instance backed by a temporary file."""
    from database import Database

    db = Database(db_path=str(tmp_path / "test.db"))
    yield db
    db.close()


@pytest.fixture
def seeded_db(temp_db):
    """Provide a Database pre-populated with seed genres, lore, and songs."""
    from seed_data import SEED_GENRES, SEED_LORE, SEED_SONGS

    for genre in SEED_GENRES:
        temp_db.add_genre(
            name=genre["name"],
            prompt_template=genre["prompt_template"],
            description=genre.get("description", ""),
            bpm_range=genre.get("bpm_range", ""),
            active=genre.get("active", True),
        )
    for lore in SEED_LORE:
        temp_db.add_lore(
            title=lore["title"],
            content=lore["content"],
            category=lore.get("category", "general"),
            active=lore.get("active", True),
        )
    genres = temp_db.get_all_genres()
    genre_map = {}
    for g in genres:
        genre_map[g["name"].upper()] = g["id"]

    for song in SEED_SONGS:
        genre_id = None
        label = song.get("genre_label", "")
        for gname, gid in genre_map.items():
            if gname in label.upper():
                genre_id = gid
                break
        temp_db.add_song(
            title=song["title"],
            genre_id=genre_id,
            genre_label=song.get("genre_label", ""),
            prompt=song.get("prompt", ""),
            lyrics=song.get("lyrics", ""),
            status=song.get("status", "completed"),
        )
    yield temp_db

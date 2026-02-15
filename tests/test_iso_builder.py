"""Tests for the ISO builder worker."""

import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from PyQt6.QtCore import QCoreApplication

from automation.iso_builder import ISOBuildWorker, _iso9660_name


@pytest.fixture(scope="module", autouse=True)
def qapp():
    """Ensure a QCoreApplication exists for signal/slot tests."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def test_iso_build_worker_init():
    """Constructor should set all fields correctly."""
    project = {"id": 1, "name": "Test CD", "album_title": "Test Album"}
    tracks = [{"id": 1, "title": "Track 1", "track_number": 1}]
    songs = [{"id": 10, "title": "Song 1"}]

    worker = ISOBuildWorker(
        project=project,
        tracks=tracks,
        songs=songs,
        output_path="/tmp/test.iso",
    )

    assert worker.project == project
    assert worker.tracks == tracks
    assert worker.songs == songs
    assert worker.output_path == "/tmp/test.iso"
    assert worker._stop_requested is False


def test_iso_build_stop_cancels():
    """Setting stop flag should prevent build from completing."""
    project = {"id": 99, "name": "Test"}
    worker = ISOBuildWorker(project, [], [], "/tmp/test.iso")
    worker.stop()
    assert worker._stop_requested is True


def test_iso9660_name_basic():
    """_iso9660_name should produce valid ISO 9660 names."""
    assert _iso9660_name("hello.txt") == "HELLO.TXT"
    assert _iso9660_name("My Song (1).mp3") == "MY_SONG__1_.MP3"
    assert _iso9660_name("") == "FILE"


def test_iso9660_name_long():
    """Long names should be truncated."""
    long_name = "a" * 100 + ".mp3"
    result = _iso9660_name(long_name)
    # Should have truncated base name + extension
    assert len(result) <= 28 + 4  # 24 char base + ext


def test_iso_build_missing_pycdlib():
    """If pycdlib is not importable, error signal should be emitted."""
    project = {"id": 1, "name": "Test"}
    worker = ISOBuildWorker(project, [], [], "/tmp/test.iso")

    errors = []
    worker.build_error.connect(errors.append)

    with patch.dict("sys.modules", {"pycdlib": None}):
        # Force ImportError by patching builtins import
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "pycdlib":
                raise ImportError("No module named 'pycdlib'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            worker.run()

    assert len(errors) == 1
    assert "pycdlib" in errors[0].lower()


def test_iso_build_creates_file(tmp_path):
    """Worker should create an ISO file with pycdlib."""
    # Create a fake data directory that build_data_directory would produce
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "album_info.txt").write_text("Test Album\n")
    mp3_dir = data_dir / "MP3"
    mp3_dir.mkdir()
    (mp3_dir / "01 - Track 1.mp3").write_bytes(b"\x00" * 100)

    project = {
        "id": 1,
        "name": "Test CD",
        "album_title": "Test Album",
        "include_mp3": True,
        "include_lyrics": False,
        "include_source": False,
    }
    tracks = [{"id": 1, "title": "Track 1", "track_number": 1, "source_path": ""}]
    songs = []

    output_path = str(tmp_path / "output.iso")

    # Mock build_data_directory to return our pre-built dir
    with patch(
        "automation.iso_builder.build_data_directory",
        return_value=str(data_dir),
    ):
        worker = ISOBuildWorker(project, tracks, songs, output_path)

        completed_paths = []
        worker.build_completed.connect(completed_paths.append)

        errors = []
        worker.build_error.connect(errors.append)

        worker.run()

    assert len(errors) == 0, f"Unexpected errors: {errors}"
    assert len(completed_paths) == 1
    assert completed_paths[0] == output_path
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0

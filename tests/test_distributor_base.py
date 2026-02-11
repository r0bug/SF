"""Tests for the distributor plugin interface."""

from automation.distributor_base import (
    DistroKidPlugin, get_distributor, list_distributors,
    AVAILABLE_DISTRIBUTORS,
)


def test_distrokid_plugin_properties():
    dk = DistroKidPlugin()
    assert dk.name == "DistroKid"
    assert dk.slug == "distrokid"
    assert dk.requires_browser is True


def test_distrokid_genre_map():
    dk = DistroKidPlugin()
    gm = dk.genre_map
    assert isinstance(gm, dict)
    assert "Rock" in gm


def test_distrokid_map_genre():
    dk = DistroKidPlugin()
    assert dk.map_genre("Rock") == "Rock"
    assert dk.map_genre("Unknown Genre XYZ") == "Pop"  # fallback


def test_distrokid_validate_valid():
    dk = DistroKidPlugin()
    errors = dk.validate_release({"song_id": 1, "songwriter": "John Doe"})
    assert errors == []


def test_distrokid_validate_missing_songwriter():
    dk = DistroKidPlugin()
    errors = dk.validate_release({"song_id": 1, "songwriter": ""})
    assert any("songwriter" in e.lower() for e in errors)


def test_distrokid_validate_missing_song():
    dk = DistroKidPlugin()
    errors = dk.validate_release({"songwriter": "John"})
    assert any("song" in e.lower() for e in errors)


def test_distrokid_config_keys():
    dk = DistroKidPlugin()
    keys = dk.get_config_keys()
    assert "dk_email" in keys
    assert "dk_password" in keys


def test_get_distributor():
    dk = get_distributor("distrokid")
    assert dk is not None
    assert dk.name == "DistroKid"


def test_get_distributor_unknown():
    result = get_distributor("nonexistent")
    assert result is None


def test_list_distributors():
    distributors = list_distributors()
    assert len(distributors) >= 1
    assert any(d.slug == "distrokid" for d in distributors)

"""Tests for multi-artist support in the database."""


def test_default_artist_seeded(temp_db):
    """Fresh DB should have Yakima Finds as default artist."""
    artists = temp_db.get_all_artists()
    assert len(artists) >= 1
    default = temp_db.get_default_artist()
    assert default is not None
    assert default["name"] == "Yakima Finds"
    assert default["is_default"] == 1


def test_add_artist(temp_db):
    new_id = temp_db.add_artist("Side Project", legal_name="SP", bio="A side project")
    assert new_id > 0
    artist = temp_db.get_artist(new_id)
    assert artist["name"] == "Side Project"
    assert artist["is_default"] == 0


def test_add_default_artist_resets_others(temp_db):
    """Setting a new artist as default should clear the flag on others."""
    old_default = temp_db.get_default_artist()
    assert old_default["is_default"] == 1

    new_id = temp_db.add_artist("New Default", is_default=True)
    new_default = temp_db.get_default_artist()
    assert new_default["id"] == new_id

    # Old one should no longer be default
    old = temp_db.get_artist(old_default["id"])
    assert old["is_default"] == 0


def test_update_artist(temp_db):
    default = temp_db.get_default_artist()
    temp_db.update_artist(default["id"], bio="Updated bio")
    refreshed = temp_db.get_artist(default["id"])
    assert refreshed["bio"] == "Updated bio"


def test_delete_default_artist_refused(temp_db):
    default = temp_db.get_default_artist()
    result = temp_db.delete_artist(default["id"])
    assert result is False
    # Still exists
    assert temp_db.get_artist(default["id"]) is not None


def test_delete_non_default_artist(temp_db):
    new_id = temp_db.add_artist("Deletable")
    result = temp_db.delete_artist(new_id)
    assert result is True
    assert temp_db.get_artist(new_id) is None


def test_get_all_artists_ordering(temp_db):
    """Default artist should come first."""
    temp_db.add_artist("Zzz Band")
    temp_db.add_artist("Aaa Band")
    artists = temp_db.get_all_artists()
    assert artists[0]["is_default"] == 1
    # Non-defaults should be alphabetical
    non_defaults = [a for a in artists if not a["is_default"]]
    names = [a["name"] for a in non_defaults]
    assert names == sorted(names)

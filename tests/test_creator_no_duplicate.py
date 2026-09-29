"""Saving and queueing the same generated song must not create two rows."""

from unittest.mock import patch

LYRICS = "[Verse]\n" + "Walking down Second Street in Yak-eh-Mah\n" * 6


def _tab(qt_app, seeded_db):
    from tabs.creator import SongCreatorTab
    tab = SongCreatorTab(seeded_db)
    tab.on_generation_complete({
        "title": "Zz Test Anthem", "prompt": "Upbeat classic rock, organ",
        "lyrics": LYRICS, "genre_label": "Rock",
    })
    return tab


def _rows(db, title):
    return [s for s in db.get_all_songs() if s["title"] == title]


@patch("tabs.creator.QMessageBox")
def test_queue_then_save_is_one_song(_mb, qt_app, seeded_db):
    tab = _tab(qt_app, seeded_db)
    tab.save_song(status="queued")
    tab.save_song(status="draft")
    rows = _rows(seeded_db, "Zz Test Anthem")
    assert len(rows) == 1
    assert rows[0]["status"] == "queued"  # not downgraded to draft


@patch("tabs.creator.QMessageBox")
def test_save_then_queue_promotes_draft(_mb, qt_app, seeded_db):
    tab = _tab(qt_app, seeded_db)
    tab.save_song(status="draft")
    tab.save_song(status="queued")
    rows = _rows(seeded_db, "Zz Test Anthem")
    assert [r["status"] for r in rows] == ["queued"]


@patch("tabs.creator.QMessageBox")
def test_new_generation_makes_new_song(_mb, qt_app, seeded_db):
    tab = _tab(qt_app, seeded_db)
    tab.save_song(status="queued")
    tab.on_generation_complete({"title": "Zz Test Anthem", "prompt": "Take two",
                                "lyrics": LYRICS, "genre_label": "Rock"})
    tab.save_song(status="queued")
    assert len(_rows(seeded_db, "Zz Test Anthem")) == 2

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


@patch("tabs.creator.QMessageBox")
def test_open_draft_then_save_updates_it(_mb, qt_app, seeded_db):
    from tabs.creator import SongCreatorTab
    sid = seeded_db.add_song(title="Zz Draft", genre_id=None, genre_label="Rock",
                             prompt="p", lyrics=LYRICS, status="draft")
    tab = SongCreatorTab(seeded_db)
    tab.load_song(seeded_db.get_song(sid))
    assert "Walking down Second Street" in tab.lyrics_output.toPlainText()
    tab.lyrics_output.setPlainText(LYRICS + "\n[Outro]\nFade out")
    tab.save_song(status="queued")
    rows = _rows(seeded_db, "Zz Draft")
    assert len(rows) == 1 and rows[0]["status"] == "queued"
    assert rows[0]["lyrics"].endswith("Fade out")


@patch("tabs.creator.QMessageBox")
def test_open_completed_then_queue_makes_new_song(_mb, qt_app, seeded_db):
    from tabs.creator import SongCreatorTab
    sid = seeded_db.add_song(title="Zz Done", genre_id=None, genre_label="Rock",
                             prompt="p", lyrics=LYRICS, status="completed")
    tab = SongCreatorTab(seeded_db)
    tab.load_song(seeded_db.get_song(sid))
    tab.save_song(status="queued")
    statuses = sorted(r["status"] for r in _rows(seeded_db, "Zz Done"))
    assert statuses == ["completed", "queued"]  # original recording untouched


def test_picker_open_mode_lists_all_statuses(qt_app, seeded_db):
    from tabs.song_picker_dialog import SongPickerDialog
    seeded_db.add_song(title="Zz Draft 2", genre_id=None, genre_label="Rock",
                       prompt="p", lyrics=LYRICS, status="draft")
    dlg = SongPickerDialog(seeded_db, open_mode=True)
    titles = [s["title"] for s in dlg._all_songs]
    assert "Zz Draft 2" in titles
    cd = SongPickerDialog(seeded_db)  # CD mode still requires audio files
    assert "Zz Draft 2" not in [s["title"] for s in cd._all_songs]

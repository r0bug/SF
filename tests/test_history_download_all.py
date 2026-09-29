"""'Download All History' chains discovery into a full import."""

from unittest.mock import patch


def _dialog(qt_app, temp_db):
    from tabs.history_import_dialog import HistoryImportDialog
    dlg = HistoryImportDialog(temp_db)
    dlg.skip_existing_cb.setChecked(False)  # don't read the real user DB
    return dlg


def test_download_all_imports_everything_after_discovery(qt_app, temp_db):
    dlg = _dialog(qt_app, temp_db)
    with patch.object(dlg, "_start_discovery") as disc, \
         patch.object(dlg, "_start_import") as imp:
        dlg._start_download_all()
        disc.assert_called_once()

        for pid in ("a", "b"):
            dlg._on_song_found({"id": pid, "task_id": pid, "title": f"Song {pid}"})
        dlg._on_discovery_finished(0)

        imp.assert_called_once()
        assert all(dlg.table.cellWidget(r, 0).isChecked()
                   for r in range(dlg.table.rowCount()))


def test_plain_discovery_does_not_auto_import(qt_app, temp_db):
    dlg = _dialog(qt_app, temp_db)
    with patch.object(dlg, "_start_import") as imp:
        dlg._on_song_found({"id": "a", "task_id": "a", "title": "Song a"})
        dlg._on_discovery_finished(0)
        imp.assert_not_called()


def test_download_all_with_nothing_new(qt_app, temp_db):
    dlg = _dialog(qt_app, temp_db)
    with patch.object(dlg, "_start_discovery"), \
         patch.object(dlg, "_start_import") as imp:
        dlg._start_download_all()
        dlg._on_discovery_finished(0)
        imp.assert_not_called()
        assert "already imported" in dlg.status_label.text()

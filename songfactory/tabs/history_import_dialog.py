"""History Import Dialog for Song Factory.

Provides a QDialog that discovers songs from lalals.com history,
displays them in a table with checkboxes, and imports selected ones.
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QCheckBox, QProgressBar,
    QMessageBox, QAbstractItemView, QComboBox,
)
from PyQt6.QtCore import Qt

# Guard import
try:
    from automation.history_importer import HistoryImportWorker
    _HAS_IMPORTER = True
except ImportError:
    _HAS_IMPORTER = False

from theme import Theme


class HistoryImportDialog(QDialog):
    """Dialog for importing song history from lalals.com."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Import History from Lalals.com")
        self.setMinimumSize(700, 500)
        self.resize(800, 550)

        self._discovered_songs = []
        self._worker = None

        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header
        header = QLabel("Discover and import songs from your lalals.com history")
        header.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # Info label
        self.info_label = QLabel(
            "Click 'Discover' to scan your lalals.com account for past generations."
        )
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # Source selector
        source_row = QHBoxLayout()
        source_label = QLabel("Discovery Source:")
        source_label.setStyleSheet(f"color: {Theme.TEXT}; font-weight: bold;")
        source_row.addWidget(source_label)

        self.source_combo = QComboBox()
        self.source_combo.addItem("Profile Page", "profile")
        self.source_combo.addItem("Home/API (Legacy)", "legacy")
        self.source_combo.setMinimumWidth(180)
        source_row.addWidget(self.source_combo)
        source_row.addStretch()
        layout.addLayout(source_row)

        # Track type checkboxes
        track_row = QHBoxLayout()
        track_label = QLabel("Download:")
        track_label.setStyleSheet(f"color: {Theme.TEXT}; font-weight: bold;")
        track_row.addWidget(track_label)

        self.cb_full_song = QCheckBox("Full Song")
        self.cb_full_song.setChecked(True)
        track_row.addWidget(self.cb_full_song)

        self.cb_vocals = QCheckBox("Vocals")
        self.cb_vocals.setChecked(True)
        track_row.addWidget(self.cb_vocals)

        self.cb_instrumental = QCheckBox("Instrumental")
        self.cb_instrumental.setChecked(True)
        track_row.addWidget(self.cb_instrumental)

        self.cb_extract_lyrics = QCheckBox("Extract Lyrics")
        self.cb_extract_lyrics.setChecked(True)
        track_row.addWidget(self.cb_extract_lyrics)

        track_row.addStretch()
        layout.addLayout(track_row)

        # Discover button + skip checkbox
        top_row = QHBoxLayout()
        self.discover_btn = QPushButton("Discover History")
        self.discover_btn.clicked.connect(self._start_discovery)
        top_row.addWidget(self.discover_btn)

        self.skip_existing_cb = QCheckBox("Skip already imported")
        self.skip_existing_cb.setChecked(True)
        top_row.addWidget(self.skip_existing_cb)

        top_row.addStretch()
        layout.addLayout(top_row)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(18)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Table of discovered songs
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["", "Title", "Style", "Date", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 40)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

        # Select all / deselect all
        sel_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all)
        sel_row.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        sel_row.addWidget(self.deselect_all_btn)

        sel_row.addStretch()

        # Import button
        self.import_btn = QPushButton("Import Selected")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._start_import)
        sel_row.addWidget(self.import_btn)

        # Cancel button
        self.cancel_btn = QPushButton("Close")
        self.cancel_btn.clicked.connect(self.close)
        sel_row.addWidget(self.cancel_btn)

        layout.addLayout(sel_row)

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.BG};
                color: {Theme.TEXT};
            }}
            QLabel {{
                color: {Theme.TEXT};
            }}
            QTableWidget {{
                background-color: {Theme.BG};
                alternate-background-color: {Theme.PANEL};
                color: {Theme.TEXT};
                border: 1px solid #555555;
                border-radius: 4px;
            }}
            QTableWidget::item:selected {{
                background-color: {Theme.ACCENT};
                color: #000000;
            }}
            QHeaderView::section {{
                background-color: {Theme.PANEL};
                color: {Theme.TEXT};
                border: none;
                border-bottom: 2px solid {Theme.ACCENT};
                padding: 6px;
                font-weight: bold;
            }}
            QPushButton {{
                background-color: {Theme.PANEL};
                color: {Theme.TEXT};
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #444444;
                border-color: {Theme.ACCENT};
            }}
            QPushButton:disabled {{
                background-color: #3a3a3a;
                color: #666666;
            }}
            QComboBox {{
                background-color: {Theme.PANEL};
                color: {Theme.TEXT};
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 13px;
            }}
            QComboBox:focus {{
                border-color: {Theme.ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Theme.PANEL};
                color: {Theme.TEXT};
                selection-background-color: {Theme.ACCENT};
                selection-color: #000000;
            }}
            QCheckBox {{
                color: {Theme.TEXT};
                spacing: 6px;
            }}
            QProgressBar {{
                background-color: {Theme.BG};
                border: 1px solid #555555;
                border-radius: 4px;
                text-align: center;
                color: {Theme.TEXT};
            }}
            QProgressBar::chunk {{
                background-color: {Theme.ACCENT};
                border-radius: 3px;
            }}
        """)

    def _start_discovery(self):
        """Launch the history import worker in discovery mode."""
        if not _HAS_IMPORTER:
            QMessageBox.warning(
                self, "Missing Dependencies",
                "Requires playwright. Install with: pip install playwright && playwright install chromium"
            )
            return

        self.discover_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Opening browser to discover history...")
        self._discovered_songs = []
        self.table.setRowCount(0)

        is_profile = self.source_combo.currentData() == "profile"

        config = {
            "download_dir": self.db.get_config(
                "download_dir",
                str(os.path.join(os.path.expanduser("~"), "Music", "SongFactory")),
            ),
            "browser_path": self.db.get_config("browser_path", ""),
            "use_xvfb": True,  # run browser hidden via Xvfb
            "lalals_username": self.db.get_config("lalals_username", ""),
        }

        db_path = os.path.expanduser("~/.songfactory/songfactory.db")
        self._worker = HistoryImportWorker(
            db_path, config,
            profile_mode=is_profile,
        )
        self._worker.song_found.connect(self._on_song_found)
        self._worker.import_finished.connect(self._on_discovery_finished)
        self._worker.import_error.connect(self._on_import_error)
        self._worker.progress_update.connect(self._on_progress_update)
        self._worker.start()

    def _on_song_found(self, song_data: dict):
        """A song was discovered — add it to the table."""
        task_id = song_data.get("task_id") or song_data.get("taskId") or song_data.get("id", "")

        # Deduplicate in the table
        for existing in self._discovered_songs:
            eid = existing.get("task_id") or existing.get("taskId") or existing.get("id", "")
            if eid == task_id:
                return

        # Check if already in DB — by task_id or title
        already_imported = False
        title_match_id = None
        if self.skip_existing_cb.isChecked():
            try:
                import sqlite3
                conn = sqlite3.connect(os.path.expanduser("~/.songfactory/songfactory.db"))
                conn.row_factory = sqlite3.Row
                existing_song = conn.execute(
                    "SELECT id, file_path_1 FROM songs WHERE task_id=?", (task_id,)
                ).fetchone()
                if existing_song and existing_song["file_path_1"]:
                    already_imported = True
                elif not existing_song:
                    # Check by title match
                    discovered_title = (
                        song_data.get("title")
                        or song_data.get("prompt", "")[:60]
                        or ""
                    )
                    if discovered_title:
                        title_row = conn.execute(
                            "SELECT id, file_path_1 FROM songs WHERE LOWER(title)=LOWER(?)",
                            (discovered_title,)
                        ).fetchone()
                        if title_row:
                            title_match_id = title_row["id"]
                            if title_row["file_path_1"]:
                                already_imported = True
                conn.close()
            except Exception:
                pass

        self._discovered_songs.append(song_data)

        title = (song_data.get("title")
                 or song_data.get("track_name")
                 or song_data.get("prompt", "")[:60]
                 or f"Task-{task_id[:8]}")
        style = song_data.get("music_style") or song_data.get("musicStyle") or song_data.get("style", "")
        date = song_data.get("created_at") or song_data.get("createdAt", "")
        status_text = song_data.get("status", "")
        if already_imported:
            status_text = "Already imported"
        elif title_match_id:
            status_text = f"Title match (DB #{title_match_id})"

        row = self.table.rowCount()
        self.table.setRowCount(row + 1)

        # Checkbox
        cb = QCheckBox()
        cb.setChecked(not already_imported)
        cb.setEnabled(not already_imported)
        self.table.setCellWidget(row, 0, cb)

        self.table.setItem(row, 1, QTableWidgetItem(title))
        self.table.setItem(row, 2, QTableWidgetItem(style))
        self.table.setItem(row, 3, QTableWidgetItem(str(date)[:16] if date else ""))
        self.table.setItem(row, 4, QTableWidgetItem(status_text))
        self.table.setRowHeight(row, 32)

        self.status_label.setText(f"Discovered {len(self._discovered_songs)} song(s)...")

    def _on_discovery_finished(self, count: int):
        """Discovery phase complete."""
        self.discover_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.import_btn.setEnabled(len(self._discovered_songs) > 0)
        self.status_label.setText(
            f"Discovery complete: {len(self._discovered_songs)} song(s) found. "
            "Select songs and click 'Import Selected'."
        )
        self._worker = None

    def _on_import_error(self, message: str):
        self.status_label.setText(f"Error: {message}")

    def _on_progress_update(self, message: str):
        self.status_label.setText(message)

    def _select_all(self):
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if cb and cb.isEnabled():
                cb.setChecked(True)

    def _deselect_all(self):
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if cb:
                cb.setChecked(False)

    def _start_import(self):
        """Import the selected songs."""
        selected_task_ids = []
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if cb and cb.isChecked():
                song_data = self._discovered_songs[row]
                tid = song_data.get("task_id") or song_data.get("taskId") or song_data.get("id", "")
                if tid:
                    selected_task_ids.append(tid)

        if not selected_task_ids:
            QMessageBox.information(self, "No Selection", "No songs selected for import.")
            return

        self.import_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Importing {len(selected_task_ids)} song(s)...")

        is_profile = self.source_combo.currentData() == "profile"

        # Build track_types list from checkboxes
        track_types = []
        if self.cb_full_song.isChecked():
            track_types.append("Full Song")
        if self.cb_vocals.isChecked():
            track_types.append("Vocals")
        if self.cb_instrumental.isChecked():
            track_types.append("Instrumental")
        if not track_types:
            track_types = ["Full Song"]

        config = {
            "download_dir": self.db.get_config(
                "download_dir",
                str(os.path.join(os.path.expanduser("~"), "Music", "SongFactory")),
            ),
            "browser_path": self.db.get_config("browser_path", ""),
            "use_xvfb": True,
            "lalals_username": self.db.get_config("lalals_username", ""),
        }

        db_path = os.path.expanduser("~/.songfactory/songfactory.db")
        self._worker = HistoryImportWorker(
            db_path, config,
            selected_task_ids=selected_task_ids,
            pre_discovered=list(self._discovered_songs),
            profile_mode=is_profile,
            track_types=track_types,
            extract_lyrics=self.cb_extract_lyrics.isChecked(),
        )
        self._worker.song_imported.connect(self._on_song_imported)
        self._worker.import_finished.connect(self._on_import_finished)
        self._worker.import_error.connect(self._on_import_error)
        self._worker.progress_update.connect(self._on_progress_update)
        self._worker.start()

    def _on_song_imported(self, song_id: int, title: str):
        self.status_label.setText(f"Imported: {title}")

    def _on_import_finished(self, count: int):
        self.progress_bar.setVisible(False)
        self.import_btn.setEnabled(True)
        self.status_label.setText(f"Import complete: {count} song(s) imported")
        self._worker = None

    def close(self):
        """Stop worker if running before closing."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(5000)
        super().close()

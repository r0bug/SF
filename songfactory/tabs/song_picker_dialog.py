"""
Song Factory - Song Picker Dialog

Modal dialog for selecting songs from the library to add to a CD project.
Shows only songs that have audio files (file_path_1 IS NOT NULL).
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QLabel,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QTimer

from theme import Theme


class SongPickerDialog(QDialog):
    """Dialog for selecting songs to add to a CD project."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Add Songs to CD Project")
        self.setMinimumSize(700, 500)
        self.resize(800, 550)

        self._all_songs = []
        self._filtered_songs = []
        self._selected_songs = []

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._apply_filter)

        self._build_ui()
        self._apply_styles()
        self._load_songs()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QLabel("Select songs to add (only songs with audio files are shown)")
        header.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        # Search bar
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by title, genre, or lyrics...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_box)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Title", "Genre", "Duration", "File"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

        # Count label
        self.count_label = QLabel("0 songs selected")
        self.count_label.setStyleSheet(f"color: {Theme.TEXT}; font-size: 12px;")
        self.table.itemSelectionChanged.connect(self._update_count)
        layout.addWidget(self.count_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        add_btn = QPushButton("Add Selected")
        add_btn.setObjectName("addBtn")
        add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(add_btn)

        layout.addLayout(btn_row)

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QDialog {{ background-color: {Theme.BG}; }}
            QLabel {{ color: {Theme.TEXT}; }}
            QLineEdit {{
                background-color: {Theme.PANEL}; color: {Theme.TEXT};
                border: 1px solid #555555; border-radius: 4px; padding: 6px;
            }}
            QLineEdit:focus {{ border: 1px solid {Theme.ACCENT}; }}
            QTableWidget {{
                background-color: {Theme.BG}; alternate-background-color: #323232;
                color: {Theme.TEXT}; border: 1px solid #555555; gridline-color: transparent;
            }}
            QTableWidget::item:selected {{
                background-color: {Theme.ACCENT}; color: #000000;
            }}
            QHeaderView::section {{
                background-color: {Theme.PANEL}; color: {Theme.TEXT};
                border: none; border-bottom: 2px solid {Theme.ACCENT};
                padding: 6px; font-weight: bold;
            }}
            QPushButton {{
                background-color: {Theme.PANEL}; color: {Theme.TEXT};
                border: 1px solid #555555; border-radius: 4px;
                padding: 8px 16px; font-weight: bold;
            }}
            QPushButton:hover {{ border-color: {Theme.ACCENT}; }}
            QPushButton#addBtn {{
                background-color: {Theme.ACCENT}; color: #000000; border: none;
            }}
            QPushButton#addBtn:hover {{ background-color: #F0B848; }}
        """)

    def _load_songs(self):
        """Load songs with audio files from the database."""
        all_songs = self.db.get_all_songs()
        self._all_songs = [
            s for s in all_songs
            if s.get("file_path_1") and os.path.exists(s["file_path_1"])
        ]
        self._apply_filter()

    def _on_search_changed(self):
        self._search_timer.stop()
        self._search_timer.start()

    def _apply_filter(self):
        query = self.search_box.text().strip().lower()
        if query:
            self._filtered_songs = [
                s for s in self._all_songs
                if query in (s.get("title") or "").lower()
                or query in (s.get("genre_label") or "").lower()
                or query in (s.get("lyrics") or "").lower()
            ]
        else:
            self._filtered_songs = list(self._all_songs)

        self._populate_table()

    def _populate_table(self):
        songs = self._filtered_songs
        self.table.setRowCount(len(songs))

        for row, song in enumerate(songs):
            title_item = QTableWidgetItem(song.get("title", ""))
            title_item.setData(Qt.ItemDataRole.UserRole, song)
            self.table.setItem(row, 0, title_item)

            genre = song.get("genre_label") or ""
            self.table.setItem(row, 1, QTableWidgetItem(genre))

            dur = song.get("duration_seconds")
            if dur:
                m = int(dur) // 60
                s = int(dur) % 60
                dur_str = f"{m}:{s:02d}"
            else:
                dur_str = "—"
            self.table.setItem(row, 2, QTableWidgetItem(dur_str))

            fp = song.get("file_path_1", "")
            ext = os.path.splitext(fp)[1].upper() if fp else ""
            self.table.setItem(row, 3, QTableWidgetItem(ext))

            self.table.setRowHeight(row, 32)

    def _update_count(self):
        count = len(self.table.selectionModel().selectedRows())
        self.count_label.setText(f"{count} song{'s' if count != 1 else ''} selected")

    def _on_add(self):
        self._selected_songs = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item:
                song = item.data(Qt.ItemDataRole.UserRole)
                if song:
                    self._selected_songs.append(song)
        self.accept()

    def get_selected_songs(self) -> list[dict]:
        """Return the list of song dicts the user selected."""
        return self._selected_songs

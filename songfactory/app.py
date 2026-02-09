import sys
import os
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel, QApplication, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from database import Database
from seed_data import SEED_GENRES, SEED_LORE, SEED_SONGS
from tabs.creator import SongCreatorTab
from tabs.lore import LoreEditorTab
from tabs.genres import GenreManagerTab
from tabs.library import SongLibraryTab
from tabs.settings import SettingsTab
from tabs.lore_discovery import LoreDiscoveryTab
from tabs.cd_master import CDMasterTab


DARK_STYLESHEET = """
QMainWindow {
    background-color: #2b2b2b;
}
QTabWidget::pane {
    border: 1px solid #555555;
    background-color: #2b2b2b;
}
QTabBar::tab {
    background-color: #353535;
    color: #e0e0e0;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-size: 13px;
}
QTabBar::tab:selected {
    background-color: #E8A838;
    color: #1a1a1a;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background-color: #454545;
}
QWidget {
    background-color: #2b2b2b;
    color: #e0e0e0;
}
QLabel {
    color: #e0e0e0;
}
QTextEdit, QLineEdit, QPlainTextEdit {
    background-color: #353535;
    color: #e0e0e0;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 4px;
    selection-background-color: #E8A838;
    selection-color: #1a1a1a;
}
QTextEdit:focus, QLineEdit:focus {
    border: 1px solid #E8A838;
}
QPushButton {
    background-color: #454545;
    color: #e0e0e0;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #555555;
    border-color: #E8A838;
}
QPushButton:pressed {
    background-color: #E8A838;
    color: #1a1a1a;
}
QPushButton:disabled {
    background-color: #3a3a3a;
    color: #666666;
    border-color: #444444;
}
QComboBox {
    background-color: #353535;
    color: #e0e0e0;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px 10px;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #353535;
    color: #e0e0e0;
    selection-background-color: #E8A838;
    selection-color: #1a1a1a;
    border: 1px solid #555555;
}
QTableWidget {
    background-color: #353535;
    color: #e0e0e0;
    gridline-color: #454545;
    border: 1px solid #555555;
    selection-background-color: #E8A838;
    selection-color: #1a1a1a;
    alternate-background-color: #3a3a3a;
}
QTableWidget::item {
    padding: 4px;
}
QHeaderView::section {
    background-color: #404040;
    color: #e0e0e0;
    padding: 6px;
    border: 1px solid #555555;
    font-weight: bold;
}
QListWidget {
    background-color: #353535;
    color: #e0e0e0;
    border: 1px solid #555555;
    border-radius: 4px;
}
QListWidget::item {
    padding: 6px;
}
QListWidget::item:selected {
    background-color: #E8A838;
    color: #1a1a1a;
}
QListWidget::item:hover:!selected {
    background-color: #454545;
}
QCheckBox {
    color: #e0e0e0;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #555555;
    border-radius: 3px;
    background-color: #353535;
}
QCheckBox::indicator:checked {
    background-color: #E8A838;
    border-color: #E8A838;
}
QSpinBox {
    background-color: #353535;
    color: #e0e0e0;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 4px;
}
QGroupBox {
    color: #E8A838;
    border: 1px solid #555555;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QSplitter::handle {
    background-color: #454545;
    width: 3px;
    height: 3px;
}
QScrollBar:vertical {
    background-color: #2b2b2b;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #555555;
    border-radius: 6px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #E8A838;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background-color: #2b2b2b;
    height: 12px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #555555;
    border-radius: 6px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #E8A838;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QStatusBar {
    background-color: #1e1e1e;
    color: #888888;
    border-top: 1px solid #454545;
    font-size: 12px;
}
QMessageBox {
    background-color: #2b2b2b;
}
QMessageBox QLabel {
    color: #e0e0e0;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Song Factory — Yakima Finds")
        self.setMinimumSize(1200, 800)

        self.db = Database()
        self._seed_if_needed()
        self._check_for_backup()

        self._setup_tabs()
        self._setup_status_bar()

    def _seed_if_needed(self):
        if self.db.is_seeded():
            return
        for genre in SEED_GENRES:
            self.db.add_genre(
                name=genre['name'],
                prompt_template=genre['prompt_template'],
                description=genre.get('description', ''),
                bpm_range=genre.get('bpm_range', ''),
                active=genre.get('active', True),
            )
        for lore in SEED_LORE:
            self.db.add_lore(
                title=lore['title'],
                content=lore['content'],
                category=lore.get('category', 'general'),
                active=lore.get('active', True),
            )
        # Map genre names to IDs for songs
        genres = self.db.get_all_genres()
        genre_map = {}
        for g in genres:
            genre_map[g['name'].upper()] = g['id']
            genre_map[g['name']] = g['id']

        for song in SEED_SONGS:
            genre_id = None
            label = song.get('genre_label', '')
            # Try to match genre label to a genre in the database
            for gname, gid in genre_map.items():
                if gname.upper() in label.upper():
                    genre_id = gid
                    break
            self.db.add_song(
                title=song['title'],
                genre_id=genre_id,
                genre_label=song.get('genre_label', ''),
                prompt=song.get('prompt', ''),
                lyrics=song.get('lyrics', ''),
                user_input='',
                lore_snapshot='',
                status=song.get('status', 'completed'),
            )

    def _check_for_backup(self):
        """On a fresh install (no songs beyond seed data), look for a backup
        in the download directory and offer to restore it."""
        # Only trigger on a genuinely fresh database — seed songs have
        # status 'completed' and were just inserted by _seed_if_needed,
        # so we check whether there are any non-seed songs (i.e. user data).
        song_count = self.db.get_song_count()
        seed_count = len(SEED_SONGS)

        # If the user has added any songs beyond the seeds, skip
        if song_count > seed_count:
            return

        # Read download directory from config (may not be set yet on fresh install)
        _DEFAULT_DOWNLOAD_DIR = os.path.join(
            os.path.expanduser("~"), "Music", "SongFactory"
        )
        download_dir = self.db.get_config("download_dir", _DEFAULT_DOWNLOAD_DIR)

        backups = Database.detect_backups(download_dir)
        if not backups:
            return

        newest = backups[0]
        answer = QMessageBox.question(
            self,
            "Backup Found",
            f"A Song Factory backup was found:\n\n"
            f"  {newest['filename']}\n"
            f"  Date: {newest['date']}\n"
            f"  Location: {download_dir}\n\n"
            "Would you like to restore it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.db.restore_from(newest["path"])
        except Exception:
            pass  # Non-fatal; the app will still start with current DB

    def _setup_tabs(self):
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.creator_tab = SongCreatorTab(self.db)
        self.lore_tab = LoreEditorTab(self.db)
        self.genre_tab = GenreManagerTab(self.db)
        self.library_tab = SongLibraryTab(self.db)
        self.settings_tab = SettingsTab(self.db)
        self.discovery_tab = LoreDiscoveryTab(self.db)
        self.cd_master_tab = CDMasterTab(self.db)

        self.tabs.addTab(self.creator_tab, "🎵 Song Creator")
        self.tabs.addTab(self.lore_tab, "📖 Lore Editor")
        self.tabs.addTab(self.discovery_tab, "🔍 Lore Discovery")
        self.tabs.addTab(self.genre_tab, "🎸 Genre Manager")
        self.tabs.addTab(self.library_tab, "🗄️ Song Library")
        self.tabs.addTab(self.cd_master_tab, "💿 CD Master")
        self.tabs.addTab(self.settings_tab, "⚙️ Settings")

        # Refresh tabs when switching to them
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self.tabs)

    def _on_tab_changed(self, index):
        widget = self.tabs.widget(index)
        if widget is self.creator_tab:
            self.creator_tab.refresh_genres()
            self.creator_tab.refresh_lore()
        elif widget is self.lore_tab:
            self.lore_tab.load_lore_list()
        elif widget is self.genre_tab:
            self.genre_tab.load_genres()
        elif widget is self.library_tab:
            self.library_tab.load_songs()
        elif widget is self.cd_master_tab:
            self.cd_master_tab.refresh_projects()
        elif widget is self.settings_tab:
            self.settings_tab.load_settings()
        # discovery_tab has no refresh needed on tab switch
        self._update_status_bar()

    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.db_label = QLabel()
        self.songs_label = QLabel()
        self.api_label = QLabel()

        self.status_bar.addWidget(self.db_label, 1)
        self.status_bar.addWidget(self.songs_label, 1)
        self.status_bar.addPermanentWidget(self.api_label)

        self._update_status_bar()

    def _update_status_bar(self):
        db_path = os.path.expanduser("~/.songfactory/songfactory.db")
        self.db_label.setText(f"DB: {db_path}")

        count = self.db.get_song_count()
        self.songs_label.setText(f"Songs: {count}")

        api_key = self.db.get_config('api_key')
        if api_key:
            self.api_label.setText("API: Configured")
            self.api_label.setStyleSheet("color: #4CAF50;")
        else:
            self.api_label.setText("API: Not configured")
            self.api_label.setStyleSheet("color: #F44336;")

    def closeEvent(self, event):
        self.db.close()
        event.accept()

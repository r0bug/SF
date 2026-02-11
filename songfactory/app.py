import sys
import os
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel, QApplication, QMessageBox,
    QDialog, QVBoxLayout, QTextEdit, QPushButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QShortcut, QKeySequence

from database import Database
from theme import Theme
from seed_data import SEED_GENRES, SEED_LORE, SEED_SONGS
from tabs.creator import SongCreatorTab
from tabs.lore import LoreEditorTab
from tabs.genres import GenreManagerTab
from tabs.library import SongLibraryTab
from tabs.settings import SettingsTab
from tabs.lore_discovery import LoreDiscoveryTab
from tabs.cd_master import CDMasterTab
from tabs.distribution import DistributionTab
from tabs.analytics import AnalyticsTab


# Backward-compatible alias — main.py imports this
DARK_STYLESHEET = Theme.global_stylesheet()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Song Factory — Yakima Finds")
        self.setMinimumSize(1200, 800)

        self.db = Database()
        self._seed_if_needed()
        self._check_for_backup()
        self._auto_import_bundle()

        self._setup_tabs()
        self._setup_status_bar()
        self._setup_shortcuts()

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

    def _auto_import_bundle(self):
        """Import a personal bundle on startup if enabled and newer."""
        import logging
        logger = logging.getLogger("songfactory.sync")

        if self.db.get_config("auto_import_on_startup", "false").lower() != "true":
            return
        sync_folder = self.db.get_config("sync_folder", "")
        if not sync_folder:
            return

        bundle_path = os.path.join(sync_folder, "songfactory_personal.json")
        if not os.path.exists(bundle_path):
            return

        try:
            from export_import import preview_personal_bundle, import_personal_bundle

            preview = preview_personal_bundle(bundle_path)
            exported_at = preview.get("exported_at", "")
            last_import = self.db.get_config("last_import_at", "")

            if last_import and exported_at <= last_import:
                return  # Already up to date

            report = import_personal_bundle(self.db, bundle_path)
            from datetime import datetime
            now = datetime.now().isoformat(timespec="seconds")
            self.db.set_config("last_import_at", now)

            changes = {k: v for k, v in report.items() if v > 0}
            if changes:
                logger.info(
                    "Auto-imported personal bundle: %s",
                    ", ".join(f"{k}={v}" for k, v in changes.items()),
                )
        except Exception as exc:
            logger.error("Auto-import failed: %s", exc)

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
        self.distribution_tab = DistributionTab(self.db)
        self.analytics_tab = AnalyticsTab(self.db)

        self.tabs.addTab(self.creator_tab, "🎵 Song Creator")
        self.tabs.addTab(self.lore_tab, "📖 Lore Editor")
        self.tabs.addTab(self.discovery_tab, "🔍 Lore Discovery")
        self.tabs.addTab(self.genre_tab, "🎸 Genre Manager")
        self.tabs.addTab(self.library_tab, "🗄️ Song Library")
        self.tabs.addTab(self.cd_master_tab, "💿 CD Master")
        self.tabs.addTab(self.distribution_tab, "📤 Distribution")
        self.tabs.addTab(self.analytics_tab, "📊 Analytics")
        self.tabs.addTab(self.settings_tab, "⚙️ Settings")

        # Refresh tabs when switching to them
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self.tabs)

    def _on_tab_changed(self, index):
        widget = self.tabs.widget(index)
        # All tabs implement refresh() via BaseTab; discovery is a no-op
        if hasattr(widget, "refresh"):
            widget.refresh()
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
            self.api_label.setStyleSheet(f"color: {Theme.SUCCESS};")
        else:
            self.api_label.setText("API: Not configured")
            self.api_label.setStyleSheet(f"color: {Theme.ERROR};")

    def _setup_shortcuts(self):
        """Register application-wide keyboard shortcuts."""
        # Tab switching: Ctrl+1 through Ctrl+8
        for i in range(min(8, self.tabs.count())):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self)
            shortcut.activated.connect(lambda idx=i: self.tabs.setCurrentIndex(idx))

        # F5 — Refresh current tab
        QShortcut(QKeySequence("F5"), self).activated.connect(self._refresh_current_tab)

        # Ctrl+? — Help dialog
        QShortcut(QKeySequence("Ctrl+/"), self).activated.connect(self._show_help)

    def _refresh_current_tab(self):
        widget = self.tabs.currentWidget()
        if hasattr(widget, "refresh"):
            widget.refresh()
        self._update_status_bar()

    def _show_help(self):
        """Show the keyboard shortcuts help dialog."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Keyboard Shortcuts")
        dlg.setMinimumSize(420, 340)
        layout = QVBoxLayout(dlg)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(f"""
        <h3 style="color: {Theme.ACCENT};">Keyboard Shortcuts</h3>
        <table style="font-size: 13px;">
        <tr><td><b>Ctrl+1</b> &ndash; <b>Ctrl+8</b></td><td>Switch to tab 1&ndash;8</td></tr>
        <tr><td><b>F5</b></td><td>Refresh current tab</td></tr>
        <tr><td><b>Ctrl+/</b></td><td>Show this help dialog</td></tr>
        </table>
        """)
        layout.addWidget(text)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)

        dlg.exec()

    def closeEvent(self, event):
        # Clean up all tab workers before closing
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if hasattr(tab, "cleanup"):
                tab.cleanup()
        self.db.close()
        event.accept()

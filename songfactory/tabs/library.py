"""
Song Factory - Song Library Tab

Provides a SongLibraryTab widget with search/filter controls, a song table
with colored status badges, and an expandable detail area for viewing and
editing individual songs.

Includes browser automation queue controls for processing songs through
Lalals.com via the LalalsWorker background thread.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QPushButton, QLabel, QMessageBox, QAbstractItemView, QFrame,
    QApplication, QSizePolicy, QProgressBar, QMenu,
    QDialog, QListWidget, QListWidgetItem, QColorDialog, QInputDialog,
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QFont, QDesktopServices, QAction

from widgets.tag_chips import TagChipsWidget

from tabs.base_tab import BaseTab
from theme import Theme
from event_bus import event_bus

# Guard the import -- playwright may not be installed
try:
    from automation.browser_worker import LalalsWorker
    _HAS_WORKER = True
except ImportError:
    _HAS_WORKER = False

try:
    from automation.api_worker import MusicGptApiWorker
    _HAS_API_WORKER = True
except ImportError:
    _HAS_API_WORKER = False

try:
    from automation.song_detail_syncer import SongDetailSyncer
    _HAS_SYNCER = True
except ImportError:
    _HAS_SYNCER = False


_ALL_STATUSES = ["draft", "queued", "processing", "submitted", "completed", "error", "imported"]


class StatusBadgeWidget(QLabel):
    """A small colored label used to display a song's status inside a table cell."""

    def __init__(self, status: str, parent=None):
        super().__init__(parent)
        self.setText(status)
        color = Theme.STATUS_COLORS.get(status, "#888888")
        # Determine foreground: dark text on bright backgrounds, light otherwise
        fg = "#000000" if status in ("processing",) else "#FFFFFF"
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background-color: {color};"
            f"color: {fg};"
            "border-radius: 4px;"
            "padding: 2px 8px;"
            "font-weight: bold;"
            "font-size: 11px;"
        )
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class SongLibraryTab(BaseTab):
    """Main widget for the Song Library tab."""

    def __init__(self, db, parent=None):
        # Instance variables MUST be initialised before super().__init__
        # because BaseTab.__init__ calls _init_ui() and _connect_signals().
        self.all_songs: list[dict] = []
        self.filtered_songs: list[dict] = []
        self.selected_song: dict | None = None
        self._worker: "LalalsWorker | None" = None
        self._detail_syncer = None

        super().__init__(db, parent)  # calls _init_ui(), _connect_signals()

        self._apply_styles()
        self.load_songs()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self):
        """Build the complete widget layout."""
        # Search debounce timer (signal connected in _connect_signals)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # ---- Queue control panel (top) ----
        self._build_queue_panel(root_layout)

        # ---- Top filter bar ----
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search songs...")
        self.search_box.setClearButtonEnabled(True)
        filter_bar.addWidget(self.search_box, stretch=3)

        self.genre_filter = QComboBox()
        self.genre_filter.setMinimumWidth(160)
        self.genre_filter.addItem("All Genres", userData=None)
        filter_bar.addWidget(self.genre_filter, stretch=1)

        self.status_filter = QComboBox()
        self.status_filter.setMinimumWidth(140)
        self.status_filter.addItem("All Statuses", userData=None)
        for s in _ALL_STATUSES:
            self.status_filter.addItem(s, userData=s)
        filter_bar.addWidget(self.status_filter, stretch=1)

        self.tag_filter = QComboBox()
        self.tag_filter.setMinimumWidth(140)
        self.tag_filter.addItem("All Tags", userData=None)
        filter_bar.addWidget(self.tag_filter, stretch=1)

        self.manage_tags_btn = QPushButton("Manage Tags")
        self.manage_tags_btn.setObjectName("manageTagsBtn")
        self.manage_tags_btn.setFixedHeight(28)
        self.manage_tags_btn.setToolTip("Add, rename, recolor, or delete tags")
        self.manage_tags_btn.setStyleSheet(
            f"background-color: {Theme.PANEL}; color: {Theme.TEXT}; "
            "border: 1px solid #555; border-radius: 4px; "
            "padding: 4px 12px; font-size: 12px;"
        )
        filter_bar.addWidget(self.manage_tags_btn)

        self.refresh_library_btn = QPushButton("Refresh")
        self.refresh_library_btn.setObjectName("refreshLibraryBtn")
        self.refresh_library_btn.setFixedHeight(28)
        self.refresh_library_btn.setToolTip("Reload song list from database")
        self.refresh_library_btn.setStyleSheet(
            f"background-color: {Theme.PANEL}; color: {Theme.TEXT}; "
            "border: 1px solid #555; border-radius: 4px; "
            "padding: 4px 12px; font-size: 12px;"
        )
        filter_bar.addWidget(self.refresh_library_btn)

        root_layout.addLayout(filter_bar)

        # ---- Batch actions bar ----
        batch_bar = QHBoxLayout()
        batch_bar.setSpacing(8)

        self.batch_delete_btn = QPushButton("Delete Selected")
        self.batch_delete_btn.setStyleSheet(
            f"background-color: {Theme.ERROR}; color: #FFFFFF; border: none; "
            "border-radius: 4px; padding: 6px 12px; font-weight: bold; font-size: 12px;"
        )
        self.batch_delete_btn.clicked.connect(self._batch_delete)
        self.batch_delete_btn.setVisible(False)
        batch_bar.addWidget(self.batch_delete_btn)

        self.batch_status_btn = QPushButton("Set Status...")
        self.batch_status_btn.setStyleSheet(
            f"background-color: {Theme.PANEL}; color: {Theme.TEXT}; border: 1px solid #555; "
            "border-radius: 4px; padding: 6px 12px; font-weight: bold; font-size: 12px;"
        )
        self.batch_status_btn.clicked.connect(self._batch_set_status)
        self.batch_status_btn.setVisible(False)
        batch_bar.addWidget(self.batch_status_btn)

        self.batch_export_btn = QPushButton("Export Selected")
        self.batch_export_btn.setStyleSheet(
            f"background-color: {Theme.PANEL}; color: {Theme.TEXT}; border: 1px solid #555; "
            "border-radius: 4px; padding: 6px 12px; font-weight: bold; font-size: 12px;"
        )
        self.batch_export_btn.clicked.connect(self._batch_export)
        self.batch_export_btn.setVisible(False)
        batch_bar.addWidget(self.batch_export_btn)

        self.batch_selection_label = QLabel("")
        self.batch_selection_label.setStyleSheet(
            f"color: {Theme.ACCENT}; font-size: 12px; font-weight: bold;"
        )
        self.batch_selection_label.setVisible(False)
        batch_bar.addWidget(self.batch_selection_label)

        batch_bar.addStretch()
        root_layout.addLayout(batch_bar)

        # ---- Song table ----
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Title", "Genre", "Tags", "Status", "Created", "Actions"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        # Enable custom context menu on the table
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        root_layout.addWidget(self.table, stretch=3)

        # ---- Detail area (hidden by default) ----
        self.detail_frame = QFrame()
        self.detail_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.detail_frame.setVisible(False)
        detail_layout = QVBoxLayout(self.detail_frame)
        detail_layout.setContentsMargins(10, 10, 10, 10)
        detail_layout.setSpacing(8)

        self.detail_title_label = QLabel()
        self.detail_title_label.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {Theme.ACCENT};"
        )
        detail_layout.addWidget(self.detail_title_label)

        # Prompt section
        prompt_label = QLabel("Prompt")
        prompt_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
        detail_layout.addWidget(prompt_label)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMaximumHeight(90)
        self.prompt_edit.setPlaceholderText("Song generation prompt...")
        detail_layout.addWidget(self.prompt_edit)

        # Lyrics section
        lyrics_label = QLabel("Lyrics")
        lyrics_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
        detail_layout.addWidget(lyrics_label)

        self.lyrics_edit = QTextEdit()
        self.lyrics_edit.setMinimumHeight(140)
        self.lyrics_edit.setPlaceholderText("Song lyrics...")
        mono_font = QFont("Courier New", 10)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.lyrics_edit.setFont(mono_font)
        detail_layout.addWidget(self.lyrics_edit)

        # Tags row
        tags_row = QHBoxLayout()
        tags_row.setSpacing(8)
        tags_label = QLabel("Tags:")
        tags_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
        tags_row.addWidget(tags_label)
        self.detail_tags_container = QWidget()
        self.detail_tags_layout = QHBoxLayout(self.detail_tags_container)
        self.detail_tags_layout.setContentsMargins(0, 0, 0, 0)
        tags_row.addWidget(self.detail_tags_container, stretch=1)
        self.edit_tags_btn = QPushButton("Edit Tags")
        self.edit_tags_btn.setFixedHeight(24)
        self.edit_tags_btn.setStyleSheet(
            f"background-color: {Theme.PANEL}; color: {Theme.TEXT}; "
            "border: 1px solid #555; border-radius: 4px; "
            "padding: 2px 10px; font-size: 11px;"
        )
        tags_row.addWidget(self.edit_tags_btn)
        detail_layout.addLayout(tags_row)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.save_btn = QPushButton("Save Changes")
        btn_row.addWidget(self.save_btn)

        self.requeue_btn = QPushButton("Re-queue")
        btn_row.addWidget(self.requeue_btn)

        self.process_this_btn = QPushButton("Process This Song")
        self.process_this_btn.setObjectName("processThisBtn")
        btn_row.addWidget(self.process_this_btn)

        self.copy_prompt_btn = QPushButton("Copy Prompt")
        btn_row.addWidget(self.copy_prompt_btn)

        self.copy_lyrics_btn = QPushButton("Copy Lyrics")
        btn_row.addWidget(self.copy_lyrics_btn)

        self.wrong_song_btn = QPushButton("Wrong Song")
        self.wrong_song_btn.setObjectName("wrongSongBtn")
        self.wrong_song_btn.setToolTip(
            "Delete downloaded files and re-download (wrong file was matched)"
        )
        btn_row.addWidget(self.wrong_song_btn)

        btn_row.addStretch()

        self.delete_btn = QPushButton("Delete")
        btn_row.addWidget(self.delete_btn)

        detail_layout.addLayout(btn_row)
        root_layout.addWidget(self.detail_frame, stretch=2)

    # ------------------------------------------------------------------
    # Queue control panel
    # ------------------------------------------------------------------

    def _build_queue_panel(self, parent_layout: QVBoxLayout):
        """Build the queue control panel at the top of the tab."""
        self.queue_frame = QFrame()
        self.queue_frame.setObjectName("queueFrame")
        self.queue_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.queue_frame.setFixedHeight(52)

        queue_layout = QHBoxLayout(self.queue_frame)
        queue_layout.setContentsMargins(10, 6, 10, 6)
        queue_layout.setSpacing(12)

        # Queue count label
        self.queue_count_label = QLabel("Queue: 0 songs waiting")
        self.queue_count_label.setObjectName("queueCountLabel")
        self.queue_count_label.setStyleSheet(
            f"color: {Theme.TEXT}; font-size: 12px; font-weight: bold;"
        )
        queue_layout.addWidget(self.queue_count_label)

        # Login button
        self.login_btn = QPushButton("Login to Lalals")
        self.login_btn.setObjectName("loginBtn")
        self.login_btn.setFixedHeight(30)
        queue_layout.addWidget(self.login_btn)

        # Process Queue button
        self.process_queue_btn = QPushButton("Process Queue")
        self.process_queue_btn.setObjectName("processQueueBtn")
        self.process_queue_btn.setFixedHeight(30)
        queue_layout.addWidget(self.process_queue_btn)

        # Stop button
        self.stop_queue_btn = QPushButton("Stop")
        self.stop_queue_btn.setObjectName("stopQueueBtn")
        self.stop_queue_btn.setFixedHeight(30)
        self.stop_queue_btn.setEnabled(False)
        queue_layout.addWidget(self.stop_queue_btn)

        # Refresh button — user clicks this when generation is done
        self.refresh_btn = QPushButton("Song is Done - Refresh")
        self.refresh_btn.setObjectName("refreshBtn")
        self.refresh_btn.setFixedHeight(30)
        self.refresh_btn.setEnabled(False)
        queue_layout.addWidget(self.refresh_btn)

        # Sync button — full history scan
        self.sync_btn = QPushButton("Sync History")
        self.sync_btn.setObjectName("syncBtn")
        self.sync_btn.setFixedHeight(30)
        queue_layout.addWidget(self.sync_btn)

        # Sync Details button — fetch prompt + lyrics for songs missing them
        self.sync_details_btn = QPushButton("Sync Details")
        self.sync_details_btn.setObjectName("syncDetailsBtn")
        self.sync_details_btn.setFixedHeight(30)
        self.sync_details_btn.setToolTip(
            "Fetch prompt and lyrics from lalals.com for songs missing them"
        )
        queue_layout.addWidget(self.sync_details_btn)

        # Recover Downloads button — re-fetch songs that have task_ids but no files
        self.recover_btn = QPushButton("Recover Downloads")
        self.recover_btn.setObjectName("recoverBtn")
        self.recover_btn.setFixedHeight(30)
        self.recover_btn.setToolTip(
            "Re-download songs that have task IDs but missing audio files"
        )
        queue_layout.addWidget(self.recover_btn)

        # Recover Error Songs button — find error songs on home page by title
        self.recover_error_btn = QPushButton("Recover Error Songs")
        self.recover_error_btn.setObjectName("recoverErrorBtn")
        self.recover_error_btn.setFixedHeight(30)
        self.recover_error_btn.setToolTip(
            "Find songs in 'error' status on the lalals.com home page\n"
            "and download them by title (headless browser)"
        )
        queue_layout.addWidget(self.recover_error_btn)

        # Status label
        self.queue_status_label = QLabel("Status: Idle")
        self.queue_status_label.setObjectName("queueStatusLabel")
        self.queue_status_label.setStyleSheet(
            f"color: {Theme.TEXT}; font-size: 12px;"
        )
        self.queue_status_label.setMinimumWidth(200)
        queue_layout.addWidget(self.queue_status_label, stretch=1)

        # Progress bar
        self.queue_progress = QProgressBar()
        self.queue_progress.setObjectName("queueProgressBar")
        self.queue_progress.setFixedHeight(18)
        self.queue_progress.setMinimumWidth(150)
        self.queue_progress.setMaximumWidth(250)
        self.queue_progress.setRange(0, 0)  # indeterminate initially
        self.queue_progress.setVisible(False)
        queue_layout.addWidget(self.queue_progress)

        parent_layout.addWidget(self.queue_frame)

    # ------------------------------------------------------------------
    # Signal wiring (called by BaseTab.__init__ after _init_ui)
    # ------------------------------------------------------------------

    def _connect_signals(self):
        """Connect all widget signals to their slots."""
        # Search / filter bar
        self._search_timer.timeout.connect(self.apply_filters)
        self.search_box.textChanged.connect(self._on_search_text_changed)
        self.genre_filter.currentIndexChanged.connect(self.apply_filters)
        self.status_filter.currentIndexChanged.connect(self.apply_filters)
        self.tag_filter.currentIndexChanged.connect(self.apply_filters)
        self.manage_tags_btn.clicked.connect(self._open_manage_tags)
        self.refresh_library_btn.clicked.connect(self.load_songs)

        # Song table
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        self.table.itemSelectionChanged.connect(self._update_batch_bar)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)

        # Queue panel buttons
        self.login_btn.clicked.connect(self._open_login_browser)
        self.process_queue_btn.clicked.connect(self._start_queue_processing)
        self.stop_queue_btn.clicked.connect(self._stop_queue_processing)
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        self.sync_btn.clicked.connect(self._open_import_history)
        self.sync_details_btn.clicked.connect(self._start_detail_sync)
        self.recover_btn.clicked.connect(self._recover_all_downloads)
        self.recover_error_btn.clicked.connect(self._recover_error_songs)

        # Detail area buttons
        self.save_btn.clicked.connect(self.save_changes)
        self.requeue_btn.clicked.connect(self.requeue_song)
        self.process_this_btn.clicked.connect(self._process_single_song)
        self.copy_prompt_btn.clicked.connect(self._copy_prompt)
        self.copy_lyrics_btn.clicked.connect(self._copy_lyrics)
        self.wrong_song_btn.clicked.connect(self._wrong_song)
        self.delete_btn.clicked.connect(self.delete_song)
        self.edit_tags_btn.clicked.connect(self._edit_song_tags)

        # Cross-tab event bus
        event_bus.songs_changed.connect(self.load_songs)
        event_bus.tags_changed.connect(self.refresh_tags_filter)

    # ------------------------------------------------------------------
    # BaseTab lifecycle overrides
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload song data from the database."""
        self.load_songs()

    def cleanup(self):
        """Stop running workers and release resources."""
        super().cleanup()
        # Stop the search debounce timer
        self._search_timer.stop()
        # Stop detail syncer if running
        if self._detail_syncer is not None and self._detail_syncer.isRunning():
            self._detail_syncer.requestInterruption()
            self._detail_syncer.wait(3000)

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def _open_login_browser(self):
        """Open a browser window for the user to log in to lalals.com."""
        if not _HAS_WORKER:
            QMessageBox.warning(
                self,
                "Missing Dependencies",
                "Browser automation requires playwright.\n\n"
                "Install it with:  pip install playwright && playwright install chromium",
            )
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Browser open...")
        self.queue_status_label.setText("Status: Log in via the browser window...")

        try:
            from pathlib import Path
            from playwright.sync_api import sync_playwright

            from automation.browser_profiles import get_profile_path
            profile_dir = get_profile_path("lalals")
            pw = sync_playwright().start()

            launch_args = {
                'headless': True,  # Always headless — prevents user from closing browser
                'accept_downloads': True,
                'viewport': {'width': 1280, 'height': 900},
                'args': ['--disable-blink-features=AutomationControlled'],
            }

            try:
                ctx = pw.chromium.launch_persistent_context(
                    profile_dir, channel='chrome', **launch_args
                )
            except Exception:
                ctx = pw.chromium.launch_persistent_context(
                    profile_dir, **launch_args
                )

            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto("https://lalals.com/auth/sign-in", wait_until="domcontentloaded")

            QMessageBox.information(
                self,
                "Login to Lalals.com",
                "A browser window has opened.\n\n"
                "Log in using Google Auth (or any method), then click OK here "
                "when you're done.\n\n"
                "Your session will be saved for queue processing.",
            )

            # Check if they actually logged in
            url = page.url
            if "/auth/" not in url:
                self.queue_status_label.setText("Status: Logged in successfully")
            else:
                self.queue_status_label.setText("Status: Login may not have completed")

            ctx.close()
            pw.stop()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open browser:\n\n{e}")
            self.queue_status_label.setText("Status: Idle")

        self.login_btn.setEnabled(True)
        self.login_btn.setText("Login to Lalals")

    # ------------------------------------------------------------------
    # Queue processing logic
    # ------------------------------------------------------------------

    def _start_queue_processing(self):
        """Gather config and start the appropriate worker for all queued songs."""
        is_api = self._is_api_mode()

        if is_api and not _HAS_API_WORKER:
            QMessageBox.warning(
                self,
                "Missing Module",
                "MusicGPT API worker module not found.\n\n"
                "Check that automation/api_worker.py exists.",
            )
            return

        if not is_api and not _HAS_WORKER:
            QMessageBox.warning(
                self,
                "Missing Dependencies",
                "Browser automation requires playwright.\n\n"
                "Install it with:  pip install playwright && playwright install chromium",
            )
            return

        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self, "Already Running", "Queue processing is already in progress."
            )
            return

        db_path = os.path.expanduser("~/.songfactory/songfactory.db")

        if is_api:
            # Validate API key
            api_key = self.db.get_config("musicgpt_api_key", "")
            if not api_key:
                QMessageBox.warning(
                    self,
                    "No API Key",
                    "MusicGPT API mode requires an API key.\n\n"
                    "Set it in Settings > Song Submission > MusicGPT API Key.",
                )
                return

            config = {
                "musicgpt_api_key": api_key,
                "download_dir": self.db.get_config(
                    "download_dir",
                    str(os.path.join(os.path.expanduser("~"), "Music", "SongFactory")),
                ),
                "delay_between_songs": int(
                    self.db.get_config("delay_between_songs", "30")
                ),
                "max_songs_per_session": int(
                    self.db.get_config("max_songs_per_session", "20")
                ),
                "dry_run": self.db.get_config("dry_run", "false").lower() == "true",
            }
            self._worker = MusicGptApiWorker(db_path, config)
        else:
            config = {
                "lalals_email": self.db.get_config("lalals_email", ""),
                "lalals_password": self.db.get_config("lalals_password", ""),
                "download_dir": self.db.get_config(
                    "download_dir",
                    str(os.path.join(os.path.expanduser("~"), "Music", "SongFactory")),
                ),
                "headless": self.db.get_config("headless", "false").lower() == "true",
                "delay_between_songs": int(
                    self.db.get_config("delay_between_songs", "30")
                ),
                "max_songs_per_session": int(
                    self.db.get_config("max_songs_per_session", "20")
                ),
                "generation_timeout": int(
                    self.db.get_config("generation_timeout", "600000")
                ),
                "dry_run": self.db.get_config("dry_run", "false").lower() == "true",
                "use_xvfb": self.db.get_config("use_xvfb", "false").lower() == "true",
            }
            self._worker = LalalsWorker(db_path, config)

        # Connect common signals (both workers have these)
        self._worker.song_started.connect(self._on_song_started)
        self._worker.song_completed.connect(self._on_song_completed)
        self._worker.song_error.connect(self._on_song_error)
        self._worker.progress_update.connect(self._on_progress_update)
        self._worker.queue_finished.connect(self._on_queue_finished)

        # Browser-only signals
        if not is_api:
            self._worker.login_required.connect(self._on_login_required)
            self._worker.awaiting_refresh.connect(self._on_awaiting_refresh)

        self.register_worker(self._worker)

        # Update UI state
        self.process_queue_btn.setEnabled(False)
        self.stop_queue_btn.setEnabled(True)
        self.queue_progress.setVisible(True)
        self.queue_progress.setRange(0, 0)  # indeterminate pulse
        mode_label = "API" if is_api else "Browser"
        self.queue_status_label.setText(f"Status: Starting ({mode_label})...")

        self._worker.start()

    def _stop_queue_processing(self):
        """Request the worker to stop gracefully."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self.queue_status_label.setText("Status: Stopping after current song...")
            self.stop_queue_btn.setEnabled(False)

    def _on_refresh_clicked(self):
        """User clicked 'Song is Done - Refresh' — tell the worker to proceed."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_refresh()
            self.refresh_btn.setEnabled(False)
            self.queue_status_label.setText("Status: Refreshing — downloading song...")
            self.queue_progress.setVisible(True)

    def _process_single_song(self):
        """Queue and immediately process the currently selected song."""
        if self.selected_song is None:
            return

        is_api = self._is_api_mode()

        if is_api and not _HAS_API_WORKER:
            QMessageBox.warning(
                self,
                "Missing Module",
                "MusicGPT API worker module not found.\n\n"
                "Check that automation/api_worker.py exists.",
            )
            return

        if not is_api and not _HAS_WORKER:
            QMessageBox.warning(
                self,
                "Missing Dependencies",
                "Browser automation requires playwright.\n\n"
                "Install it with:  pip install playwright && playwright install chromium",
            )
            return

        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self, "Already Running", "Queue processing is already in progress."
            )
            return

        song_id = self.selected_song["id"]

        # Set to queued first
        self.db.update_song(song_id, status="queued")
        self._refresh_after_edit(song_id)

        db_path = os.path.expanduser("~/.songfactory/songfactory.db")

        if is_api:
            api_key = self.db.get_config("musicgpt_api_key", "")
            if not api_key:
                QMessageBox.warning(
                    self,
                    "No API Key",
                    "MusicGPT API mode requires an API key.\n\n"
                    "Set it in Settings > Song Submission > MusicGPT API Key.",
                )
                return

            config = {
                "musicgpt_api_key": api_key,
                "download_dir": self.db.get_config(
                    "download_dir",
                    str(os.path.join(os.path.expanduser("~"), "Music", "SongFactory")),
                ),
                "delay_between_songs": int(
                    self.db.get_config("delay_between_songs", "30")
                ),
                "max_songs_per_session": int(
                    self.db.get_config("max_songs_per_session", "20")
                ),
                "dry_run": self.db.get_config("dry_run", "false").lower() == "true",
            }
            self._worker = MusicGptApiWorker(db_path, config, song_ids=[song_id])
        else:
            config = {
                "lalals_email": self.db.get_config("lalals_email", ""),
                "lalals_password": self.db.get_config("lalals_password", ""),
                "download_dir": self.db.get_config(
                    "download_dir",
                    str(os.path.join(os.path.expanduser("~"), "Music", "SongFactory")),
                ),
                "headless": self.db.get_config("headless", "false").lower() == "true",
                "delay_between_songs": int(
                    self.db.get_config("delay_between_songs", "30")
                ),
                "max_songs_per_session": int(
                    self.db.get_config("max_songs_per_session", "20")
                ),
                "generation_timeout": int(
                    self.db.get_config("generation_timeout", "600000")
                ),
                "dry_run": self.db.get_config("dry_run", "false").lower() == "true",
            }
            self._worker = LalalsWorker(db_path, config, song_ids=[song_id])

        # Connect common signals
        self._worker.song_started.connect(self._on_song_started)
        self._worker.song_completed.connect(self._on_song_completed)
        self._worker.song_error.connect(self._on_song_error)
        self._worker.progress_update.connect(self._on_progress_update)
        self._worker.queue_finished.connect(self._on_queue_finished)

        # Browser-only signals
        if not is_api:
            self._worker.login_required.connect(self._on_login_required)
            self._worker.awaiting_refresh.connect(self._on_awaiting_refresh)

        self.register_worker(self._worker)

        # Update UI state
        self.process_queue_btn.setEnabled(False)
        self.stop_queue_btn.setEnabled(True)
        self.queue_progress.setVisible(True)
        self.queue_progress.setRange(0, 0)
        mode_label = "API" if is_api else "Browser"
        self.queue_status_label.setText(f"Status: Starting single song ({mode_label})...")

        self._worker.start()

    # ------------------------------------------------------------------
    def _open_import_history(self):
        """Open the History Import dialog."""
        try:
            from tabs.history_import_dialog import HistoryImportDialog
            dialog = HistoryImportDialog(self.db, parent=self)
            dialog.exec()
            self.load_songs()  # Refresh after potential imports
        except ImportError:
            QMessageBox.warning(
                self,
                "Missing Dependencies",
                "History import requires playwright.\n\n"
                "Install it with:  pip install playwright && playwright install chromium",
            )

    # ------------------------------------------------------------------
    # Song detail sync
    # ------------------------------------------------------------------

    def _start_detail_sync(self, song_ids=None):
        """Sync prompt + lyrics from lalals.com for songs missing them.

        Args:
            song_ids: Optional list of DB song IDs. If None, syncs all
                      songs missing prompt or lyrics.
        """
        if not _HAS_SYNCER:
            QMessageBox.warning(
                self,
                "Missing Dependencies",
                "Detail sync requires playwright.\n\n"
                "Install it with:  pip install playwright && playwright install chromium",
            )
            return

        if hasattr(self, "_detail_syncer") and self._detail_syncer and self._detail_syncer.isRunning():
            QMessageBox.information(
                self, "Already Running",
                "Detail sync is already in progress.",
            )
            return

        config = {
            "lalals_username": self.db.get_config("lalals_username", ""),
            "use_xvfb": self.db.get_config("use_xvfb", "false").lower() == "true",
            "browser_path": self.db.get_config("browser_path", ""),
        }

        db_path = os.path.expanduser("~/.songfactory/songfactory.db")
        self._detail_syncer = SongDetailSyncer(db_path, config, song_ids=song_ids)
        self.register_worker(self._detail_syncer)
        self._detail_syncer.progress.connect(self._on_detail_sync_progress)
        self._detail_syncer.song_synced.connect(self._on_detail_song_synced)
        self._detail_syncer.finished.connect(self._on_detail_sync_finished)
        self._detail_syncer.error.connect(self._on_detail_sync_error)

        self.sync_details_btn.setEnabled(False)
        self.sync_details_btn.setText("Syncing...")
        self.queue_status_label.setText("Status: Syncing prompt & lyrics...")
        self._detail_syncer.start()

    def _on_detail_sync_progress(self, message: str):
        self.queue_status_label.setText(f"Status: {message}")

    def _on_detail_song_synced(self, db_id: int, title: str):
        self.queue_status_label.setText(f"Status: Synced '{title}'")

    def _on_detail_sync_finished(self, count: int):
        self.sync_details_btn.setEnabled(True)
        self.sync_details_btn.setText("Sync Details")
        self.queue_status_label.setText(
            f"Status: Detail sync complete — {count} song(s) updated"
        )
        self._detail_syncer = None
        self.load_songs()

    def _on_detail_sync_error(self, message: str):
        self.sync_details_btn.setEnabled(True)
        self.sync_details_btn.setText("Sync Details")
        self.queue_status_label.setText(f"Status: Sync error — {message}")
        self._detail_syncer = None

    # ------------------------------------------------------------------
    # Worker signal handlers
    # ------------------------------------------------------------------

    def _on_song_started(self, song_id: int, title: str):
        """Handle worker signal: a song has started processing."""
        self.queue_status_label.setText(f"Status: Processing '{title}'...")
        # Highlight the row in the table if visible
        self._highlight_song_row(song_id)
        self.load_songs()

    def _on_song_completed(self, song_id: int, file_path_1: str, file_path_2: str):
        """Handle worker signal: a song finished successfully."""
        self.queue_status_label.setText("Status: Song completed")
        self.load_songs()

    def _on_song_error(self, song_id: int, error_msg: str):
        """Handle worker signal: a song failed."""
        self.queue_status_label.setText(f"Status: Error - {error_msg[:60]}")
        self.load_songs()

    def _on_progress_update(self, message: str):
        """Handle worker signal: status text update."""
        self.queue_status_label.setText(f"Status: {message}")

    def _on_login_required(self, message: str):
        """Handle worker signal: manual login needed in the browser window."""
        QMessageBox.information(
            self,
            "Login Required",
            message,
        )

    def _on_awaiting_refresh(self, song_id: int, title: str):
        """Handle worker signal: song submitted, waiting for user Refresh."""
        self.refresh_btn.setEnabled(True)
        self.queue_progress.setVisible(False)
        self.queue_status_label.setText(
            f"Status: '{title}' submitted — click Refresh when done"
        )
        self.load_songs()

    def _on_queue_finished(self):
        """Handle worker signal: entire queue is done."""
        self.process_queue_btn.setEnabled(True)
        self.stop_queue_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.queue_progress.setVisible(False)
        self.queue_status_label.setText("Status: Idle")
        self._worker = None
        self.load_songs()

    def _highlight_song_row(self, song_id: int):
        """Select/highlight the table row for a given song ID."""
        for row_idx, song in enumerate(self.filtered_songs):
            if song.get("id") == song_id:
                self.table.selectRow(row_idx)
                return

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_table_context_menu(self, position):
        """Show a right-click context menu on the song table."""
        row_idx = self.table.rowAt(position.y())
        if row_idx < 0 or row_idx >= len(self.filtered_songs):
            return

        song = self.filtered_songs[row_idx]
        song_id = song.get("id")
        title = song.get("title", "Untitled")

        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background-color: {Theme.PANEL}; color: {Theme.TEXT}; "
            f"border: 1px solid #555555; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 20px; }}"
            f"QMenu::item:selected {{ background-color: {Theme.ACCENT}; color: #000000; }}"
        )

        # Queue for Processing
        queue_action = QAction("Queue for Processing", self)
        queue_action.triggered.connect(
            lambda checked, sid=song_id: self._context_queue_song(sid)
        )
        menu.addAction(queue_action)

        # Re-download / Recover Download
        task_id = song.get("task_id")
        has_file = bool(song.get("file_path_1"))
        if task_id:
            redownload_action = QAction("Re-download", self)
            redownload_action.triggered.connect(
                lambda checked, sid=song_id, tid=task_id: self._context_redownload(sid, tid)
            )
            menu.addAction(redownload_action)

            # Sync Prompt & Lyrics
            sync_detail_action = QAction("Sync Prompt && Lyrics", self)
            sync_detail_action.triggered.connect(
                lambda checked, sid=song_id: self._start_detail_sync(song_ids=[sid])
            )
            menu.addAction(sync_detail_action)
        else:
            recover_action = QAction("Recover from Home Page", self)
            recover_action.setToolTip(
                "Download this song from the lalals.com home page by title"
            )
            recover_action.triggered.connect(
                lambda checked, sid=song_id, t=title: self._recover_from_home(sid, t)
            )
            menu.addAction(recover_action)

        # Wrong Song — Re-download (only if there's a downloaded file)
        if has_file:
            wrong_song_action = QAction("Wrong Song \u2014 Re-download", self)
            wrong_song_action.setToolTip(
                "Delete downloaded files and re-download (wrong file was matched)"
            )
            wrong_song_action.triggered.connect(
                lambda checked, sid=song_id: self._context_wrong_song(sid)
            )
            menu.addAction(wrong_song_action)

        # Add to CD Project submenu
        cd_projects = self.db.get_all_cd_projects()
        if cd_projects:
            cd_menu = QMenu("Add to CD Project", self)
            cd_menu.setStyleSheet(
                f"QMenu {{ background-color: {Theme.PANEL}; color: {Theme.TEXT}; "
                f"border: 1px solid #555555; padding: 4px; }}"
                f"QMenu::item {{ padding: 6px 20px; }}"
                f"QMenu::item:selected {{ background-color: {Theme.ACCENT}; color: #000000; }}"
            )
            for proj in cd_projects:
                proj_name = proj.get("name", "Untitled")
                proj_id = proj["id"]
                action = QAction(proj_name, self)
                action.triggered.connect(
                    lambda checked, pid=proj_id, s=song: self._add_to_cd_project(pid, s)
                )
                cd_menu.addAction(action)
            menu.addMenu(cd_menu)

        # Tags submenu
        all_tags = self.db.get_all_tags()
        if all_tags:
            tags_menu = QMenu("Tags", self)
            tags_menu.setStyleSheet(
                f"QMenu {{ background-color: {Theme.PANEL}; color: {Theme.TEXT}; "
                f"border: 1px solid #555555; padding: 4px; }}"
                f"QMenu::item {{ padding: 6px 20px; }}"
                f"QMenu::item:selected {{ background-color: {Theme.ACCENT}; color: #000000; }}"
            )
            song_tags = self.db.get_tags_for_song(song_id)
            song_tag_ids = {t["id"] for t in song_tags}
            for tag in all_tags:
                tag_action = QAction(tag["name"], self)
                tag_action.setCheckable(True)
                tag_action.setChecked(tag["id"] in song_tag_ids)
                tag_action.triggered.connect(
                    lambda checked, sid=song_id, tid=tag["id"]:
                        self._toggle_song_tag(sid, tid, checked)
                )
                tags_menu.addAction(tag_action)
            tags_menu.addSeparator()
            new_tag_action = QAction("Create New Tag...", self)
            new_tag_action.triggered.connect(
                lambda checked, sid=song_id: self._create_and_assign_tag(sid)
            )
            tags_menu.addAction(new_tag_action)
            menu.addMenu(tags_menu)

        menu.addSeparator()

        # Open Download Folder
        open_folder_action = QAction("Open Download Folder", self)
        open_folder_action.triggered.connect(
            lambda checked, s=song: self._context_open_folder(s)
        )
        menu.addAction(open_folder_action)

        # Play Song
        play_action = QAction("Play Song", self)
        file_path_1 = song.get("file_path_1", "")
        play_action.setEnabled(bool(file_path_1))
        play_action.triggered.connect(
            lambda checked, fp=file_path_1: self._context_play_song(fp)
        )
        menu.addAction(play_action)

        # Play Vocals
        fp_vocals = song.get("file_path_vocals", "")
        if fp_vocals and os.path.exists(fp_vocals):
            play_vocals_action = QAction("Play Vocals", self)
            play_vocals_action.triggered.connect(
                lambda checked, fp=fp_vocals: self._context_play_song(fp)
            )
            menu.addAction(play_vocals_action)

        # Play Instrumental
        fp_inst = song.get("file_path_instrumental", "")
        if fp_inst and os.path.exists(fp_inst):
            play_inst_action = QAction("Play Instrumental", self)
            play_inst_action.triggered.connect(
                lambda checked, fp=fp_inst: self._context_play_song(fp)
            )
            menu.addAction(play_inst_action)

        menu.exec(self.table.viewport().mapToGlobal(position))

    def _add_to_cd_project(self, project_id: int, song: dict):
        """Context menu action: add a song to a CD project."""
        tracks = self.db.get_cd_tracks(project_id)
        next_num = len(tracks) + 1
        source = song.get("file_path_1", "")
        title = song.get("title", "Untitled")
        dur = song.get("duration_seconds", 0)

        self.db.add_cd_track(
            project_id, next_num, title, source,
            song_id=song.get("id"),
            performer="Yakima Finds",
            duration_seconds=dur or 0,
        )

        proj = self.db.get_cd_project(project_id)
        proj_name = proj.get("name", "CD") if proj else "CD"
        QMessageBox.information(
            self,
            "Added to CD",
            f'"{title}" added to "{proj_name}" as track {next_num}.',
        )

    def _context_queue_song(self, song_id: int):
        """Context menu action: set a song's status to 'queued'."""
        updated = self.db.update_song(song_id, status="queued")
        if updated:
            self.load_songs()

    def _context_open_folder(self, song: dict):
        """Context menu action: open the download folder for a song."""
        # Try file_path_1 first, fall back to configured download dir
        file_path = song.get("file_path_1", "")
        if file_path and os.path.exists(file_path):
            folder = os.path.dirname(file_path)
        else:
            # Fall back to the configured download_dir / slugified title
            download_dir = self.db.get_config(
                "download_dir",
                str(os.path.join(os.path.expanduser("~"), "Music", "SongFactory")),
            )
            folder = download_dir

        if os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            QMessageBox.information(
                self,
                "Folder Not Found",
                f"Download folder does not exist yet:\n{folder}",
            )

    def _context_play_song(self, file_path: str):
        """Context menu action: open a song file with the system default player."""
        if file_path and os.path.exists(file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        else:
            QMessageBox.information(
                self,
                "File Not Found",
                f"Song file not found:\n{file_path or '(no path)'}",
            )

    def _context_redownload(self, song_id: int, task_id: str):
        """Context menu action: re-download a song using fresh URLs from MusicGPT API."""
        if not task_id:
            QMessageBox.information(
                self, "No Task ID",
                "This song has no task_id — it cannot be re-downloaded.",
            )
            return

        is_api = self._is_api_mode()

        if is_api:
            self._redownload_via_api(song_id, task_id)
        else:
            self._redownload_via_browser(song_id, task_id)

    def _redownload_via_api(self, song_id: int, task_id: str):
        """Re-download a song via direct HTTP (API mode, no browser)."""
        api_key = self.db.get_config("musicgpt_api_key", "")
        if not api_key:
            QMessageBox.warning(
                self,
                "No API Key",
                "MusicGPT API mode requires an API key.\n\n"
                "Set it in Settings > Song Submission > MusicGPT API Key.",
            )
            return

        self.queue_status_label.setText("Status: Fetching fresh URLs via API...")
        QApplication.processEvents()

        try:
            import json
            import urllib.request
            import urllib.error
            from automation.download_manager import DownloadManager
            from automation.api_worker import extract_metadata

            url = (
                "https://api.musicgpt.com/api/public/v1/byId"
                f"?conversionType=MUSIC_AI&task_id={task_id}"
            )
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                method="GET",
            )

            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            metadata = extract_metadata(data)

            if not metadata:
                self.queue_status_label.setText("Status: No metadata from API")
                QMessageBox.warning(
                    self, "Re-download Failed",
                    "Could not fetch metadata from MusicGPT API.",
                )
                return

            # Download files
            download_dir = self.db.get_config(
                "download_dir",
                str(os.path.join(os.path.expanduser("~"), "Music", "SongFactory")),
            )
            dm = DownloadManager(download_dir)
            song = self.db.get_song(song_id)
            title = song.get("title", "untitled") if song else "untitled"

            paths = []
            for version in (1, 2):
                audio_url = metadata.get(f"audio_url_{version}")
                if audio_url:
                    try:
                        path = dm.save_from_url(audio_url, title, version)
                        paths.append(str(path))
                    except Exception:
                        pass

            if paths:
                update_kwargs = {}
                if len(paths) >= 1:
                    update_kwargs["file_path_1"] = paths[0]
                if len(paths) >= 2:
                    update_kwargs["file_path_2"] = paths[1]
                for key in ("audio_url_1", "audio_url_2"):
                    if key in metadata:
                        update_kwargs[key] = metadata[key]

                self.db.update_song(song_id, **update_kwargs)
                self.queue_status_label.setText("Status: Re-download complete (API)")
                self.load_songs()
            else:
                self.queue_status_label.setText("Status: No downloadable URLs found")

        except Exception as e:
            self.queue_status_label.setText("Status: Re-download failed")
            QMessageBox.warning(
                self, "Re-download Error", f"Error during API re-download:\n\n{e}"
            )

    def _redownload_via_browser(self, song_id: int, task_id: str):
        """Re-download a song via browser automation (original method)."""
        if not _HAS_WORKER:
            QMessageBox.warning(
                self,
                "Missing Dependencies",
                "Browser automation requires playwright.\n\n"
                "Install it with:  pip install playwright && playwright install chromium",
            )
            return

        self.queue_status_label.setText("Status: Fetching fresh download URLs...")
        QApplication.processEvents()

        try:
            from playwright.sync_api import sync_playwright
            from automation.lalals_driver import LalalsDriver
            from automation.download_manager import DownloadManager
            from automation.browser_profiles import get_profile_path

            profile_dir = get_profile_path("lalals")
            pw = sync_playwright().start()

            launch_args = {
                'headless': True,  # Always headless — prevents user from closing browser
                'accept_downloads': True,
                'viewport': {'width': 1280, 'height': 900},
                'args': ['--disable-blink-features=AutomationControlled'],
            }

            try:
                ctx = pw.chromium.launch_persistent_context(
                    profile_dir, channel='chrome', **launch_args
                )
            except Exception:
                ctx = pw.chromium.launch_persistent_context(
                    profile_dir, **launch_args
                )

            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            driver = LalalsDriver(page, ctx)

            # Navigate to lalals.com first to establish session
            driver.navigate_to_music()

            # Fetch fresh URLs
            metadata = driver.fetch_fresh_urls(task_id)

            ctx.close()
            pw.stop()

            if not metadata:
                self.queue_status_label.setText("Status: Could not fetch fresh URLs")
                QMessageBox.warning(
                    self, "Re-download Failed",
                    "Could not fetch fresh URLs from MusicGPT API.\n"
                    "The session may have expired or the task may no longer exist.",
                )
                return

            # Download files
            download_dir = self.db.get_config(
                "download_dir",
                str(os.path.join(os.path.expanduser("~"), "Music", "SongFactory")),
            )
            dm = DownloadManager(download_dir)
            song = self.db.get_song(song_id)
            title = song.get("title", "untitled") if song else "untitled"

            paths = []
            for version in (1, 2):
                url = metadata.get(f"audio_url_{version}")
                if url:
                    try:
                        path = dm.save_from_url(url, title, version)
                        paths.append(str(path))
                    except Exception:
                        pass

            if paths:
                update_kwargs = {}
                if len(paths) >= 1:
                    update_kwargs["file_path_1"] = paths[0]
                if len(paths) >= 2:
                    update_kwargs["file_path_2"] = paths[1]
                # Update metadata too
                for key in ("audio_url_1", "audio_url_2"):
                    if key in metadata:
                        update_kwargs[key] = metadata[key]

                self.db.update_song(song_id, **update_kwargs)
                self.queue_status_label.setText("Status: Re-download complete")
                self.load_songs()
            else:
                self.queue_status_label.setText("Status: No downloadable URLs found")

        except Exception as e:
            self.queue_status_label.setText("Status: Re-download failed")
            QMessageBox.warning(
                self, "Re-download Error", f"Error during re-download:\n\n{e}"
            )

    # ------------------------------------------------------------------
    # Wrong Song — delete files and re-download
    # ------------------------------------------------------------------

    def _wrong_song(self):
        """Detail panel button handler: wrong song for the selected song."""
        if self.selected_song is None:
            return
        self._do_wrong_song(self.selected_song["id"])

    def _context_wrong_song(self, song_id: int):
        """Context menu handler: wrong song for a specific song_id."""
        self._do_wrong_song(song_id)

    def _do_wrong_song(self, song_id: int):
        """Delete wrong downloaded files, set error status, and trigger re-download.

        1. Confirm with user
        2. Delete existing files from disk
        3. Remove empty parent directory
        4. Clear DB file fields + set status to error
        5. If task_id exists → trigger re-download
        6. If no task_id → suggest recovery options
        """
        song = self.db.get_song(song_id)
        if not song:
            return
        title = song.get("title", "Untitled")

        reply = QMessageBox.question(
            self,
            "Wrong Song",
            f'Delete downloaded files for "{title}" and re-download?\n\n'
            "This will remove the current audio files from disk and attempt "
            "to download the correct version.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Collect file paths to delete
        path_fields = ("file_path_1", "file_path_2", "file_path_vocals", "file_path_instrumental")
        dirs_to_check = set()
        for field in path_fields:
            fp = song.get(field, "")
            if fp and os.path.exists(fp):
                try:
                    dirs_to_check.add(os.path.dirname(fp))
                    os.remove(fp)
                except OSError:
                    pass

        # Remove empty parent directories
        for d in dirs_to_check:
            try:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
            except OSError:
                pass

        # Clear DB fields and set error status
        self.db.update_song(
            song_id,
            file_path_1="",
            file_path_2="",
            file_size_1=0,
            file_size_2=0,
            file_path_vocals="",
            file_path_instrumental="",
            status="error",
            notes="Wrong song downloaded \u2014 re-download requested",
        )

        task_id = song.get("task_id")
        if task_id:
            self._refresh_after_edit(song_id)
            self._context_redownload(song_id, task_id)
        else:
            self._refresh_after_edit(song_id)
            QMessageBox.information(
                self,
                "No Task ID",
                f'Files for "{title}" have been removed.\n\n'
                "This song has no task_id, so automatic re-download is not possible.\n"
                'Use "Recover Error Songs" or "Recover from Home Page" '
                "(right-click menu) to re-download.",
            )

    # ------------------------------------------------------------------
    # Recover all downloads
    # ------------------------------------------------------------------

    def _recover_all_downloads(self):
        """Recover downloads for all songs with task_ids but missing files.

        Uses the MusicGPT API key to call byId for each song, then downloads.
        """
        api_key = self.db.get_config("musicgpt_api_key", "")
        if not api_key:
            QMessageBox.warning(
                self,
                "No API Key",
                "Recovering downloads requires a MusicGPT API key.\n\n"
                "Set it in Settings > Song Submission > MusicGPT API Key.",
            )
            return

        # Find songs with task_ids but no files
        recoverable = [
            s for s in self.all_songs
            if s.get("task_id")
            and not s.get("file_path_1")
        ]

        if not recoverable:
            QMessageBox.information(
                self,
                "Nothing to Recover",
                "No songs found with task IDs but missing files.\n\n"
                "To discover songs from your lalals.com history,\n"
                "use the 'Sync History' button first.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Recover Downloads",
            f"Found {len(recoverable)} song(s) with task IDs but no files.\n\n"
            "Recover downloads via MusicGPT API?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.recover_btn.setEnabled(False)
        self.queue_progress.setVisible(True)
        self.queue_progress.setRange(0, len(recoverable))

        try:
            from automation.api_worker import fetch_by_task_id, MusicGptApiError
            from automation.download_manager import DownloadManager

            download_dir = self.db.get_config(
                "download_dir",
                str(os.path.join(os.path.expanduser("~"), "Music", "SongFactory")),
            )
            dm = DownloadManager(download_dir)

            success_count = 0
            fail_count = 0

            for i, song in enumerate(recoverable):
                song_id = song["id"]
                title = song.get("title", "Untitled")
                task_id = song["task_id"]

                self.queue_status_label.setText(
                    f"Recovering: {title} ({i + 1}/{len(recoverable)})"
                )
                self.queue_progress.setValue(i)
                QApplication.processEvents()

                try:
                    metadata = fetch_by_task_id(api_key, task_id)
                    api_status = metadata.get("api_status", "")

                    if api_status and api_status != "COMPLETED":
                        fail_count += 1
                        continue

                    # Download files
                    paths = []
                    for version in (1, 2):
                        url = metadata.get(f"audio_url_{version}")
                        if url:
                            try:
                                path = dm.save_from_url(url, title, version)
                                paths.append(str(path))
                            except Exception:
                                pass

                    if paths:
                        update_kwargs = {"status": "completed"}
                        if len(paths) >= 1:
                            update_kwargs["file_path_1"] = paths[0]
                        if len(paths) >= 2:
                            update_kwargs["file_path_2"] = paths[1]
                        for key in ("audio_url_1", "audio_url_2",
                                    "conversion_id_1", "conversion_id_2",
                                    "duration_seconds", "music_style"):
                            if key in metadata:
                                update_kwargs[key] = metadata[key]

                        self.db.update_song(song_id, **update_kwargs)
                        success_count += 1
                    else:
                        fail_count += 1

                except MusicGptApiError:
                    fail_count += 1
                except Exception:
                    fail_count += 1

            self.queue_progress.setValue(len(recoverable))

            msg = f"Recovery complete: {success_count} downloaded"
            if fail_count:
                msg += f", {fail_count} failed"
            self.queue_status_label.setText(f"Status: {msg}")
            QMessageBox.information(self, "Recovery Complete", msg)

        except ImportError:
            QMessageBox.warning(
                self,
                "Missing Module",
                "Could not import api_worker module.",
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Recovery Error",
                f"Error during recovery:\n\n{e}",
            )

        self.recover_btn.setEnabled(True)
        self.queue_progress.setVisible(False)
        self.load_songs()

    # ------------------------------------------------------------------
    # Recover error songs (no task_id) via home page
    # ------------------------------------------------------------------

    def _recover_from_home(self, song_id: int, title: str):
        """Recover a single song by downloading from lalals.com home page.

        Used when no task_id was captured (browser closed, API capture failed).
        Opens a headless browser, navigates to home page, finds the song by
        title/prompt/lyrics text matching.
        """
        self.queue_status_label.setText(f"Status: Recovering '{title}' from home page...")
        QApplication.processEvents()

        # Fetch song prompt, lyrics, and task_id for better matching
        song_row = self.db.get_song(song_id) if hasattr(self.db, 'get_song') else None
        prompt = ""
        lyrics = ""
        task_id = ""
        if song_row:
            prompt = song_row.get("prompt", "") or ""
            lyrics = song_row.get("lyrics", "") or ""
            task_id = song_row.get("task_id", "") or ""

        try:
            from playwright.sync_api import sync_playwright
            from automation.lalals_driver import LalalsDriver
            from automation.browser_profiles import get_profile_path

            download_dir = self.db.get_config(
                "download_dir",
                str(os.path.join(os.path.expanduser("~"), "Music", "SongFactory")),
            )

            profile_dir = get_profile_path("lalals")
            pw = sync_playwright().start()

            launch_args = {
                'headless': True,
                'accept_downloads': True,
                'viewport': {'width': 1280, 'height': 900},
                'args': ['--disable-blink-features=AutomationControlled'],
            }

            try:
                ctx = pw.chromium.launch_persistent_context(
                    profile_dir, channel='chrome', **launch_args
                )
            except Exception:
                ctx = pw.chromium.launch_persistent_context(
                    profile_dir, **launch_args
                )

            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            driver = LalalsDriver(page, ctx)

            # Check login
            if not driver.is_logged_in():
                ctx.close()
                pw.stop()
                self.queue_status_label.setText("Status: Not logged in to lalals.com")
                QMessageBox.warning(
                    self, "Login Required",
                    "You need to be logged in to lalals.com to recover songs.\n\n"
                    "Use the 'Login to Lalals' button first.",
                )
                return

            # Go to home page and download by title/prompt/lyrics
            driver.go_to_home_page()
            page.wait_for_timeout(3000)
            paths = driver.download_from_home(
                title, download_dir, prompt=prompt, lyrics=lyrics,
                task_id=task_id,
            )

            # Capture a screenshot for debugging regardless of outcome
            driver._capture_debug_screenshot(f"recover_{song_id}")

            ctx.close()
            pw.stop()

            if paths:
                from pathlib import Path as _Path
                update_kwargs = {"status": "completed"}
                if len(paths) >= 1:
                    update_kwargs["file_path_1"] = str(paths[0])
                    try:
                        update_kwargs["file_size_1"] = _Path(paths[0]).stat().st_size
                    except OSError:
                        pass
                if len(paths) >= 2:
                    update_kwargs["file_path_2"] = str(paths[1])
                    try:
                        update_kwargs["file_size_2"] = _Path(paths[1]).stat().st_size
                    except OSError:
                        pass
                self.db.update_song(song_id, **update_kwargs)
                self.queue_status_label.setText(
                    f"Status: Recovered '{title}' — {len(paths)} file(s)"
                )
                self.load_songs()
            else:
                self.queue_status_label.setText(
                    f"Status: Could not find '{title}' on home page"
                )
                QMessageBox.warning(
                    self, "Recovery Failed",
                    f"Could not find '{title}' on the lalals.com home page.\n\n"
                    "The song may not be on the first page of results, "
                    "or the title may not match exactly.",
                )

        except Exception as e:
            self.queue_status_label.setText("Status: Recovery failed")
            QMessageBox.warning(
                self, "Recovery Error", f"Error during home page recovery:\n\n{e}"
            )

    def _recover_error_songs(self):
        """Batch recover all songs in 'error' status via home page download.

        Launches a single headless browser session and tries to find each
        error song on the lalals.com home page by title.
        """
        error_songs = [
            s for s in self.all_songs
            if s.get("status") == "error"
        ]

        if not error_songs:
            QMessageBox.information(
                self, "No Error Songs",
                "No songs in 'error' status to recover.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Recover Error Songs",
            f"Found {len(error_songs)} song(s) in error status.\n\n"
            "This will open a headless browser and try to download\n"
            "each song from the lalals.com home page by title.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.recover_error_btn.setEnabled(False)
        self.queue_progress.setVisible(True)
        self.queue_progress.setRange(0, len(error_songs))

        try:
            from playwright.sync_api import sync_playwright
            from automation.lalals_driver import LalalsDriver
            from automation.browser_profiles import get_profile_path

            download_dir = self.db.get_config(
                "download_dir",
                str(os.path.join(os.path.expanduser("~"), "Music", "SongFactory")),
            )

            profile_dir = get_profile_path("lalals")
            pw = sync_playwright().start()

            launch_args = {
                'headless': True,
                'accept_downloads': True,
                'viewport': {'width': 1280, 'height': 900},
                'args': ['--disable-blink-features=AutomationControlled'],
            }

            try:
                ctx = pw.chromium.launch_persistent_context(
                    profile_dir, channel='chrome', **launch_args
                )
            except Exception:
                ctx = pw.chromium.launch_persistent_context(
                    profile_dir, **launch_args
                )

            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            driver = LalalsDriver(page, ctx)

            if not driver.is_logged_in():
                ctx.close()
                pw.stop()
                self.recover_error_btn.setEnabled(True)
                self.queue_progress.setVisible(False)
                self.queue_status_label.setText("Status: Not logged in")
                QMessageBox.warning(
                    self, "Login Required",
                    "You need to be logged in to lalals.com.\n"
                    "Use 'Login to Lalals' first.",
                )
                return

            success_count = 0
            fail_count = 0

            for i, song in enumerate(error_songs):
                song_id = song["id"]
                title = song.get("title", "Untitled")
                prompt = song.get("prompt", "") or ""
                lyrics = song.get("lyrics", "") or ""
                task_id = song.get("task_id", "") or ""

                self.queue_status_label.setText(
                    f"Recovering: {title} ({i + 1}/{len(error_songs)})"
                )
                self.queue_progress.setValue(i)
                QApplication.processEvents()

                try:
                    driver.go_to_home_page()
                    page.wait_for_timeout(3000)
                    paths = driver.download_from_home(
                        title, download_dir, prompt=prompt, lyrics=lyrics,
                        task_id=task_id,
                    )

                    if paths:
                        from pathlib import Path as _Path
                        update_kwargs = {"status": "completed"}
                        if len(paths) >= 1:
                            update_kwargs["file_path_1"] = str(paths[0])
                            try:
                                update_kwargs["file_size_1"] = _Path(paths[0]).stat().st_size
                            except OSError:
                                pass
                        if len(paths) >= 2:
                            update_kwargs["file_path_2"] = str(paths[1])
                            try:
                                update_kwargs["file_size_2"] = _Path(paths[1]).stat().st_size
                            except OSError:
                                pass
                        self.db.update_song(song_id, **update_kwargs)
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1

            driver._capture_debug_screenshot("recover_error_batch")
            ctx.close()
            pw.stop()

            self.queue_progress.setValue(len(error_songs))
            msg = f"Recovery complete: {success_count} recovered"
            if fail_count:
                msg += f", {fail_count} not found on home page"
            self.queue_status_label.setText(f"Status: {msg}")
            QMessageBox.information(self, "Recovery Complete", msg)

        except Exception as e:
            self.queue_status_label.setText("Status: Recovery failed")
            QMessageBox.warning(
                self, "Recovery Error", f"Error during batch recovery:\n\n{e}"
            )

        self.recover_error_btn.setEnabled(True)
        self.queue_progress.setVisible(False)
        self.load_songs()

    # ------------------------------------------------------------------
    # Stylesheet
    # ------------------------------------------------------------------

    def _apply_styles(self):
        """Apply the dark theme stylesheet to the entire tab."""
        self.setStyleSheet(f"""
            SongLibraryTab {{
                background-color: {Theme.BG};
            }}

            QLineEdit {{
                background-color: {Theme.PANEL};
                color: {Theme.TEXT};
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Theme.ACCENT};
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
                border: 1px solid {Theme.ACCENT};
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

            QTableWidget {{
                background-color: {Theme.BG};
                alternate-background-color: {Theme.ROW_ODD};
                color: {Theme.TEXT};
                border: 1px solid #555555;
                border-radius: 4px;
                gridline-color: transparent;
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
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
                padding: 6px 8px;
                font-weight: bold;
                font-size: 12px;
            }}

            QFrame#detailFrame {{
                background-color: {Theme.PANEL};
                border: 1px solid #555555;
                border-radius: 6px;
            }}

            QFrame#queueFrame {{
                background-color: {Theme.PANEL};
                border: 1px solid #555555;
                border-radius: 6px;
            }}

            QTextEdit {{
                background-color: {Theme.BG};
                color: {Theme.TEXT};
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
            }}
            QTextEdit:focus {{
                border: 1px solid {Theme.ACCENT};
            }}

            QPushButton {{
                background-color: {Theme.PANEL};
                color: {Theme.TEXT};
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #444444;
                border-color: {Theme.ACCENT};
            }}
            QPushButton:pressed {{
                background-color: {Theme.ACCENT};
                color: #000000;
            }}
            QPushButton:disabled {{
                background-color: #3a3a3a;
                color: #666666;
                border-color: #444444;
            }}

            QPushButton#saveBtn {{
                background-color: #4CAF50;
                color: #FFFFFF;
                border: none;
            }}
            QPushButton#saveBtn:hover {{
                background-color: #5CBF60;
            }}

            QPushButton#deleteBtn {{
                background-color: #F44336;
                color: #FFFFFF;
                border: none;
            }}
            QPushButton#deleteBtn:hover {{
                background-color: #FF5544;
            }}

            QPushButton#requeueBtn {{
                background-color: #2196F3;
                color: #FFFFFF;
                border: none;
            }}
            QPushButton#requeueBtn:hover {{
                background-color: #42A5F5;
            }}

            QPushButton#wrongSongBtn {{
                background-color: #FF9800;
                color: #000000;
                border: none;
            }}
            QPushButton#wrongSongBtn:hover {{
                background-color: #FFB74D;
            }}

            QPushButton#processQueueBtn {{
                background-color: {Theme.ACCENT};
                color: #000000;
                border: none;
                font-weight: bold;
            }}
            QPushButton#processQueueBtn:hover {{
                background-color: #F0B848;
            }}
            QPushButton#processQueueBtn:disabled {{
                background-color: #7a6a3a;
                color: #555555;
            }}

            QPushButton#stopQueueBtn {{
                background-color: #F44336;
                color: #FFFFFF;
                border: none;
                font-weight: bold;
            }}
            QPushButton#stopQueueBtn:hover {{
                background-color: #FF5544;
            }}
            QPushButton#stopQueueBtn:disabled {{
                background-color: #5a2a2a;
                color: #666666;
            }}

            QPushButton#refreshBtn {{
                background-color: #4CAF50;
                color: #FFFFFF;
                border: none;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 20px;
            }}
            QPushButton#refreshBtn:hover {{
                background-color: #66BB6A;
            }}
            QPushButton#refreshBtn:disabled {{
                background-color: #2a4a2a;
                color: #666666;
            }}

            QPushButton#syncBtn {{
                background-color: #7B1FA2;
                color: #FFFFFF;
                border: none;
                font-weight: bold;
            }}
            QPushButton#syncBtn:hover {{
                background-color: #9C27B0;
            }}

            QPushButton#recoverBtn {{
                background-color: #00897B;
                color: #FFFFFF;
                border: none;
                font-weight: bold;
            }}
            QPushButton#recoverBtn:hover {{
                background-color: #00ACC1;
            }}

            QPushButton#processThisBtn {{
                background-color: {Theme.ACCENT};
                color: #000000;
                border: none;
                font-weight: bold;
            }}
            QPushButton#processThisBtn:hover {{
                background-color: #F0B848;
            }}

            QProgressBar#queueProgressBar {{
                background-color: {Theme.BG};
                border: 1px solid #555555;
                border-radius: 4px;
                text-align: center;
                color: {Theme.TEXT};
                font-size: 10px;
            }}
            QProgressBar#queueProgressBar::chunk {{
                background-color: {Theme.ACCENT};
                border-radius: 3px;
            }}

            QLabel {{
                color: {Theme.TEXT};
            }}
        """)

        # Assign object names for targeted styling
        self.detail_frame.setObjectName("detailFrame")
        self.save_btn.setObjectName("saveBtn")
        self.delete_btn.setObjectName("deleteBtn")
        self.requeue_btn.setObjectName("requeueBtn")

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_songs(self):
        """Load all songs from the database and refresh the view."""
        self.all_songs = self.db.get_all_songs()
        self.refresh_genres_filter()
        self.refresh_tags_filter()
        self.apply_filters()
        self._update_queue_count()

    def _update_queue_count(self):
        """Count songs with status='queued' and update the queue label."""
        queued_count = sum(
            1 for s in self.all_songs if s.get("status") == "queued"
        )
        if queued_count == 1:
            self.queue_count_label.setText("Queue: 1 song waiting")
        else:
            self.queue_count_label.setText(f"Queue: {queued_count} songs waiting")

        # Also refresh queue panel buttons for current mode
        self._update_queue_panel_for_mode()

    # ------------------------------------------------------------------
    # Submission mode helpers
    # ------------------------------------------------------------------

    def _get_submission_mode(self) -> str:
        """Return the configured submission mode ('browser' or 'api')."""
        return self.db.get_config("submission_mode", "browser")

    def _is_api_mode(self) -> bool:
        """Return True if the configured mode is MusicGPT API."""
        return self._get_submission_mode() == "api"

    def _update_queue_panel_for_mode(self):
        """Show/hide queue panel buttons based on submission mode."""
        is_api = self._is_api_mode()

        # In API mode: hide browser-only buttons, keep Sync and Recover visible
        self.login_btn.setVisible(not is_api)
        self.refresh_btn.setVisible(not is_api)
        # Sync History stays visible in both modes (for discovering task_ids)
        self.sync_btn.setVisible(True)
        # Recover Downloads is always visible
        self.recover_btn.setVisible(True)

        # Update button label
        if is_api:
            self.process_queue_btn.setText("Process Queue (API)")
        else:
            self.process_queue_btn.setText("Process Queue")

    def refresh_genres_filter(self):
        """Reload the genre filter dropdown from the database."""
        current_data = self.genre_filter.currentData()
        self.genre_filter.blockSignals(True)
        self.genre_filter.clear()
        self.genre_filter.addItem("All Genres", userData=None)

        genres = self.db.get_all_genres()
        for genre in genres:
            self.genre_filter.addItem(genre["name"], userData=genre["id"])

        # Restore previous selection if still valid
        if current_data is not None:
            for i in range(self.genre_filter.count()):
                if self.genre_filter.itemData(i) == current_data:
                    self.genre_filter.setCurrentIndex(i)
                    break

        self.genre_filter.blockSignals(False)

    def refresh_tags_filter(self):
        """Reload the tag filter dropdown from the database."""
        current_data = self.tag_filter.currentData()
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("All Tags", userData=None)

        tags = self.db.get_all_tags()
        for tag in tags:
            self.tag_filter.addItem(tag["name"], userData=tag["id"])

        # Restore previous selection if still valid
        if current_data is not None:
            for i in range(self.tag_filter.count()):
                if self.tag_filter.itemData(i) == current_data:
                    self.tag_filter.setCurrentIndex(i)
                    break

        self.tag_filter.blockSignals(False)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _on_search_text_changed(self):
        """Restart the debounce timer when the user types in the search box."""
        self._search_timer.stop()
        self._search_timer.start()

    def apply_filters(self):
        """Filter self.all_songs by the current search text, genre, status,
        and tag, then repopulate the table."""
        search_text = self.search_box.text().strip().lower()
        genre_id = self.genre_filter.currentData()
        status = self.status_filter.currentData()
        tag_id = self.tag_filter.currentData()

        filtered = self.all_songs

        # Genre filter
        if genre_id is not None:
            filtered = [s for s in filtered if s.get("genre_id") == genre_id]

        # Status filter
        if status is not None:
            filtered = [s for s in filtered if s.get("status") == status]

        # Tag filter
        if tag_id is not None:
            tagged_songs = self.db.get_songs_by_tag(tag_id)
            tagged_ids = {s["id"] for s in tagged_songs}
            filtered = [s for s in filtered if s.get("id") in tagged_ids]

        # Search filter (across title, lyrics, prompt)
        if search_text:
            filtered = [
                s for s in filtered
                if search_text in (s.get("title") or "").lower()
                or search_text in (s.get("lyrics") or "").lower()
                or search_text in (s.get("prompt") or "").lower()
            ]

        self.filtered_songs = filtered
        self.populate_table(filtered)

    # ------------------------------------------------------------------
    # Table population
    # ------------------------------------------------------------------

    def populate_table(self, songs: list[dict]):
        """Fill the table widget with the given list of songs."""
        self.table.setRowCount(0)
        self.table.setRowCount(len(songs))

        for row_idx, song in enumerate(songs):
            # Title
            title_item = QTableWidgetItem(song.get("title", ""))
            title_item.setData(Qt.ItemDataRole.UserRole, song.get("id"))
            self.table.setItem(row_idx, 0, title_item)

            # Genre
            genre_text = song.get("genre_label") or ""
            genre_item = QTableWidgetItem(genre_text)
            self.table.setItem(row_idx, 1, genre_item)

            # Tags (colored chips)
            song_id = song.get("id")
            tags = self.db.get_tags_for_song(song_id) if song_id else []
            chips = TagChipsWidget(tags)
            self.table.setCellWidget(row_idx, 2, chips)

            # Status (colored badge)
            status_val = song.get("status", "draft")
            badge = StatusBadgeWidget(status_val)
            self.table.setCellWidget(row_idx, 3, badge)

            # Created
            created = song.get("created_at", "")
            if created and len(created) > 16:
                created = created[:16]  # trim seconds
            created_item = QTableWidgetItem(created)
            self.table.setItem(row_idx, 4, created_item)

            # Actions column: small buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            # Play button — only enabled if file exists
            file_path_1 = song.get("file_path_1", "")
            play_btn = QPushButton("Play")
            play_btn.setFixedSize(46, 24)
            if file_path_1 and os.path.exists(file_path_1):
                play_btn.setStyleSheet(
                    "font-size: 11px; padding: 2px 6px; background-color: #4CAF50;"
                    "color: #FFFFFF; border: none; border-radius: 3px; font-weight: bold;"
                )
                play_btn.clicked.connect(
                    lambda checked, fp=file_path_1: self._context_play_song(fp)
                )
            else:
                play_btn.setStyleSheet(
                    "font-size: 11px; padding: 2px 6px; background-color: #3a3a3a;"
                    "color: #666666; border: none; border-radius: 3px; font-weight: bold;"
                )
                play_btn.setEnabled(False)
            actions_layout.addWidget(play_btn)

            # Vocals button — only shown if file exists
            fp_vocals = song.get("file_path_vocals", "")
            if fp_vocals and os.path.exists(fp_vocals):
                voc_btn = QPushButton("Voc")
                voc_btn.setFixedSize(40, 24)
                voc_btn.setStyleSheet(
                    "font-size: 11px; padding: 2px 4px; background-color: #2196F3;"
                    "color: #FFFFFF; border: none; border-radius: 3px; font-weight: bold;"
                )
                voc_btn.clicked.connect(
                    lambda checked, fp=fp_vocals: self._context_play_song(fp)
                )
                actions_layout.addWidget(voc_btn)

            # Instrumental button — only shown if file exists
            fp_inst = song.get("file_path_instrumental", "")
            if fp_inst and os.path.exists(fp_inst):
                inst_btn = QPushButton("Inst")
                inst_btn.setFixedSize(40, 24)
                inst_btn.setStyleSheet(
                    "font-size: 11px; padding: 2px 4px; background-color: #9C27B0;"
                    "color: #FFFFFF; border: none; border-radius: 3px; font-weight: bold;"
                )
                inst_btn.clicked.connect(
                    lambda checked, fp=fp_inst: self._context_play_song(fp)
                )
                actions_layout.addWidget(inst_btn)

            view_btn = QPushButton("View")
            view_btn.setFixedSize(46, 24)
            view_btn.setStyleSheet(
                f"font-size: 11px; padding: 2px 6px; background-color: {Theme.ACCENT};"
                "color: #000000; border: none; border-radius: 3px; font-weight: bold;"
            )
            view_btn.clicked.connect(lambda checked, r=row_idx: self._select_row(r))
            actions_layout.addWidget(view_btn)

            del_btn = QPushButton("Del")
            del_btn.setFixedSize(40, 24)
            del_btn.setStyleSheet(
                "font-size: 11px; padding: 2px 6px; background-color: #F44336;"
                "color: #FFFFFF; border: none; border-radius: 3px; font-weight: bold;"
            )
            del_btn.clicked.connect(lambda checked, sid=song.get("id"): self._quick_delete(sid))
            actions_layout.addWidget(del_btn)

            self.table.setCellWidget(row_idx, 5, actions_widget)

            # Set row height
            self.table.setRowHeight(row_idx, 36)

        # Hide detail area when table is repopulated (selection is lost)
        self.detail_frame.setVisible(False)
        self.selected_song = None

    # ------------------------------------------------------------------
    # Row selection / Detail area
    # ------------------------------------------------------------------

    def _select_row(self, row: int):
        """Programmatically select a table row and trigger detail display."""
        if 0 <= row < self.table.rowCount():
            self.table.selectRow(row)

    def on_row_selected(self):
        """Display the detail area for the currently selected song."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self.detail_frame.setVisible(False)
            self.selected_song = None
            return

        row_idx = selected_rows[0].row()
        if row_idx < 0 or row_idx >= len(self.filtered_songs):
            self.detail_frame.setVisible(False)
            self.selected_song = None
            return

        song = self.filtered_songs[row_idx]
        # Re-fetch from db in case something changed
        fresh = self.db.get_song(song["id"])
        if fresh is None:
            self.detail_frame.setVisible(False)
            self.selected_song = None
            return

        self.selected_song = fresh
        self.detail_title_label.setText(
            f"{fresh.get('title', 'Untitled')}  [{fresh.get('status', '')}]"
        )
        self.prompt_edit.setPlainText(fresh.get("prompt") or "")
        self.lyrics_edit.setPlainText(fresh.get("lyrics") or "")
        self._update_detail_tags(fresh["id"])
        self.detail_frame.setVisible(True)

    # ------------------------------------------------------------------
    # Detail area actions
    # ------------------------------------------------------------------

    def save_changes(self):
        """Persist prompt and lyrics edits for the selected song."""
        if self.selected_song is None:
            return

        song_id = self.selected_song["id"]
        new_prompt = self.prompt_edit.toPlainText()
        new_lyrics = self.lyrics_edit.toPlainText()

        updated = self.db.update_song(
            song_id,
            prompt=new_prompt,
            lyrics=new_lyrics,
        )

        if updated:
            QMessageBox.information(self, "Saved", "Song changes saved successfully.")
            self._refresh_after_edit(song_id)
        else:
            QMessageBox.warning(self, "Error", "Failed to save changes.")

    def requeue_song(self):
        """Set the selected song's status to 'queued' and refresh."""
        if self.selected_song is None:
            return

        song_id = self.selected_song["id"]
        updated = self.db.update_song(song_id, status="queued")

        if updated:
            QMessageBox.information(self, "Re-queued", "Song status set to 'queued'.")
            self._refresh_after_edit(song_id)
        else:
            QMessageBox.warning(self, "Error", "Failed to re-queue song.")

    def delete_song(self):
        """Delete the selected song after user confirmation."""
        if self.selected_song is None:
            return

        song_id = self.selected_song["id"]
        title = self.selected_song.get("title", "Untitled")

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete \"{title}\"?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted = self.db.delete_song(song_id)
            if deleted:
                self.selected_song = None
                self.detail_frame.setVisible(False)
                self.load_songs()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete song.")

    def _quick_delete(self, song_id: int):
        """Delete a song directly from the table actions column."""
        song = self.db.get_song(song_id)
        if song is None:
            return

        title = song.get("title", "Untitled")

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete \"{title}\"?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted = self.db.delete_song(song_id)
            if deleted:
                if self.selected_song and self.selected_song["id"] == song_id:
                    self.selected_song = None
                    self.detail_frame.setVisible(False)
                self.load_songs()

    def _copy_prompt(self):
        """Copy the prompt text to the system clipboard."""
        text = self.prompt_edit.toPlainText()
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def _copy_lyrics(self):
        """Copy the lyrics text to the system clipboard."""
        text = self.lyrics_edit.toPlainText()
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    def _get_selected_song_ids(self) -> list[int]:
        """Return song IDs for all selected table rows."""
        selected_rows = set()
        for index in self.table.selectionModel().selectedRows():
            selected_rows.add(index.row())

        song_ids = []
        for row in sorted(selected_rows):
            if 0 <= row < len(self.filtered_songs):
                song_id = self.filtered_songs[row].get("id")
                if song_id is not None:
                    song_ids.append(song_id)
        return song_ids

    def _update_batch_bar(self):
        """Show/hide batch action buttons based on selection count."""
        ids = self._get_selected_song_ids()
        count = len(ids)
        show_batch = count > 1

        self.batch_delete_btn.setVisible(show_batch)
        self.batch_status_btn.setVisible(show_batch)
        self.batch_export_btn.setVisible(show_batch)
        self.batch_selection_label.setVisible(show_batch)

        if show_batch:
            self.batch_selection_label.setText(f"{count} songs selected")

    def _batch_delete(self):
        """Delete all selected songs after confirmation."""
        ids = self._get_selected_song_ids()
        if not ids:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Batch Delete",
            f"Are you sure you want to delete {len(ids)} selected song(s)?\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        for song_id in ids:
            if self.db.delete_song(song_id):
                deleted += 1

        QMessageBox.information(
            self, "Batch Delete", f"Deleted {deleted} of {len(ids)} songs."
        )
        self.selected_song = None
        self.detail_frame.setVisible(False)
        self.load_songs()

    def _batch_set_status(self):
        """Set status for all selected songs."""
        ids = self._get_selected_song_ids()
        if not ids:
            return

        from PyQt6.QtWidgets import QInputDialog
        statuses = ["draft", "queued", "completed", "error"]
        status, ok = QInputDialog.getItem(
            self,
            "Set Status",
            f"Choose status for {len(ids)} selected song(s):",
            statuses,
            0,
            False,
        )
        if not ok:
            return

        updated = 0
        for song_id in ids:
            if self.db.update_song(song_id, status=status):
                updated += 1

        QMessageBox.information(
            self, "Batch Status", f"Updated {updated} of {len(ids)} songs to '{status}'."
        )
        self.load_songs()

    def _batch_export(self):
        """Export selected songs to a JSON file."""
        ids = self._get_selected_song_ids()
        if not ids:
            return

        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Selected Songs",
            os.path.expanduser("~/songs_export.json"),
            "JSON Files (*.json)",
        )
        if not path:
            return

        try:
            from export_import import export_json
            export_json(self.db, path, songs=True, lore=False, genres=False, song_ids=ids)
            QMessageBox.information(
                self, "Export Complete", f"Exported {len(ids)} songs to:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Error: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_after_edit(self, song_id: int):
        """Reload songs from the database and re-select the edited song."""
        self.all_songs = self.db.get_all_songs()
        self.apply_filters()
        self._update_queue_count()

        # Attempt to re-select the same song
        for row_idx, song in enumerate(self.filtered_songs):
            if song.get("id") == song_id:
                self.table.selectRow(row_idx)
                return

        # Song no longer visible (filtered out) -- hide detail
        self.detail_frame.setVisible(False)
        self.selected_song = None

    # ------------------------------------------------------------------
    # Tag helpers
    # ------------------------------------------------------------------

    def _update_detail_tags(self, song_id: int):
        """Refresh the tag chips shown in the detail area."""
        # Clear existing widgets
        while self.detail_tags_layout.count():
            child = self.detail_tags_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        tags = self.db.get_tags_for_song(song_id)
        chips = TagChipsWidget(tags)
        self.detail_tags_layout.addWidget(chips)

    def _toggle_song_tag(self, song_id: int, tag_id: int, checked: bool):
        """Context menu action: add or remove a tag from a song."""
        if checked:
            self.db.add_tag_to_song(song_id, tag_id)
        else:
            self.db.remove_tag_from_song(song_id, tag_id)
        event_bus.tags_changed.emit()
        self._refresh_after_edit(song_id)

    def _create_and_assign_tag(self, song_id: int):
        """Context menu action: create a new tag and assign it to a song."""
        name, ok = QInputDialog.getText(
            self, "New Tag", "Tag name:"
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        try:
            tag_id = self.db.add_tag(name)
        except Exception:
            QMessageBox.warning(
                self, "Duplicate Tag", f'A tag named "{name}" already exists.'
            )
            return
        self.db.add_tag_to_song(song_id, tag_id)
        event_bus.tags_changed.emit()
        self._refresh_after_edit(song_id)

    def _edit_song_tags(self):
        """Open a checkable tag dialog for the selected song."""
        if self.selected_song is None:
            return
        song_id = self.selected_song["id"]
        all_tags = self.db.get_all_tags()
        song_tags = self.db.get_tags_for_song(song_id)
        song_tag_ids = {t["id"] for t in song_tags}

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Tags")
        dlg.setMinimumWidth(280)
        layout = QVBoxLayout(dlg)

        tag_list = QListWidget()
        for tag in all_tags:
            item = QListWidgetItem(tag["name"])
            item.setData(Qt.ItemDataRole.UserRole, tag["id"])
            item.setCheckState(
                Qt.CheckState.Checked if tag["id"] in song_tag_ids
                else Qt.CheckState.Unchecked
            )
            item.setForeground(QColor(tag.get("color", "#888888")))
            tag_list.addItem(item)
        layout.addWidget(tag_list)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_ids = []
            for i in range(tag_list.count()):
                item = tag_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    new_ids.append(item.data(Qt.ItemDataRole.UserRole))
            self.db.set_song_tags(song_id, new_ids)
            event_bus.tags_changed.emit()
            self._update_detail_tags(song_id)
            self._refresh_after_edit(song_id)

    def _open_manage_tags(self):
        """Open the Manage Tags dialog."""
        dlg = ManageTagsDialog(self.db, parent=self)
        dlg.exec()
        event_bus.tags_changed.emit()
        self.refresh_tags_filter()
        # Refresh table to show any tag renames / color changes
        self.apply_filters()


class ManageTagsDialog(QDialog):
    """Dialog for adding, renaming, recoloring, and deleting tags."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Manage Tags")
        self.setMinimumSize(360, 320)
        self._build_ui()
        self._load_tags()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.tag_list = QListWidget()
        layout.addWidget(self.tag_list)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.rename_btn = QPushButton("Rename")
        self.color_btn = QPushButton("Color")
        self.delete_btn = QPushButton("Delete")
        self.close_btn = QPushButton("Close")

        for btn in (self.add_btn, self.rename_btn, self.color_btn,
                    self.delete_btn, self.close_btn):
            btn_row.addWidget(btn)

        layout.addLayout(btn_row)

        self.add_btn.clicked.connect(self._add_tag)
        self.rename_btn.clicked.connect(self._rename_tag)
        self.color_btn.clicked.connect(self._change_color)
        self.delete_btn.clicked.connect(self._delete_tag)
        self.close_btn.clicked.connect(self.accept)

    def _load_tags(self):
        self.tag_list.clear()
        tags = self.db.get_all_tags()
        for tag in tags:
            label = tag["name"]
            if tag.get("is_builtin"):
                label += "  (built-in)"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, tag["id"])
            item.setData(Qt.ItemDataRole.UserRole + 1, tag.get("is_builtin", 0))
            color = tag.get("color", "#888888")
            item.setForeground(QColor(color))
            self.tag_list.addItem(item)

    def _selected_tag_id(self):
        item = self.tag_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _add_tag(self):
        name, ok = QInputDialog.getText(self, "New Tag", "Tag name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        color = QColorDialog.getColor(QColor("#888888"), self, "Tag Color")
        if not color.isValid():
            return
        try:
            self.db.add_tag(name, color.name())
        except Exception:
            QMessageBox.warning(
                self, "Duplicate", f'Tag "{name}" already exists.'
            )
            return
        self._load_tags()

    def _rename_tag(self):
        tag_id = self._selected_tag_id()
        if tag_id is None:
            return
        name, ok = QInputDialog.getText(self, "Rename Tag", "New name:")
        if not ok or not name.strip():
            return
        try:
            self.db.update_tag(tag_id, name=name.strip())
        except Exception:
            QMessageBox.warning(
                self, "Error", f'Could not rename: "{name.strip()}" may already exist.'
            )
            return
        self._load_tags()

    def _change_color(self):
        tag_id = self._selected_tag_id()
        if tag_id is None:
            return
        color = QColorDialog.getColor(QColor("#888888"), self, "Tag Color")
        if not color.isValid():
            return
        self.db.update_tag(tag_id, color=color.name())
        self._load_tags()

    def _delete_tag(self):
        tag_id = self._selected_tag_id()
        if tag_id is None:
            return
        item = self.tag_list.currentItem()
        is_builtin = item.data(Qt.ItemDataRole.UserRole + 1)
        if is_builtin:
            QMessageBox.information(
                self, "Cannot Delete", "Built-in tags cannot be deleted."
            )
            return
        reply = QMessageBox.question(
            self,
            "Delete Tag",
            "Delete this tag? It will be removed from all songs.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_tag(tag_id)
            self._load_tags()

"""
Song Factory - Distribution Tab

Provides a DistributionTab widget with a 3-panel layout:
- Left: Distribution queue (list of distributions by status)
- Center: Release form (song, artist, title, songwriter, genre, cover art, etc.)
- Right: Status log and upload controls
"""

import os
from datetime import date
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
    QListWidgetItem, QPushButton, QLabel, QLineEdit, QComboBox,
    QCheckBox, QTextEdit, QDateEdit, QGroupBox, QFormLayout,
    QFileDialog, QMessageBox, QProgressBar, QFrame, QScrollArea,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QPixmap, QColor

# Guard imports
try:
    from automation.distrokid_worker import DistroKidWorker
    _HAS_DK_WORKER = True
except ImportError:
    _HAS_DK_WORKER = False

try:
    from automation.cover_art_preparer import validate_cover_art, prepare_cover_art
    _HAS_COVER_ART = True
except ImportError:
    _HAS_COVER_ART = False

from automation.distrokid_driver import GENRE_MAP, map_genre
from tabs.base_tab import BaseTab
from theme import Theme


class DistributionTab(BaseTab):
    """Distribution management tab for uploading songs to DistroKid."""

    def __init__(self, db, parent=None):
        self._worker = None
        self._current_dist_id = None
        super().__init__(db, parent)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Left panel: Distribution queue ----
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        queue_label = QLabel("Distribution Queue")
        queue_label.setStyleSheet(
            f"color: {Theme.ACCENT}; font-weight: bold; font-size: 14px;"
        )
        left_layout.addWidget(queue_label)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All", "all")
        for status in ("draft", "ready", "uploading", "submitted", "live", "error"):
            self.filter_combo.addItem(status.capitalize(), status)
        self.filter_combo.currentIndexChanged.connect(self.load_distributions)
        left_layout.addWidget(self.filter_combo)

        self.dist_list = QListWidget()
        self.dist_list.currentRowChanged.connect(self._on_dist_selected)
        left_layout.addWidget(self.dist_list, 1)

        btn_row = QHBoxLayout()
        self.new_btn = QPushButton("New")
        self.new_btn.clicked.connect(self._new_distribution)
        btn_row.addWidget(self.new_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_distribution)
        btn_row.addWidget(self.delete_btn)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left)

        # ---- Center panel: Release form ----
        center = QWidget()
        center_scroll = QScrollArea()
        center_scroll.setWidgetResizable(True)
        center_scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(8, 8, 8, 8)
        form_layout.setSpacing(8)

        form_label = QLabel("Release Details")
        form_label.setStyleSheet(
            f"color: {Theme.ACCENT}; font-weight: bold; font-size: 14px;"
        )
        form_layout.addWidget(form_label)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Song selection
        self.song_combo = QComboBox()
        self.song_combo.currentIndexChanged.connect(self._on_song_changed)
        form.addRow("Song:", self.song_combo)

        # Artist
        self.artist_edit = QLineEdit()
        self.artist_edit.setPlaceholderText("Yakima Finds")
        form.addRow("Artist:", self.artist_edit)

        # Release title
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Release title (defaults to song title)")
        form.addRow("Release Title:", self.title_edit)

        # Songwriter
        self.songwriter_edit = QLineEdit()
        self.songwriter_edit.setPlaceholderText("Legal name of songwriter")
        form.addRow("Songwriter:", self.songwriter_edit)

        # Genre
        self.genre_combo = QComboBox()
        self._populate_genres()
        form.addRow("Genre:", self.genre_combo)

        # Language
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "English", "Spanish", "French", "Portuguese", "German",
            "Italian", "Japanese", "Korean", "Chinese", "Hindi",
            "Arabic", "Russian",
        ])
        form.addRow("Language:", self.language_combo)

        # Cover art
        art_row = QHBoxLayout()
        self.art_path_edit = QLineEdit()
        self.art_path_edit.setPlaceholderText("Path to cover art (3000x3000 JPG/PNG)")
        art_row.addWidget(self.art_path_edit, 1)

        self.art_browse_btn = QPushButton("Browse...")
        self.art_browse_btn.clicked.connect(self._browse_cover_art)
        art_row.addWidget(self.art_browse_btn)

        self.art_validate_btn = QPushButton("Validate")
        self.art_validate_btn.clicked.connect(self._validate_cover_art)
        art_row.addWidget(self.art_validate_btn)
        form.addRow("Cover Art:", art_row)

        # Art preview
        self.art_preview = QLabel()
        self.art_preview.setFixedSize(150, 150)
        self.art_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art_preview.setStyleSheet(
            f"background-color: {Theme.PANEL}; border: 1px solid #555555; border-radius: 4px;"
        )
        self.art_preview.setText("No art")
        form.addRow("", self.art_preview)

        # Instrumental
        self.instrumental_check = QCheckBox("This is an instrumental (no vocals)")
        form.addRow("", self.instrumental_check)

        # AI Disclosure
        self.ai_check = QCheckBox("This music was generated with AI")
        self.ai_check.setChecked(True)
        form.addRow("", self.ai_check)

        # Release date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Release Date:", self.date_edit)

        # Record label
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Optional record label")
        form.addRow("Record Label:", self.label_edit)

        # Lyrics
        lyrics_label = QLabel("Lyrics (submitted as plain text):")
        lyrics_label.setStyleSheet("font-weight: bold;")
        form.addRow(lyrics_label)

        self.lyrics_edit = QTextEdit()
        self.lyrics_edit.setMaximumHeight(150)
        self.lyrics_edit.setPlaceholderText("Lyrics will auto-populate from the song...")
        form.addRow(self.lyrics_edit)

        # Notes
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Optional notes")
        form.addRow("Notes:", self.notes_edit)

        form_layout.addLayout(form)

        # Form buttons
        form_btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save Draft")
        self.save_btn.setStyleSheet(
            f"background-color: {Theme.ACCENT}; color: #1a1a1a; font-weight: bold; "
            "border: none; border-radius: 6px; padding: 10px 24px;"
        )
        self.save_btn.clicked.connect(self._save_draft)
        form_btn_row.addWidget(self.save_btn)

        self.mark_ready_btn = QPushButton("Mark Ready")
        self.mark_ready_btn.clicked.connect(self._mark_ready)
        form_btn_row.addWidget(self.mark_ready_btn)

        form_btn_row.addStretch()
        form_layout.addLayout(form_btn_row)
        form_layout.addStretch()

        center_scroll.setWidget(form_widget)

        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(center_scroll)

        splitter.addWidget(center)

        # ---- Right panel: Status & Log ----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        status_label = QLabel("Upload Status")
        status_label.setStyleSheet(
            f"color: {Theme.ACCENT}; font-weight: bold; font-size: 14px;"
        )
        right_layout.addWidget(status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)

        self.status_display = QLabel("Idle")
        self.status_display.setWordWrap(True)
        self.status_display.setStyleSheet("font-size: 13px; padding: 4px;")
        right_layout.addWidget(self.status_display)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Upload log will appear here...")
        right_layout.addWidget(self.log_text, 1)

        # Upload controls
        ctrl_row = QHBoxLayout()

        self.login_btn = QPushButton("Login to DK")
        self.login_btn.setToolTip(
            "Open browser and log in to DistroKid.\n"
            "Complete 2FA in the browser window."
        )
        self.login_btn.clicked.connect(self._start_upload)
        ctrl_row.addWidget(self.login_btn)

        self.upload_btn = QPushButton("Upload Now")
        self.upload_btn.setStyleSheet(
            f"background-color: {Theme.ACCENT}; color: #1a1a1a; font-weight: bold; "
            "border: none; border-radius: 6px; padding: 10px 24px;"
        )
        self.upload_btn.clicked.connect(self._start_upload)
        ctrl_row.addWidget(self.upload_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_upload)
        ctrl_row.addWidget(self.stop_btn)

        right_layout.addLayout(ctrl_row)

        splitter.addWidget(right)

        # Set initial sizes (left: 250, center: 500, right: 300)
        splitter.setSizes([250, 500, 300])

        layout.addWidget(splitter)

    # ------------------------------------------------------------------
    # Genre population
    # ------------------------------------------------------------------

    def _populate_genres(self):
        """Fill the genre combo with Song Factory genres + DK mapping."""
        self.genre_combo.clear()
        genres = self.db.get_all_genres()
        for g in genres:
            name = g["name"]
            dk = map_genre(name)
            self.genre_combo.addItem(f"{name} -> {dk}", name)

    # ------------------------------------------------------------------
    # Signals & Refresh
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Initial data load after UI and signals are ready."""
        self.load_distributions()

    def refresh(self) -> None:
        """Reload distribution data (called by app.py on tab activation)."""
        self.load_distributions()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_distributions(self):
        """Reload the distribution list from the database."""
        self.dist_list.clear()
        self._refresh_song_combo()

        status_filter = self.filter_combo.currentData()
        if status_filter == "all":
            dists = self.db.get_all_distributions()
        else:
            dists = self.db.get_distributions_by_status(status_filter)

        for d in dists:
            # Get the song title
            song = self.db.get_song(d["song_id"])
            song_title = song["title"] if song else f"Song #{d['song_id']}"
            status = d.get("status", "draft")
            color = Theme.DIST_STATUS_COLORS.get(status, "#888888")

            item = QListWidgetItem(f"[{status}] {song_title}")
            item.setData(Qt.ItemDataRole.UserRole, d["id"])
            item.setForeground(QColor(color))
            self.dist_list.addItem(item)

    def _refresh_song_combo(self):
        """Populate the song dropdown with completed songs."""
        current_data = self.song_combo.currentData()
        self.song_combo.blockSignals(True)
        self.song_combo.clear()
        self.song_combo.addItem("-- Select a song --", None)

        songs = self.db.get_all_songs()
        for s in songs:
            # Show all songs but prefer completed ones
            status = s.get("status", "draft")
            has_file = bool(s.get("file_path_1"))
            label = f"{s['title']} [{status}]"
            if has_file:
                label += " (has audio)"
            self.song_combo.addItem(label, s["id"])

        # Restore selection
        if current_data is not None:
            for i in range(self.song_combo.count()):
                if self.song_combo.itemData(i) == current_data:
                    self.song_combo.setCurrentIndex(i)
                    break

        self.song_combo.blockSignals(False)

    def _on_dist_selected(self, row):
        """Load the selected distribution into the form."""
        if row < 0:
            self._current_dist_id = None
            self._clear_form()
            return

        item = self.dist_list.item(row)
        if not item:
            return

        dist_id = item.data(Qt.ItemDataRole.UserRole)
        self._current_dist_id = dist_id
        dist = self.db.get_distribution(dist_id)
        if not dist:
            return

        self._populate_form(dist)

    def _populate_form(self, dist: dict):
        """Fill the form fields from a distribution record."""
        # Song combo
        song_id = dist.get("song_id")
        for i in range(self.song_combo.count()):
            if self.song_combo.itemData(i) == song_id:
                self.song_combo.setCurrentIndex(i)
                break

        self.artist_edit.setText(dist.get("artist_name", "Yakima Finds"))
        self.title_edit.setText(dist.get("album_title", ""))
        self.songwriter_edit.setText(dist.get("songwriter", ""))

        # Genre
        genre = dist.get("primary_genre", "")
        for i in range(self.genre_combo.count()):
            if self.genre_combo.itemData(i) == genre:
                self.genre_combo.setCurrentIndex(i)
                break

        # Language
        lang = dist.get("language", "English")
        idx = self.language_combo.findText(lang)
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)

        self.art_path_edit.setText(dist.get("cover_art_path", ""))
        self._update_art_preview(dist.get("cover_art_path", ""))

        self.instrumental_check.setChecked(bool(dist.get("is_instrumental", 0)))
        self.ai_check.setChecked(bool(dist.get("ai_disclosure", 1)))

        # Date
        date_str = dist.get("release_date", "")
        if date_str:
            qdate = QDate.fromString(date_str, "yyyy-MM-dd")
            if qdate.isValid():
                self.date_edit.setDate(qdate)
        else:
            self.date_edit.setDate(QDate.currentDate())

        self.label_edit.setText(dist.get("record_label", ""))
        self.lyrics_edit.setPlainText(dist.get("lyrics_submitted", ""))
        self.notes_edit.setText(dist.get("notes", ""))

    def _clear_form(self):
        """Reset all form fields."""
        self.song_combo.setCurrentIndex(0)
        self.artist_edit.setText(self.db.get_config("dk_artist", "Yakima Finds"))
        self.title_edit.clear()
        self.songwriter_edit.setText(self.db.get_config("dk_songwriter", ""))
        self.genre_combo.setCurrentIndex(0)
        self.language_combo.setCurrentIndex(0)
        self.art_path_edit.clear()
        self.art_preview.setPixmap(QPixmap())
        self.art_preview.setText("No art")
        self.instrumental_check.setChecked(False)
        self.ai_check.setChecked(True)
        self.date_edit.setDate(QDate.currentDate())
        self.label_edit.clear()
        self.lyrics_edit.clear()
        self.notes_edit.clear()

    def _on_song_changed(self, index):
        """Auto-populate fields when a song is selected."""
        song_id = self.song_combo.currentData()
        if song_id is None:
            return

        song = self.db.get_song(song_id)
        if not song:
            return

        # Auto-fill title if empty
        if not self.title_edit.text().strip():
            self.title_edit.setText(song.get("title", ""))

        # Auto-fill genre
        genre_label = song.get("genre_label", "")
        for i in range(self.genre_combo.count()):
            if self.genre_combo.itemData(i) == genre_label:
                self.genre_combo.setCurrentIndex(i)
                break

        # Auto-fill lyrics
        lyrics = song.get("lyrics", "")
        if lyrics and not self.lyrics_edit.toPlainText().strip():
            self.lyrics_edit.setPlainText(lyrics)

    # ------------------------------------------------------------------
    # Cover art
    # ------------------------------------------------------------------

    def _browse_cover_art(self):
        """Open file picker for cover art."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Cover Art",
            os.path.expanduser("~"),
            "Images (*.jpg *.jpeg *.png);;All Files (*)",
        )
        if path:
            self.art_path_edit.setText(path)
            self._update_art_preview(path)

    def _update_art_preview(self, path: str):
        """Show a thumbnail preview of the cover art."""
        if path and os.path.isfile(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    150, 150,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.art_preview.setPixmap(scaled)
                self.art_preview.setText("")
                return
        self.art_preview.setPixmap(QPixmap())
        self.art_preview.setText("No art")

    def _validate_cover_art(self):
        """Validate the cover art file."""
        path = self.art_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a cover art file first.")
            return

        if not _HAS_COVER_ART:
            QMessageBox.warning(
                self, "Missing Dependency",
                "Cover art validation requires Pillow.\n"
                "Install with: pip install Pillow --break-system-packages"
            )
            return

        info = validate_cover_art(path)
        if info["valid"]:
            msg = (
                f"Cover art is valid.\n\n"
                f"Size: {info['width']}x{info['height']}\n"
                f"Format: {info['format']}"
            )
            if info["width"] != 3000 or info["height"] != 3000:
                msg += "\n\nNote: Will be resized to 3000x3000 before upload."
            QMessageBox.information(self, "Valid", msg)
        else:
            QMessageBox.warning(
                self, "Invalid Cover Art",
                "Issues found:\n\n" + "\n".join(f"- {e}" for e in info["errors"])
            )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _new_distribution(self):
        """Create a new distribution draft."""
        songwriter = self.db.get_config("dk_songwriter", "")
        if not songwriter:
            QMessageBox.warning(
                self, "Songwriter Required",
                "Please set a default songwriter in Settings > DistroKid first.\n"
                "DistroKid requires the songwriter's legal name."
            )
            return

        song_id = self.song_combo.currentData()
        if song_id is None:
            QMessageBox.warning(
                self, "No Song Selected",
                "Please select a song from the dropdown."
            )
            return

        artist = self.db.get_config("dk_artist", "Yakima Finds")
        song = self.db.get_song(song_id)
        genre_name = self.genre_combo.currentData() or "Pop"

        dist_id = self.db.add_distribution(
            song_id=song_id,
            songwriter=songwriter,
            artist_name=artist,
            album_title=song["title"] if song else "",
            primary_genre=genre_name,
            lyrics_submitted=song.get("lyrics", "") if song else "",
        )

        self._log(f"Created distribution #{dist_id}")
        self.load_distributions()

        # Select the new item
        for i in range(self.dist_list.count()):
            item = self.dist_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == dist_id:
                self.dist_list.setCurrentRow(i)
                break

    def _save_draft(self):
        """Save the current form to the database."""
        if self._current_dist_id is None:
            QMessageBox.warning(self, "No Selection", "Select or create a distribution first.")
            return

        song_id = self.song_combo.currentData()
        if song_id is None:
            QMessageBox.warning(self, "No Song", "Please select a song.")
            return

        kwargs = {
            "song_id": song_id,
            "artist_name": self.artist_edit.text().strip() or "Yakima Finds",
            "album_title": self.title_edit.text().strip(),
            "songwriter": self.songwriter_edit.text().strip(),
            "primary_genre": self.genre_combo.currentData() or "Pop",
            "language": self.language_combo.currentText(),
            "cover_art_path": self.art_path_edit.text().strip(),
            "is_instrumental": 1 if self.instrumental_check.isChecked() else 0,
            "ai_disclosure": 1 if self.ai_check.isChecked() else 0,
            "release_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "record_label": self.label_edit.text().strip(),
            "lyrics_submitted": self.lyrics_edit.toPlainText(),
            "notes": self.notes_edit.text().strip(),
        }

        self.db.update_distribution(self._current_dist_id, **kwargs)
        self._log(f"Saved distribution #{self._current_dist_id}")
        self.load_distributions()

    def _mark_ready(self):
        """Mark the current distribution as ready for upload."""
        if self._current_dist_id is None:
            return

        # Validate required fields
        dist = self.db.get_distribution(self._current_dist_id)
        if not dist:
            return

        errors = []
        if not dist.get("songwriter"):
            errors.append("Songwriter is required")
        if not dist.get("cover_art_path"):
            errors.append("Cover art is required")

        song = self.db.get_song(dist["song_id"])
        if not song or not song.get("file_path_1"):
            errors.append("Song must have an audio file")

        if errors:
            QMessageBox.warning(
                self, "Cannot Mark Ready",
                "Fix these issues first:\n\n" + "\n".join(f"- {e}" for e in errors)
            )
            return

        # Save first, then mark ready
        self._save_draft()
        self.db.update_distribution(self._current_dist_id, status="ready")
        self._log(f"Distribution #{self._current_dist_id} marked as ready")
        self.load_distributions()

    def _delete_distribution(self):
        """Delete the selected distribution."""
        if self._current_dist_id is None:
            return

        confirm = QMessageBox.question(
            self, "Delete Distribution",
            "Delete this distribution record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.db.delete_distribution(self._current_dist_id)
        self._log(f"Deleted distribution #{self._current_dist_id}")
        self._current_dist_id = None
        self._clear_form()
        self.load_distributions()

    # ------------------------------------------------------------------
    # Upload controls
    # ------------------------------------------------------------------

    def _start_upload(self):
        """Start the DistroKid upload worker."""
        if not _HAS_DK_WORKER:
            QMessageBox.warning(
                self, "Missing Dependency",
                "DistroKid upload requires Playwright.\n"
                "Install with: pip install playwright && playwright install chromium"
            )
            return

        if self._worker and self._worker.isRunning():
            QMessageBox.information(
                self, "Already Running",
                "An upload is already in progress."
            )
            return

        # Collect ready distributions (or just the current one if it's ready)
        ready = self.db.get_distributions_by_status("ready")
        if not ready:
            # If current is a draft, offer to mark ready first
            if self._current_dist_id:
                dist = self.db.get_distribution(self._current_dist_id)
                if dist and dist["status"] == "draft":
                    answer = QMessageBox.question(
                        self, "Not Ready",
                        "This distribution is still a draft.\n"
                        "Mark it as ready and upload?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if answer == QMessageBox.StandardButton.Yes:
                        self._mark_ready()
                        ready = self.db.get_distributions_by_status("ready")

            if not ready:
                QMessageBox.information(
                    self, "Nothing to Upload",
                    "No distributions are marked as ready.\n"
                    "Mark a distribution as 'Ready' first."
                )
                return

        dist_ids = [d["id"] for d in ready]

        config = {
            "download_dir": self.db.get_config(
                "download_dir",
                os.path.join(os.path.expanduser("~"), "Music", "SongFactory"),
            ),
            "browser_path": self.db.get_config("browser_path", ""),
            "use_xvfb": self.db.get_config("use_xvfb", "false").lower() == "true",
        }

        self._worker = DistroKidWorker(
            db_path=self.db._db_path,
            config=config,
            dist_ids=dist_ids,
        )
        self.register_worker(self._worker)
        self._worker.upload_started.connect(self._on_upload_started)
        self._worker.upload_completed.connect(self._on_upload_completed)
        self._worker.upload_error.connect(self._on_upload_error)
        self._worker.progress_update.connect(self._on_progress)
        self._worker.login_required.connect(self._on_login_required)
        self._worker.queue_finished.connect(self._on_queue_finished)

        self._worker.start()

        self.upload_btn.setEnabled(False)
        self.login_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)

        self._log(f"Upload started: {len(dist_ids)} release(s)")

    def _stop_upload(self):
        """Stop the upload worker."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._log("Stop requested...")

    def _on_upload_started(self, dist_id: int, title: str):
        self.status_display.setText(f"Uploading: {title}")
        self._log(f"Uploading: {title}")

    def _on_upload_completed(self, dist_id: int):
        self._log(f"Upload completed: distribution #{dist_id}")
        self.load_distributions()

    def _on_upload_error(self, dist_id: int, error: str):
        self._log(f"ERROR (#{dist_id}): {error}")
        self.load_distributions()

    def _on_progress(self, message: str):
        self.status_display.setText(message)
        self._log(message)

    def _on_login_required(self, message: str):
        self.status_display.setText("Waiting for login + 2FA...")
        QMessageBox.information(self, "DistroKid Login Required", message)

    def _on_queue_finished(self):
        self.upload_btn.setEnabled(True)
        self.login_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_display.setText("Idle")
        self._log("Upload queue finished")
        self.load_distributions()

    # ------------------------------------------------------------------
    # Log
    # ------------------------------------------------------------------

    def _log(self, message: str):
        """Append a message to the log text area."""
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {message}")

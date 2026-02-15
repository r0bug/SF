"""
Song Factory - CD Master Tab

Main tab for creating, editing, and burning audio CDs with CD-TEXT metadata.
Supports CD-Extra discs (audio + data sessions) via cdrdao + wodim.

Layout: 3-panel horizontal splitter
  Left:   Project list with New/Delete/Duplicate
  Center: Track list, metadata, data options, burn controls
  Right:  Art preview with generate/export buttons
"""

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
    QListWidgetItem, QPushButton, QLabel, QLineEdit, QGroupBox,
    QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QCheckBox, QDoubleSpinBox, QProgressBar,
    QMessageBox, QTextEdit, QFrame, QFileDialog, QSizePolicy,
    QApplication,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QColor

from tabs.base_tab import BaseTab
from theme import Theme

CD_MAX_SECONDS = 80 * 60       # 80 minutes Red Book
CD_WARN_SECONDS = 74 * 60      # 74 minutes warning threshold

CD_PROJECTS_DIR = Path.home() / ".songfactory" / "cd_projects"


class CDMasterTab(BaseTab):
    """Main CD mastering tab with project list, track editor, and art preview."""

    def __init__(self, db, parent=None):
        self._current_project = None
        self._current_tracks = []
        self._convert_worker = None
        self._iso_worker = None
        super().__init__(db, parent)

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Left Panel: Project List ----
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)
        left_layout.setSpacing(6)

        left_header = QLabel("CD Projects")
        left_header.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold; font-size: 14px;")
        left_layout.addWidget(left_header)

        self.project_list = QListWidget()
        self.project_list.currentItemChanged.connect(self._on_project_selected)
        left_layout.addWidget(self.project_list, stretch=1)

        btn_row = QHBoxLayout()
        self.new_project_btn = QPushButton("New")
        self.new_project_btn.clicked.connect(self._new_project)
        btn_row.addWidget(self.new_project_btn)

        self.dup_project_btn = QPushButton("Duplicate")
        self.dup_project_btn.clicked.connect(self._duplicate_project)
        btn_row.addWidget(self.dup_project_btn)

        self.del_project_btn = QPushButton("Delete")
        self.del_project_btn.setObjectName("deleteProjectBtn")
        self.del_project_btn.clicked.connect(self._delete_project)
        btn_row.addWidget(self.del_project_btn)

        left_layout.addLayout(btn_row)

        left.setFixedWidth(250)
        splitter.addWidget(left)

        # ---- Center Panel: Track List + Metadata ----
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(4, 8, 4, 8)
        center_layout.setSpacing(8)

        # Project metadata
        meta_group = QGroupBox("Album Metadata")
        meta_form = QFormLayout(meta_group)

        self.album_title_edit = QLineEdit()
        self.album_title_edit.setPlaceholderText("Album title for CD-TEXT")
        meta_form.addRow("Album Title:", self.album_title_edit)

        self.artist_edit = QLineEdit()
        self.artist_edit.setText("Yakima Finds")
        meta_form.addRow("Artist:", self.artist_edit)

        self.songwriter_edit = QLineEdit()
        meta_form.addRow("Songwriter:", self.songwriter_edit)

        self.message_edit = QLineEdit()
        self.message_edit.setPlaceholderText("CD-TEXT message (optional)")
        meta_form.addRow("Disc Message:", self.message_edit)

        self.save_meta_btn = QPushButton("Save Metadata")
        self.save_meta_btn.setObjectName("saveMetaBtn")
        self.save_meta_btn.clicked.connect(self._save_metadata)
        meta_form.addRow("", self.save_meta_btn)

        center_layout.addWidget(meta_group)

        # Track table
        track_header = QLabel("Tracks")
        track_header.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold; font-size: 13px;")
        center_layout.addWidget(track_header)

        self.track_table = QTableWidget()
        self.track_table.setColumnCount(6)
        self.track_table.setHorizontalHeaderLabels(
            ["#", "Title", "Performer", "Duration", "Gap", "Status"]
        )
        self.track_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        for col in (0, 2, 3, 4, 5):
            self.track_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self.track_table.verticalHeader().setVisible(False)
        self.track_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.track_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.track_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.track_table.setAlternatingRowColors(True)
        self.track_table.itemSelectionChanged.connect(self._on_track_selected)
        center_layout.addWidget(self.track_table, stretch=1)

        # Track controls row
        track_ctrl = QHBoxLayout()
        track_ctrl.setSpacing(6)

        self.add_from_lib_btn = QPushButton("Add from Library")
        self.add_from_lib_btn.setObjectName("addFromLibBtn")
        self.add_from_lib_btn.clicked.connect(self._add_from_library)
        track_ctrl.addWidget(self.add_from_lib_btn)

        self.add_external_btn = QPushButton("Add External File")
        self.add_external_btn.clicked.connect(self._add_external_file)
        track_ctrl.addWidget(self.add_external_btn)

        self.remove_track_btn = QPushButton("Remove")
        self.remove_track_btn.clicked.connect(self._remove_track)
        track_ctrl.addWidget(self.remove_track_btn)

        self.move_up_btn = QPushButton("Up")
        self.move_up_btn.setFixedWidth(50)
        self.move_up_btn.clicked.connect(self._move_track_up)
        track_ctrl.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("Down")
        self.move_down_btn.setFixedWidth(50)
        self.move_down_btn.clicked.connect(self._move_track_down)
        track_ctrl.addWidget(self.move_down_btn)

        track_ctrl.addStretch()

        self.duration_label = QLabel("0:00 / 80:00")
        self.duration_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-weight: bold; font-size: 13px;")
        track_ctrl.addWidget(self.duration_label)

        center_layout.addLayout(track_ctrl)

        # Track detail (editable when a track is selected)
        self.track_detail_frame = QFrame()
        self.track_detail_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.track_detail_frame.setVisible(False)
        td_layout = QFormLayout(self.track_detail_frame)

        self.td_title = QLineEdit()
        td_layout.addRow("Title:", self.td_title)
        self.td_performer = QLineEdit()
        td_layout.addRow("Performer:", self.td_performer)
        self.td_songwriter = QLineEdit()
        td_layout.addRow("Songwriter:", self.td_songwriter)
        self.td_pregap = QDoubleSpinBox()
        self.td_pregap.setRange(0, 10)
        self.td_pregap.setSingleStep(0.5)
        self.td_pregap.setSuffix(" sec")
        self.td_pregap.setValue(2.0)
        td_layout.addRow("Pre-gap:", self.td_pregap)

        self.td_save_btn = QPushButton("Save Track")
        self.td_save_btn.clicked.connect(self._save_track_detail)
        td_layout.addRow("", self.td_save_btn)

        center_layout.addWidget(self.track_detail_frame)

        # Data session options
        data_group = QGroupBox("Data Session (CD-Extra)")
        data_layout = QVBoxLayout(data_group)

        self.include_data_cb = QCheckBox("Include Data Session (CD-Extra)")
        self.include_data_cb.setChecked(True)
        self.include_data_cb.stateChanged.connect(self._on_data_toggle)
        data_layout.addWidget(self.include_data_cb)

        data_opts = QHBoxLayout()
        self.include_mp3_cb = QCheckBox("MP3 Files")
        self.include_mp3_cb.setChecked(True)
        data_opts.addWidget(self.include_mp3_cb)

        self.include_lyrics_cb = QCheckBox("Lyrics")
        self.include_lyrics_cb.setChecked(True)
        data_opts.addWidget(self.include_lyrics_cb)

        self.include_source_cb = QCheckBox("Song Factory Source Code")
        self.include_source_cb.setChecked(True)
        data_opts.addWidget(self.include_source_cb)

        data_opts.addStretch()
        data_layout.addLayout(data_opts)

        center_layout.addWidget(data_group)

        # Action buttons
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.convert_btn = QPushButton("Convert All to WAV")
        self.convert_btn.setObjectName("convertBtn")
        self.convert_btn.clicked.connect(self._convert_all)
        action_row.addWidget(self.convert_btn)

        self.export_iso_btn = QPushButton("Export ISO")
        self.export_iso_btn.setObjectName("exportIsoBtn")
        self.export_iso_btn.clicked.connect(self._export_iso)
        action_row.addWidget(self.export_iso_btn)

        center_layout.addLayout(action_row)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(18)
        center_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {Theme.TEXT}; font-size: 12px;")
        center_layout.addWidget(self.status_label)

        splitter.addWidget(center)

        # ---- Right Panel: Art Preview ----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)
        right_layout.setSpacing(8)

        art_header = QLabel("Artwork")
        art_header.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold; font-size: 14px;")
        right_layout.addWidget(art_header)

        # Disc art
        disc_label = QLabel("Disc Art")
        disc_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(disc_label)

        self.disc_art_preview = QLabel()
        self.disc_art_preview.setFixedSize(200, 200)
        self.disc_art_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.disc_art_preview.setStyleSheet(
            f"background-color: {Theme.PANEL}; border: 1px solid #555555; border-radius: 4px;"
        )
        self.disc_art_preview.setText("No art")
        right_layout.addWidget(self.disc_art_preview)

        disc_btn_row = QHBoxLayout()
        self.gen_disc_art_btn = QPushButton("Generate")
        self.gen_disc_art_btn.clicked.connect(self._generate_disc_art)
        disc_btn_row.addWidget(self.gen_disc_art_btn)
        self.export_disc_btn = QPushButton("Export")
        self.export_disc_btn.clicked.connect(lambda: self._export_art("disc"))
        disc_btn_row.addWidget(self.export_disc_btn)
        right_layout.addLayout(disc_btn_row)

        # Cover art
        cover_label = QLabel("Cover Art")
        cover_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(cover_label)

        self.cover_art_preview = QLabel()
        self.cover_art_preview.setFixedSize(200, 200)
        self.cover_art_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_art_preview.setStyleSheet(
            f"background-color: {Theme.PANEL}; border: 1px solid #555555; border-radius: 4px;"
        )
        self.cover_art_preview.setText("No art")
        right_layout.addWidget(self.cover_art_preview)

        cover_btn_row = QHBoxLayout()
        self.gen_cover_btn = QPushButton("Generate")
        self.gen_cover_btn.clicked.connect(self._generate_cover_art)
        cover_btn_row.addWidget(self.gen_cover_btn)
        self.export_cover_btn = QPushButton("Export")
        self.export_cover_btn.clicked.connect(lambda: self._export_art("cover"))
        cover_btn_row.addWidget(self.export_cover_btn)
        right_layout.addLayout(cover_btn_row)

        # Back insert
        back_label = QLabel("Back Insert")
        back_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(back_label)

        self.back_art_preview = QLabel()
        self.back_art_preview.setFixedSize(200, 160)
        self.back_art_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.back_art_preview.setStyleSheet(
            f"background-color: {Theme.PANEL}; border: 1px solid #555555; border-radius: 4px;"
        )
        self.back_art_preview.setText("No art")
        right_layout.addWidget(self.back_art_preview)

        back_btn_row = QHBoxLayout()
        self.gen_back_btn = QPushButton("Generate")
        self.gen_back_btn.clicked.connect(self._generate_back_art)
        back_btn_row.addWidget(self.gen_back_btn)
        self.export_back_btn = QPushButton("Export")
        self.export_back_btn.clicked.connect(lambda: self._export_art("back"))
        back_btn_row.addWidget(self.export_back_btn)
        right_layout.addLayout(back_btn_row)

        right_layout.addStretch()

        right.setFixedWidth(240)
        splitter.addWidget(right)

        # Splitter proportions
        splitter.setStretchFactor(0, 0)  # left fixed
        splitter.setStretchFactor(1, 1)  # center stretches
        splitter.setStretchFactor(2, 0)  # right fixed

        root.addWidget(splitter)
        self._apply_styles()

    # ==================================================================
    # Signals & Refresh
    # ==================================================================

    def _connect_signals(self) -> None:
        """Initial data load after UI and signals are ready."""
        self.refresh_projects()

    def refresh(self) -> None:
        """Reload project data (called by app.py on tab activation)."""
        self.refresh_projects()

    # ==================================================================
    # Styles
    # ==================================================================

    def _apply_styles(self):
        self.setStyleSheet(f"""
            CDMasterTab {{ background-color: {Theme.BG}; }}
            QLabel {{ color: {Theme.TEXT}; }}
            QLineEdit {{
                background-color: {Theme.PANEL}; color: {Theme.TEXT};
                border: 1px solid #555555; border-radius: 4px; padding: 4px;
            }}
            QLineEdit:focus {{ border: 1px solid {Theme.ACCENT}; }}
            QListWidget {{
                background-color: {Theme.PANEL}; color: {Theme.TEXT};
                border: 1px solid #555555; border-radius: 4px;
            }}
            QListWidget::item {{ padding: 6px; }}
            QListWidget::item:selected {{ background-color: {Theme.ACCENT}; color: #000000; }}
            QTableWidget {{
                background-color: {Theme.BG}; alternate-background-color: #323232;
                color: {Theme.TEXT}; border: 1px solid #555555; gridline-color: transparent;
            }}
            QTableWidget::item:selected {{ background-color: {Theme.ACCENT}; color: #000000; }}
            QHeaderView::section {{
                background-color: {Theme.PANEL}; color: {Theme.TEXT};
                border: none; border-bottom: 2px solid {Theme.ACCENT};
                padding: 6px; font-weight: bold;
            }}
            QGroupBox {{
                color: {Theme.ACCENT}; border: 1px solid #555555;
                border-radius: 6px; margin-top: 12px; padding-top: 16px;
                font-weight: bold;
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; }}
            QFrame {{ background-color: {Theme.PANEL}; border: 1px solid #555555; border-radius: 4px; }}
            QPushButton {{
                background-color: {Theme.PANEL}; color: {Theme.TEXT};
                border: 1px solid #555555; border-radius: 4px;
                padding: 6px 12px; font-weight: bold; font-size: 12px;
            }}
            QPushButton:hover {{ border-color: {Theme.ACCENT}; background-color: #444444; }}
            QPushButton:pressed {{ background-color: {Theme.ACCENT}; color: #000000; }}
            QPushButton:disabled {{ background-color: #3a3a3a; color: #666666; }}
            QPushButton#addFromLibBtn {{
                background-color: {Theme.ACCENT}; color: #000000; border: none;
            }}
            QPushButton#addFromLibBtn:hover {{ background-color: #F0B848; }}
            QPushButton#convertBtn {{
                background-color: #2196F3; color: #FFFFFF; border: none;
            }}
            QPushButton#convertBtn:hover {{ background-color: #42A5F5; }}
            QPushButton#exportIsoBtn {{
                background-color: {Theme.SUCCESS}; color: #FFFFFF; border: none;
                font-size: 13px; padding: 8px 16px;
            }}
            QPushButton#exportIsoBtn:hover {{ background-color: #66BB6A; }}
            QPushButton#saveMetaBtn {{
                background-color: {Theme.SUCCESS}; color: #FFFFFF; border: none;
            }}
            QPushButton#saveMetaBtn:hover {{ background-color: #66BB6A; }}
            QPushButton#deleteProjectBtn {{
                background-color: {Theme.ERROR}; color: #FFFFFF; border: none;
            }}
            QPushButton#deleteProjectBtn:hover {{ background-color: #FF5544; }}
            QCheckBox {{ color: {Theme.TEXT}; spacing: 6px; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 1px solid #555555; border-radius: 3px;
                background-color: {Theme.PANEL};
            }}
            QCheckBox::indicator:checked {{
                background-color: {Theme.ACCENT}; border-color: {Theme.ACCENT};
            }}
            QDoubleSpinBox {{
                background-color: {Theme.PANEL}; color: {Theme.TEXT};
                border: 1px solid #555555; border-radius: 4px; padding: 4px;
            }}
            QProgressBar {{
                background-color: {Theme.BG}; border: 1px solid #555555;
                border-radius: 4px; text-align: center; color: {Theme.TEXT};
            }}
            QProgressBar::chunk {{ background-color: {Theme.ACCENT}; border-radius: 3px; }}
        """)

    # ==================================================================
    # Project List
    # ==================================================================

    def refresh_projects(self):
        """Reload the project list from the database."""
        self.project_list.blockSignals(True)
        current_id = None
        if self._current_project:
            current_id = self._current_project.get("id")

        self.project_list.clear()
        projects = self.db.get_all_cd_projects()

        select_idx = -1
        for i, proj in enumerate(projects):
            tracks = self.db.get_cd_tracks(proj["id"])
            name = proj.get("name", "Untitled")
            status = proj.get("status", "draft")
            label = f"{name}  [{status}]  ({len(tracks)} tracks)"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, proj["id"])
            self.project_list.addItem(item)
            if proj["id"] == current_id:
                select_idx = i

        self.project_list.blockSignals(False)

        if select_idx >= 0:
            self.project_list.setCurrentRow(select_idx)
        elif self.project_list.count() > 0:
            self.project_list.setCurrentRow(0)
        else:
            self._clear_center()

    def _on_project_selected(self, current, previous):
        if current is None:
            self._clear_center()
            return
        project_id = current.data(Qt.ItemDataRole.UserRole)
        if project_id is None:
            self._clear_center()
            return
        self._load_project(project_id)

    def _load_project(self, project_id: int):
        """Load a project and its tracks into the center panel."""
        proj = self.db.get_cd_project(project_id)
        if not proj:
            self._clear_center()
            return

        self._current_project = proj
        self._current_tracks = self.db.get_cd_tracks(project_id)

        # Populate metadata fields
        self.album_title_edit.setText(proj.get("album_title", ""))
        self.artist_edit.setText(proj.get("artist", "Yakima Finds"))
        self.songwriter_edit.setText(proj.get("songwriter", ""))
        self.message_edit.setText(proj.get("message", ""))

        # Data session checkboxes
        self.include_data_cb.setChecked(bool(proj.get("include_data", 1)))
        self.include_mp3_cb.setChecked(bool(proj.get("include_mp3", 1)))
        self.include_lyrics_cb.setChecked(bool(proj.get("include_lyrics", 1)))
        self.include_source_cb.setChecked(bool(proj.get("include_source", 1)))
        self._on_data_toggle()

        # Populate track table
        self._populate_tracks()

        # Load art previews
        self._load_art_previews(proj)

        self.track_detail_frame.setVisible(False)
        self.status_label.setText(f"Project: {proj.get('name', '')}")

    def _clear_center(self):
        """Clear all center panel fields."""
        self._current_project = None
        self._current_tracks = []
        self.album_title_edit.clear()
        self.artist_edit.setText("Yakima Finds")
        self.songwriter_edit.clear()
        self.message_edit.clear()
        self.track_table.setRowCount(0)
        self.track_detail_frame.setVisible(False)
        self.duration_label.setText("0:00 / 80:00")
        self.duration_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-weight: bold; font-size: 13px;")
        self.disc_art_preview.setText("No art")
        self.disc_art_preview.setPixmap(QPixmap())
        self.cover_art_preview.setText("No art")
        self.cover_art_preview.setPixmap(QPixmap())
        self.back_art_preview.setText("No art")
        self.back_art_preview.setPixmap(QPixmap())

    # ==================================================================
    # Track Table
    # ==================================================================

    def _populate_tracks(self):
        """Fill the track table from self._current_tracks."""
        tracks = self._current_tracks
        self.track_table.setRowCount(len(tracks))

        total_seconds = 0
        for row, track in enumerate(tracks):
            # #
            num_item = QTableWidgetItem(str(track.get("track_number", row + 1)))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.track_table.setItem(row, 0, num_item)

            # Title
            title_item = QTableWidgetItem(track.get("title", ""))
            title_item.setData(Qt.ItemDataRole.UserRole, track.get("id"))
            self.track_table.setItem(row, 1, title_item)

            # Performer
            self.track_table.setItem(
                row, 2, QTableWidgetItem(track.get("performer", ""))
            )

            # Duration
            dur = track.get("duration_seconds", 0)
            total_seconds += dur
            m = int(dur) // 60
            s = int(dur) % 60
            dur_str = f"{m}:{s:02d}" if dur > 0 else "—"
            self.track_table.setItem(row, 3, QTableWidgetItem(dur_str))

            # Pre-gap
            gap = track.get("pregap_seconds", 2.0)
            self.track_table.setItem(row, 4, QTableWidgetItem(f"{gap:.1f}s"))

            # Status
            wav_path = track.get("wav_path")
            source = track.get("source_path", "")
            if wav_path and os.path.exists(wav_path):
                status_text = "WAV Ready"
                status_color = Theme.SUCCESS
            elif source and os.path.exists(source):
                status_text = "Needs Convert"
                status_color = Theme.ACCENT
            else:
                status_text = "Missing"
                status_color = Theme.ERROR

            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            self.track_table.setItem(row, 5, status_item)

            self.track_table.setRowHeight(row, 32)

        # Update duration label
        self._update_duration_label(total_seconds)

    def _update_duration_label(self, total_seconds: float):
        tm = int(total_seconds) // 60
        ts = int(total_seconds) % 60
        label = f"{tm}:{ts:02d} / 80:00"

        if total_seconds > CD_MAX_SECONDS:
            color = Theme.ERROR
        elif total_seconds > CD_WARN_SECONDS:
            color = Theme.ACCENT
        else:
            color = Theme.SUCCESS

        self.duration_label.setText(label)
        self.duration_label.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 13px;"
        )

    def _on_track_selected(self):
        """Show track detail editor when a track is selected."""
        rows = self.track_table.selectionModel().selectedRows()
        if not rows:
            self.track_detail_frame.setVisible(False)
            return

        row = rows[0].row()
        if row < 0 or row >= len(self._current_tracks):
            self.track_detail_frame.setVisible(False)
            return

        track = self._current_tracks[row]
        self.td_title.setText(track.get("title", ""))
        self.td_performer.setText(track.get("performer", ""))
        self.td_songwriter.setText(track.get("songwriter", ""))
        self.td_pregap.setValue(track.get("pregap_seconds", 2.0))
        self.track_detail_frame.setVisible(True)

    # ==================================================================
    # Project Actions
    # ==================================================================

    def _new_project(self):
        """Create a new CD project."""
        # Find a unique name
        existing = self.db.get_all_cd_projects()
        names = {p.get("name", "") for p in existing}
        name = "New CD Project"
        counter = 2
        while name in names:
            name = f"New CD Project {counter}"
            counter += 1

        pid = self.db.add_cd_project(name)
        self.refresh_projects()
        # Select the new project
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == pid:
                self.project_list.setCurrentRow(i)
                break

    def _duplicate_project(self):
        """Duplicate the current project and all its tracks."""
        if not self._current_project:
            return

        src = self._current_project
        new_name = f"{src.get('name', 'CD')} (Copy)"
        pid = self.db.add_cd_project(
            new_name,
            artist=src.get("artist", "Yakima Finds"),
            album_title=src.get("album_title", ""),
            songwriter=src.get("songwriter", ""),
            message=src.get("message", ""),
            include_data=src.get("include_data", 1),
            include_source=src.get("include_source", 1),
            include_lyrics=src.get("include_lyrics", 1),
            include_mp3=src.get("include_mp3", 1),
        )

        # Copy tracks
        for track in self._current_tracks:
            self.db.add_cd_track(
                pid,
                track["track_number"],
                track["title"],
                track["source_path"],
                song_id=track.get("song_id"),
                performer=track.get("performer", "Yakima Finds"),
                songwriter=track.get("songwriter", ""),
                duration_seconds=track.get("duration_seconds", 0),
                pregap_seconds=track.get("pregap_seconds", 2.0),
            )

        self.refresh_projects()

    def _delete_project(self):
        """Delete the current project after confirmation."""
        if not self._current_project:
            return

        name = self._current_project.get("name", "Untitled")
        reply = QMessageBox.question(
            self,
            "Delete CD Project",
            f'Delete "{name}" and all its tracks?\n\nThis cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_cd_project(self._current_project["id"])
            self._current_project = None
            self.refresh_projects()

    # ==================================================================
    # Metadata Save
    # ==================================================================

    def _save_metadata(self):
        """Save the album metadata fields to the database."""
        if not self._current_project:
            return

        pid = self._current_project["id"]

        # Also update project name to match album title if set
        album = self.album_title_edit.text().strip()
        name = album if album else self._current_project.get("name", "Untitled")

        self.db.update_cd_project(
            pid,
            name=name,
            album_title=album,
            artist=self.artist_edit.text().strip(),
            songwriter=self.songwriter_edit.text().strip(),
            message=self.message_edit.text().strip(),
            include_data=int(self.include_data_cb.isChecked()),
            include_source=int(self.include_source_cb.isChecked()),
            include_lyrics=int(self.include_lyrics_cb.isChecked()),
            include_mp3=int(self.include_mp3_cb.isChecked()),
        )

        self._current_project = self.db.get_cd_project(pid)
        self.refresh_projects()
        self.status_label.setText("Metadata saved.")

    def _on_data_toggle(self):
        """Enable/disable sub-checkboxes based on Include Data checkbox."""
        enabled = self.include_data_cb.isChecked()
        self.include_mp3_cb.setEnabled(enabled)
        self.include_lyrics_cb.setEnabled(enabled)
        self.include_source_cb.setEnabled(enabled)

    # ==================================================================
    # Track Actions
    # ==================================================================

    def _add_from_library(self):
        """Open song picker dialog and add selected songs as tracks."""
        if not self._current_project:
            QMessageBox.information(self, "No Project", "Create a CD project first.")
            return

        from tabs.song_picker_dialog import SongPickerDialog
        dialog = SongPickerDialog(self.db, parent=self)
        if dialog.exec() != SongPickerDialog.DialogCode.Accepted:
            return

        songs = dialog.get_selected_songs()
        if not songs:
            return

        pid = self._current_project["id"]
        next_num = len(self._current_tracks) + 1

        for song in songs:
            source = song.get("file_path_1", "")
            title = song.get("title", "Untitled")
            dur = song.get("duration_seconds", 0)

            self.db.add_cd_track(
                pid, next_num, title, source,
                song_id=song.get("id"),
                performer="Yakima Finds",
                duration_seconds=dur or 0,
            )
            next_num += 1

        self._reload_tracks()

    def _add_external_file(self):
        """Add an external audio file as a track."""
        if not self._current_project:
            QMessageBox.information(self, "No Project", "Create a CD project first.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            str(Path.home() / "Music"),
            "Audio Files (*.mp3 *.wav *.flac *.ogg *.m4a);;All Files (*)",
        )
        if not file_path:
            return

        pid = self._current_project["id"]
        next_num = len(self._current_tracks) + 1
        title = Path(file_path).stem

        # Try to probe duration
        try:
            from automation.audio_converter import probe_duration
            dur = probe_duration(file_path)
        except Exception:
            dur = 0

        self.db.add_cd_track(pid, next_num, title, file_path, duration_seconds=dur)
        self._reload_tracks()

    def _remove_track(self):
        """Remove the selected track."""
        if not self._current_project:
            return

        rows = self.track_table.selectionModel().selectedRows()
        if not rows:
            return

        row = rows[0].row()
        if row < 0 or row >= len(self._current_tracks):
            return

        track = self._current_tracks[row]
        self.db.delete_cd_track(track["id"])

        # Renumber remaining tracks
        pid = self._current_project["id"]
        remaining = self.db.get_cd_tracks(pid)
        track_ids = [t["id"] for t in remaining]
        self.db.reorder_cd_tracks(pid, track_ids)

        self._reload_tracks()

    def _move_track_up(self):
        self._move_track(-1)

    def _move_track_down(self):
        self._move_track(1)

    def _move_track(self, direction: int):
        """Move the selected track up (-1) or down (+1)."""
        if not self._current_project:
            return

        rows = self.track_table.selectionModel().selectedRows()
        if not rows:
            return

        row = rows[0].row()
        new_row = row + direction
        if new_row < 0 or new_row >= len(self._current_tracks):
            return

        # Swap in the id list
        track_ids = [t["id"] for t in self._current_tracks]
        track_ids[row], track_ids[new_row] = track_ids[new_row], track_ids[row]

        pid = self._current_project["id"]
        self.db.reorder_cd_tracks(pid, track_ids)

        self._reload_tracks()
        self.track_table.selectRow(new_row)

    def _save_track_detail(self):
        """Save edits from the track detail panel."""
        rows = self.track_table.selectionModel().selectedRows()
        if not rows:
            return

        row = rows[0].row()
        if row < 0 or row >= len(self._current_tracks):
            return

        track = self._current_tracks[row]
        self.db.update_cd_track(
            track["id"],
            title=self.td_title.text().strip(),
            performer=self.td_performer.text().strip(),
            songwriter=self.td_songwriter.text().strip(),
            pregap_seconds=self.td_pregap.value(),
        )

        self._reload_tracks()
        self.track_table.selectRow(row)

    def _reload_tracks(self):
        """Reload tracks from DB and refresh table + project list."""
        if self._current_project:
            self._current_tracks = self.db.get_cd_tracks(self._current_project["id"])

            # Update total duration in project
            total = sum(t.get("duration_seconds", 0) for t in self._current_tracks)
            self.db.update_cd_project(
                self._current_project["id"], total_duration=total
            )

        self._populate_tracks()
        self.refresh_projects()

    # ==================================================================
    # Convert to WAV
    # ==================================================================

    def _convert_all(self):
        """Convert all tracks to WAV using ffmpeg."""
        if not self._current_project or not self._current_tracks:
            return

        if self._convert_worker and self._convert_worker.isRunning():
            QMessageBox.information(self, "Busy", "Conversion already in progress.")
            return

        # Filter tracks that need conversion
        to_convert = [
            t for t in self._current_tracks
            if not (t.get("wav_path") and os.path.exists(t["wav_path"]))
        ]

        if not to_convert:
            QMessageBox.information(self, "All Ready", "All tracks already have WAV files.")
            return

        from automation.audio_converter import AudioConvertWorker

        pid = self._current_project["id"]
        self._convert_worker = AudioConvertWorker(pid, to_convert)
        self.register_worker(self._convert_worker)
        self._convert_worker.track_started.connect(self._on_convert_started)
        self._convert_worker.track_completed.connect(self._on_convert_done)
        self._convert_worker.track_error.connect(self._on_convert_error)
        self._convert_worker.all_finished.connect(self._on_convert_finished)

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(to_convert))
        self.progress_bar.setValue(0)
        self._convert_count = 0
        self.convert_btn.setEnabled(False)
        self.status_label.setText("Converting tracks to WAV...")

        self.db.update_cd_project(pid, status="converting")
        self._convert_worker.start()

    def _on_convert_started(self, track_id: int, title: str):
        self.status_label.setText(f"Converting: {title}")

    def _on_convert_done(self, track_id: int, wav_path: str):
        self.db.update_cd_track(track_id, wav_path=wav_path)

        # Probe and update duration
        try:
            from automation.audio_converter import probe_duration
            dur = probe_duration(wav_path)
            if dur > 0:
                self.db.update_cd_track(track_id, duration_seconds=dur)
        except Exception:
            pass

        self._convert_count += 1
        self.progress_bar.setValue(self._convert_count)

    def _on_convert_error(self, track_id: int, error: str):
        self.status_label.setText(f"Error converting track: {error[:80]}")
        self._convert_count += 1
        self.progress_bar.setValue(self._convert_count)

    def _on_convert_finished(self):
        self.convert_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._convert_worker = None

        if self._current_project:
            self.db.update_cd_project(self._current_project["id"], status="ready")

        self._reload_tracks()
        self.status_label.setText("Conversion complete.")

    # ==================================================================
    # ISO Export
    # ==================================================================

    def _export_iso(self):
        """Export the current project as an ISO image file."""
        if not self._current_project or not self._current_tracks:
            QMessageBox.information(
                self, "No Project",
                "Select a project with tracks before exporting.",
            )
            return

        if self._iso_worker and self._iso_worker.isRunning():
            QMessageBox.information(self, "Busy", "ISO build already in progress.")
            return

        # Suggest filename from album title
        album = (
            self._current_project.get("album_title")
            or self._current_project.get("name", "CD")
        )
        safe_name = "".join(
            c if c.isalnum() or c in (" ", "-", "_") else "_" for c in album
        ).strip()
        default_name = f"{safe_name}.iso" if safe_name else "cd_project.iso"

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export ISO Image",
            str(Path.home() / default_name),
            "ISO Images (*.iso);;All Files (*)",
        )
        if not output_path:
            return

        # Gather songs for data session
        songs = []
        for track in self._current_tracks:
            sid = track.get("song_id")
            if sid:
                song = self.db.get_song(sid)
                if song:
                    songs.append(song)

        from automation.iso_builder import ISOBuildWorker

        self._iso_worker = ISOBuildWorker(
            project=self._current_project,
            tracks=self._current_tracks,
            songs=songs,
            output_path=output_path,
        )
        self.register_worker(self._iso_worker)
        self._iso_worker.build_progress.connect(self._on_iso_progress)
        self._iso_worker.build_completed.connect(self._on_iso_completed)
        self._iso_worker.build_error.connect(self._on_iso_error)

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.export_iso_btn.setEnabled(False)
        self.status_label.setText("Building ISO...")
        self.db.update_cd_project(self._current_project["id"], status="building")
        self._iso_worker.start()

    def _on_iso_progress(self, msg: str):
        self.status_label.setText(msg)

    def _on_iso_completed(self, iso_path: str):
        self.export_iso_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._iso_worker = None

        if self._current_project:
            self.db.update_cd_project(self._current_project["id"], status="exported")
            self.refresh_projects()

        self.status_label.setText(f"ISO exported: {iso_path}")
        QMessageBox.information(
            self, "ISO Exported",
            f"ISO image created successfully:\n\n{iso_path}",
        )

    def _on_iso_error(self, error: str):
        self.export_iso_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._iso_worker = None

        if self._current_project:
            self.db.update_cd_project(self._current_project["id"], status="error")
            self.refresh_projects()

        self.status_label.setText(f"ISO error: {error[:80]}")
        QMessageBox.warning(self, "ISO Build Error", error)

    # ==================================================================
    # Art Generation
    # ==================================================================

    def _generate_disc_art(self):
        if not self._current_project:
            return
        try:
            from automation.cd_art_generator import generate_disc_art
        except ImportError:
            QMessageBox.warning(self, "Missing Pillow", "Pillow is required for art generation.")
            return

        pid = self._current_project["id"]
        out_dir = CD_PROJECTS_DIR / str(pid)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(out_dir / "disc_art.png")

        generate_disc_art(self._current_project, self._current_tracks, out_path)
        self.db.update_cd_project(pid, disc_art_path=out_path)
        self._current_project["disc_art_path"] = out_path
        self._show_preview(self.disc_art_preview, out_path, 200, 200)
        self.status_label.setText("Disc art generated.")

    def _generate_cover_art(self):
        if not self._current_project:
            return
        try:
            from automation.cd_art_generator import generate_cover_art
        except ImportError:
            QMessageBox.warning(self, "Missing Pillow", "Pillow is required for art generation.")
            return

        pid = self._current_project["id"]
        out_dir = CD_PROJECTS_DIR / str(pid)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(out_dir / "cover_art.png")

        generate_cover_art(self._current_project, self._current_tracks, out_path)
        self.db.update_cd_project(pid, cover_art_path=out_path)
        self._current_project["cover_art_path"] = out_path
        self._show_preview(self.cover_art_preview, out_path, 200, 200)
        self.status_label.setText("Cover art generated.")

    def _generate_back_art(self):
        if not self._current_project:
            return
        try:
            from automation.cd_art_generator import generate_back_insert
        except ImportError:
            QMessageBox.warning(self, "Missing Pillow", "Pillow is required for art generation.")
            return

        pid = self._current_project["id"]
        out_dir = CD_PROJECTS_DIR / str(pid)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(out_dir / "back_insert.png")

        generate_back_insert(self._current_project, self._current_tracks, out_path)
        self.db.update_cd_project(pid, back_art_path=out_path)
        self._current_project["back_art_path"] = out_path
        self._show_preview(self.back_art_preview, out_path, 200, 160)
        self.status_label.setText("Back insert generated.")

    def _load_art_previews(self, project: dict):
        """Load existing art previews from saved paths."""
        disc_path = project.get("disc_art_path", "")
        if disc_path and os.path.exists(disc_path):
            self._show_preview(self.disc_art_preview, disc_path, 200, 200)
        else:
            self.disc_art_preview.setPixmap(QPixmap())
            self.disc_art_preview.setText("No art")

        cover_path = project.get("cover_art_path", "")
        if cover_path and os.path.exists(cover_path):
            self._show_preview(self.cover_art_preview, cover_path, 200, 200)
        else:
            self.cover_art_preview.setPixmap(QPixmap())
            self.cover_art_preview.setText("No art")

        back_path = project.get("back_art_path", "")
        if back_path and os.path.exists(back_path):
            self._show_preview(self.back_art_preview, back_path, 200, 160)
        else:
            self.back_art_preview.setPixmap(QPixmap())
            self.back_art_preview.setText("No art")

    def _show_preview(self, label: QLabel, path: str, w: int, h: int):
        """Load an image and show it scaled in a QLabel."""
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(scaled)
            label.setText("")

    def _export_art(self, art_type: str):
        """Export art to a user-chosen location."""
        if not self._current_project:
            return

        path_key = {
            "disc": "disc_art_path",
            "cover": "cover_art_path",
            "back": "back_art_path",
        }.get(art_type)

        if not path_key:
            return

        src_path = self._current_project.get(path_key, "")
        if not src_path or not os.path.exists(src_path):
            QMessageBox.information(
                self, "No Art",
                "Generate the art first before exporting.",
            )
            return

        dest, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {art_type.title()} Art",
            str(Path.home() / f"cd_{art_type}_art.png"),
            "PNG Images (*.png)",
        )
        if dest:
            import shutil
            shutil.copy2(src_path, dest)
            self.status_label.setText(f"Exported to {dest}")

    # ==================================================================
    # Public API for adding songs from library context menu
    # ==================================================================

    def add_song_to_project(self, project_id: int, song: dict):
        """Add a song to a specific CD project (called from library tab)."""
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

        # Refresh if we're viewing that project
        if self._current_project and self._current_project["id"] == project_id:
            self._reload_tracks()

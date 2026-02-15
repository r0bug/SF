"""
Song Factory - Song Creator Tab

The main workflow tab for generating songs. Provides a horizontal split layout
with an input panel (creative prompt, genre, style, lore context) on the left
and an output panel (generated prompt, lyrics, action buttons) on the right.

API calls run in a background QThread so the UI stays responsive.
"""

import json

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QComboBox,
    QLineEdit, QPushButton, QSplitter, QCheckBox, QScrollArea, QFrame,
    QMessageBox, QApplication, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from api_client import SongGenerator, SongGenerationError
from validators import validate_song
from tabs.base_tab import BaseTab
from theme import Theme
from event_bus import event_bus


# ===================================================================
# GenerateWorker — runs the API call off the main thread
# ===================================================================

class GenerateWorker(QThread):
    """Background worker that calls SongGenerator.generate_song()."""

    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(
        self,
        api_key: str,
        user_input: str,
        active_lore: list,
        lore_text: str | None = None,
        genre_name: str | None = None,
        genre_prompt_template: str | None = None,
        style_notes: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._api_key = api_key
        self._user_input = user_input
        self._active_lore = active_lore
        self._lore_text = lore_text
        self._genre_name = genre_name
        self._genre_prompt_template = genre_prompt_template
        self._style_notes = style_notes

    def run(self):
        try:
            generator = SongGenerator(api_key=self._api_key)
            result = generator.generate_song(
                user_input=self._user_input,
                active_lore=self._active_lore,
                lore_text=self._lore_text,
                genre_name=self._genre_name,
                genre_prompt_template=self._genre_prompt_template,
                style_notes=self._style_notes if self._style_notes else None,
            )
            self.finished.emit(result)
        except SongGenerationError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"Unexpected error: {exc}")


# ===================================================================
# SongCreatorTab
# ===================================================================

class SongCreatorTab(BaseTab):
    """Main song creation workflow tab."""

    def __init__(self, db, parent=None):
        # Instance variables needed before _init_ui() runs
        self._worker = None
        self._genres_cache: list[dict] = []
        self._last_result: dict | None = None
        self._lore_checkboxes: list[tuple[int, QCheckBox]] = []
        self._category_checkboxes: dict[str, QCheckBox] = {}
        self._lore_id_to_category: dict[int, str] = {}

        # BaseTab.__init__ sets self.db, calls _init_ui() and _connect_signals()
        super().__init__(db, parent)

        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self):
        """Assemble the full tab layout."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            f"QSplitter {{ background-color: {Theme.BG}; }}"
            f"QSplitter::handle {{ background-color: #444; width: 3px; }}"
        )

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        root_layout.addWidget(splitter)

    # ---------- Left panel (Input) ----------

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(Theme.panel_style())
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 1. Prompt label
        lbl_prompt = QLabel("What do you want a song about?")
        lbl_prompt.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {Theme.TEXT};")
        layout.addWidget(lbl_prompt)

        # 2. User input text area
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText(
            "Describe your song idea here... be as creative as you like!"
        )
        self.input_text.setMinimumHeight(120)
        layout.addWidget(self.input_text)

        # 3. Genre combo
        lbl_genre = QLabel("Genre")
        lbl_genre.setStyleSheet(f"color: {Theme.TEXT}; font-weight: bold;")
        layout.addWidget(lbl_genre)

        self.genre_combo = QComboBox()
        layout.addWidget(self.genre_combo)

        # 4. Style notes
        lbl_style = QLabel("Style notes")
        lbl_style.setStyleSheet(f"color: {Theme.TEXT}; font-weight: bold;")
        layout.addWidget(lbl_style)

        self.style_input = QLineEdit()
        self.style_input.setPlaceholderText("e.g. in the style of Beach Bunny")
        layout.addWidget(self.style_input)

        # 5. Collapsible lore context section
        self._lore_toggle_btn = QPushButton("\u25b6  Lore Context")
        self._lore_toggle_btn.setStyleSheet(Theme.collapsible_toggle_style())
        self._lore_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lore_toggle_btn.clicked.connect(self._toggle_lore_section)
        layout.addWidget(self._lore_toggle_btn)

        # Scroll area that holds the lore checkboxes
        self._lore_container = QScrollArea()
        self._lore_container.setWidgetResizable(True)
        self._lore_container.setVisible(False)
        self._lore_container.setMaximumHeight(350)
        self._lore_container.setStyleSheet(
            f"QScrollArea {{ border: 1px solid #555; border-radius: 4px; "
            f"background-color: {Theme.BG}; }}"
        )

        self._lore_inner = QWidget()
        self._lore_layout = QVBoxLayout(self._lore_inner)
        self._lore_layout.setContentsMargins(8, 8, 8, 8)
        self._lore_layout.setSpacing(4)
        self._lore_container.setWidget(self._lore_inner)
        layout.addWidget(self._lore_container)

        # 6. Select Lore button — populates the preview below
        self.select_lore_btn = QPushButton("Select Lore")
        self.select_lore_btn.setStyleSheet(Theme.secondary_button_style())
        self.select_lore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_lore_btn.clicked.connect(self._on_select_lore)
        layout.addWidget(self.select_lore_btn)

        # 7. Editable lore preview area (hidden until Select Lore is clicked)
        self._lore_preview_label = QLabel("Lore Context (editable)")
        self._lore_preview_label.setStyleSheet(
            f"color: {Theme.TEXT}; font-weight: bold; font-size: 13px;"
        )
        self._lore_preview_label.setVisible(False)
        layout.addWidget(self._lore_preview_label)

        self._lore_preview = QTextEdit()
        self._lore_preview.setPlaceholderText(
            "Click 'Select Lore' to load selected lore entries here. "
            "You can edit the text before generating."
        )
        self._lore_preview.setMinimumHeight(120)
        self._lore_preview.setMaximumHeight(250)
        self._lore_preview.setVisible(False)
        layout.addWidget(self._lore_preview)

        # 8. Generate button
        self.generate_btn = QPushButton("Generate Song")
        self.generate_btn.setStyleSheet(Theme.accent_button_style())
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.clicked.connect(self.generate_song)
        layout.addWidget(self.generate_btn)

        layout.addStretch()
        return panel

    # ---------- Right panel (Output) ----------

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(Theme.panel_style())
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 1. Generated prompt label
        lbl_prompt = QLabel("Generated Prompt")
        lbl_prompt.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {Theme.TEXT};")
        layout.addWidget(lbl_prompt)

        # 2. Prompt text edit (editable)
        self.prompt_output = QTextEdit()
        self.prompt_output.setPlaceholderText("Generated prompt will appear here...")
        self.prompt_output.setMaximumHeight(100)
        self.prompt_output.textChanged.connect(self.update_char_count)
        layout.addWidget(self.prompt_output)

        # 3. Character counter
        self.char_count_label = QLabel("0 / 300")
        self.char_count_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 12px;")
        self.char_count_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.char_count_label)

        # 4. Generated lyrics label
        lbl_lyrics = QLabel("Generated Lyrics")
        lbl_lyrics.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {Theme.TEXT};")
        layout.addWidget(lbl_lyrics)

        # 5. Lyrics text edit (monospace, editable)
        self.lyrics_output = QTextEdit()
        self.lyrics_output.setPlaceholderText("Generated lyrics will appear here...")
        mono_font = QFont("Courier New", 11)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.lyrics_output.setFont(mono_font)
        layout.addWidget(self.lyrics_output, 1)

        # 6. Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.save_btn = QPushButton("Save to Database")
        self.save_btn.setStyleSheet(Theme.secondary_button_style())
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(lambda: self.save_song(status="draft"))
        btn_row.addWidget(self.save_btn)

        self.queue_btn = QPushButton("Queue for Lalals")
        self.queue_btn.setStyleSheet(Theme.secondary_button_style())
        self.queue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.queue_btn.clicked.connect(lambda: self.save_song(status="queued"))
        btn_row.addWidget(self.queue_btn)

        self.copy_prompt_btn = QPushButton("Copy Prompt")
        self.copy_prompt_btn.setStyleSheet(Theme.secondary_button_style())
        self.copy_prompt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_prompt_btn.clicked.connect(
            lambda: self.copy_to_clipboard(self.prompt_output.toPlainText())
        )
        btn_row.addWidget(self.copy_prompt_btn)

        self.copy_lyrics_btn = QPushButton("Copy Lyrics")
        self.copy_lyrics_btn.setStyleSheet(Theme.secondary_button_style())
        self.copy_lyrics_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_lyrics_btn.clicked.connect(
            lambda: self.copy_to_clipboard(self.lyrics_output.toPlainText())
        )
        btn_row.addWidget(self.copy_lyrics_btn)

        layout.addLayout(btn_row)
        return panel

    # ------------------------------------------------------------------
    # Collapsible lore section toggle
    # ------------------------------------------------------------------

    def _toggle_lore_section(self):
        visible = not self._lore_container.isVisible()
        self._lore_container.setVisible(visible)
        arrow = "\u25bc" if visible else "\u25b6"
        self._lore_toggle_btn.setText(f"{arrow}  Lore Context")

    # ------------------------------------------------------------------
    # Data refresh helpers
    # ------------------------------------------------------------------

    def _connect_signals(self):
        """Connect event bus signals for cross-tab refresh."""
        event_bus.genres_changed.connect(self.refresh_genres)
        event_bus.lore_changed.connect(self.refresh_lore)

    def refresh_genres(self):
        """Reload the genre dropdown from the database."""
        self.genre_combo.clear()
        self.genre_combo.addItem("Auto (let AI choose)", None)
        self._genres_cache = self.db.get_active_genres()
        for genre in self._genres_cache:
            self.genre_combo.addItem(genre["name"], genre)

    def refresh_lore(self):
        """Reload the lore checkboxes from the database, grouped by category."""
        # Clear existing checkboxes
        self._lore_checkboxes.clear()
        self._category_checkboxes.clear()
        self._lore_id_to_category.clear()
        while self._lore_layout.count():
            item = self._lore_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            sub = item.layout()
            if sub:
                while sub.count():
                    child = sub.takeAt(0)
                    cw = child.widget()
                    if cw:
                        cw.deleteLater()

        lore_entries = self.db.get_all_lore()
        if not lore_entries:
            empty_label = QLabel("No lore entries yet.")
            empty_label.setStyleSheet("color: #888; font-style: italic;")
            self._lore_layout.addWidget(empty_label)
            return

        # ---- Top control row: Select All / Deselect All + Preset dropdown ----
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        select_all_btn = QPushButton("Select All")
        select_all_btn.setStyleSheet(
            f"QPushButton {{ background-color: #444; color: {Theme.TEXT}; border: 1px solid #666; "
            f"border-radius: 3px; padding: 2px 8px; font-size: 11px; }} "
            f"QPushButton:hover {{ background-color: #555; }}"
        )
        select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_all_btn.setFixedHeight(24)
        select_all_btn.clicked.connect(self._select_all_lore)
        top_row.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setStyleSheet(
            f"QPushButton {{ background-color: #444; color: {Theme.TEXT}; border: 1px solid #666; "
            f"border-radius: 3px; padding: 2px 8px; font-size: 11px; }} "
            f"QPushButton:hover {{ background-color: #555; }}"
        )
        deselect_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        deselect_all_btn.setFixedHeight(24)
        deselect_all_btn.clicked.connect(self._deselect_all_lore)
        top_row.addWidget(deselect_all_btn)

        top_row.addStretch()

        self._creator_preset_combo = QComboBox()
        self._creator_preset_combo.setFixedHeight(24)
        self._creator_preset_combo.setMinimumWidth(120)
        self._creator_preset_combo.setStyleSheet(
            f"QComboBox {{ font-size: 11px; padding: 1px 4px; }}"
        )
        self._refresh_creator_presets()
        self._creator_preset_combo.currentIndexChanged.connect(
            self._on_creator_preset_changed
        )
        top_row.addWidget(self._creator_preset_combo)

        self._lore_layout.addLayout(top_row)

        # ---- Group entries by category ----
        groups: dict[str, list[dict]] = {}
        for entry in lore_entries:
            cat = entry.get("category") or "general"
            groups.setdefault(cat, []).append(entry)
            self._lore_id_to_category[entry["id"]] = cat

        category_order = ["people", "places", "events", "themes", "rules", "general"]
        for cat in category_order:
            if cat not in groups:
                continue
            entries = groups[cat]

            # Category header label
            header = QLabel(cat.upper())
            header.setStyleSheet(
                f"color: {Theme.ACCENT}; font-weight: bold; font-size: 12px; "
                f"margin-top: 6px; margin-bottom: 2px;"
            )
            self._lore_layout.addWidget(header)

            # Category-level toggle checkbox
            cat_cb = QCheckBox(f"All {cat}")
            cat_cb.setStyleSheet(
                f"QCheckBox {{ color: {Theme.ACCENT}; font-size: 11px; font-weight: bold; }}"
            )
            cat_cb.setTristate(True)
            self._category_checkboxes[cat] = cat_cb
            self._lore_layout.addWidget(cat_cb)

            # Individual lore entry checkboxes (indented)
            for entry in entries:
                cb = QCheckBox(entry["title"])
                cb.setChecked(bool(entry.get("active", False)))
                cb.setToolTip(entry["content"][:200])
                cb.setStyleSheet("QCheckBox { margin-left: 16px; }")
                cb.stateChanged.connect(
                    lambda _state, c=cat: self._update_category_checkbox(c)
                )
                self._lore_checkboxes.append((entry["id"], cb))
                self._lore_layout.addWidget(cb)

            # Wire category checkbox to toggle its children
            cat_cb.stateChanged.connect(
                lambda state, c=cat: self._on_category_toggled(c, state)
            )

            # Set initial category checkbox state
            self._update_category_checkbox(cat)

        self._lore_layout.addStretch()

    def refresh(self):
        """Reload genres and lore from the database."""
        self.refresh_genres()
        self.refresh_lore()

    def _refresh_creator_presets(self):
        """Reload the preset dropdown in the creator tab."""
        self._creator_preset_combo.blockSignals(True)
        self._creator_preset_combo.clear()
        self._creator_preset_combo.addItem("-- Preset --", None)
        presets = self.db.get_all_lore_presets()
        for preset in presets:
            self._creator_preset_combo.addItem(preset["name"], preset["id"])
        self._creator_preset_combo.blockSignals(False)

    def _on_creator_preset_changed(self, index: int):
        """Apply a preset selection — check only matching lore checkboxes."""
        preset_id = self._creator_preset_combo.currentData()
        if preset_id is None:
            return
        self._apply_creator_preset(preset_id)
        # Reset combo to placeholder
        self._creator_preset_combo.blockSignals(True)
        self._creator_preset_combo.setCurrentIndex(0)
        self._creator_preset_combo.blockSignals(False)

    def _apply_creator_preset(self, preset_id: int):
        """Check only lore checkboxes matching the preset's lore_ids."""
        presets = self.db.get_all_lore_presets()
        target_ids: set[int] = set()
        for p in presets:
            if p["id"] == preset_id:
                target_ids = set(p["lore_ids"])
                break

        for lore_id, cb in self._lore_checkboxes:
            cb.setChecked(lore_id in target_ids)

    def _select_all_lore(self):
        """Check all lore checkboxes."""
        for _, cb in self._lore_checkboxes:
            cb.setChecked(True)

    def _deselect_all_lore(self):
        """Uncheck all lore checkboxes."""
        for _, cb in self._lore_checkboxes:
            cb.setChecked(False)

    def _update_category_checkbox(self, category: str):
        """Sync the category checkbox state from its children."""
        cat_cb = self._category_checkboxes.get(category)
        if cat_cb is None:
            return

        children = [
            cb for lore_id, cb in self._lore_checkboxes
            if self._lore_category_for_id(lore_id) == category
        ]
        if not children:
            return

        checked_count = sum(1 for cb in children if cb.isChecked())

        cat_cb.blockSignals(True)
        if checked_count == 0:
            cat_cb.setCheckState(Qt.CheckState.Unchecked)
        elif checked_count == len(children):
            cat_cb.setCheckState(Qt.CheckState.Checked)
        else:
            cat_cb.setCheckState(Qt.CheckState.PartiallyChecked)
        cat_cb.blockSignals(False)

    def _on_category_toggled(self, category: str, state: int):
        """Toggle all children when the category checkbox changes."""
        # Ignore partial state — only react to checked/unchecked
        if state == Qt.CheckState.PartiallyChecked.value:
            return
        checked = (state == Qt.CheckState.Checked.value)
        for lore_id, cb in self._lore_checkboxes:
            if self._lore_category_for_id(lore_id) == category:
                cb.blockSignals(True)
                cb.setChecked(checked)
                cb.blockSignals(False)

    def _lore_category_for_id(self, lore_id: int) -> str:
        """Look up the category for a lore entry by its id (cached)."""
        return self._lore_id_to_category.get(lore_id, "general")

    # ------------------------------------------------------------------
    # Lore preview
    # ------------------------------------------------------------------

    def _on_select_lore(self):
        """Format selected lore entries and show them in the editable preview."""
        selected = self._get_selected_lore()
        if not selected:
            self._lore_preview.setPlainText("")
            self._lore_preview_label.setVisible(True)
            self._lore_preview.setVisible(True)
            QMessageBox.information(
                self, "No Lore Selected",
                "No lore entries are checked. The song will be generated "
                "without lore context, or you can type lore directly into "
                "the preview box.",
            )
            return

        lore_block = "\n\n".join(
            f"### {entry['title']}\n{entry['content']}"
            for entry in selected
        )
        self._lore_preview.setPlainText(lore_block)
        self._lore_preview_label.setVisible(True)
        self._lore_preview.setVisible(True)

    # ------------------------------------------------------------------
    # Generation workflow
    # ------------------------------------------------------------------

    def generate_song(self):
        """Validate inputs, then kick off background generation."""
        # 1. Check API key
        api_key = self.db.get_config("api_key")
        if not api_key:
            QMessageBox.warning(
                self,
                "API Key Missing",
                "Please set your Anthropic API key in the Settings tab before "
                "generating songs.",
            )
            return

        # Check that user provided some input
        user_input = self.input_text.toPlainText().strip()
        if not user_input:
            QMessageBox.warning(
                self,
                "Input Required",
                "Please describe what you want the song to be about.",
            )
            return

        # 2. Gather selected genre info
        genre_data = self.genre_combo.currentData()
        genre_name = None
        genre_prompt_template = None
        if genre_data is not None:
            genre_name = genre_data.get("name")
            genre_prompt_template = genre_data.get("prompt_template")

        # 3. Gather style notes
        style_notes = self.style_input.text().strip() or None

        # 4. Gather lore — use the editable preview text if visible,
        #    otherwise fall back to checkbox selection
        lore_text = None
        active_lore = []
        if self._lore_preview.isVisible():
            lore_text = self._lore_preview.toPlainText().strip() or None
        else:
            active_lore = self._get_selected_lore()

        # 5. Show busy state
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("Generating...")

        # 6. Launch worker thread
        self._worker = GenerateWorker(
            api_key=api_key,
            user_input=user_input,
            active_lore=active_lore,
            lore_text=lore_text,
            genre_name=genre_name,
            genre_prompt_template=genre_prompt_template,
            style_notes=style_notes,
            parent=self,
        )
        self.register_worker(self._worker)
        self._worker.finished.connect(self.on_generation_complete)
        self._worker.error.connect(self._on_generation_error)
        self._worker.start()

    def _get_selected_lore(self) -> list[dict]:
        """Return lore dicts for every checked checkbox."""
        selected_ids = {
            lore_id for lore_id, cb in self._lore_checkboxes if cb.isChecked()
        }
        if not selected_ids:
            return []

        all_lore = self.db.get_all_lore()
        return [entry for entry in all_lore if entry["id"] in selected_ids]

    def on_generation_complete(self, result: dict):
        """Populate output fields with the generation result."""
        self._last_result = result

        self.prompt_output.setPlainText(result.get("prompt", ""))
        self.lyrics_output.setPlainText(result.get("lyrics", ""))
        self.update_char_count()

        # Restore button
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Song")

    def _on_generation_error(self, error_message: str):
        """Show error details and restore the button."""
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Song")

        QMessageBox.critical(
            self,
            "Generation Failed",
            f"Song generation encountered an error:\n\n{error_message}",
        )

    # ------------------------------------------------------------------
    # Character counter
    # ------------------------------------------------------------------

    def update_char_count(self):
        """Update the character counter label beneath the prompt field."""
        count = len(self.prompt_output.toPlainText())
        self.char_count_label.setText(f"{count} / 300")
        if count <= 300:
            self.char_count_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 12px;")
        else:
            self.char_count_label.setStyleSheet(f"color: {Theme.ERROR}; font-size: 12px;")

    # ------------------------------------------------------------------
    # Save / copy actions
    # ------------------------------------------------------------------

    def save_song(self, status: str = "draft"):
        """Save the current song to the database."""
        prompt_text = self.prompt_output.toPlainText().strip()
        lyrics_text = self.lyrics_output.toPlainText().strip()

        # Derive title from last result or use placeholder
        title = "Untitled Song"
        if self._last_result:
            title = self._last_result.get("title", title)

        errors = validate_song(title, prompt_text, lyrics_text)
        if errors:
            msg = "\n".join(f"- {e.field}: {e.message}" for e in errors)
            QMessageBox.warning(self, "Validation Error", msg)
            return

        # Determine genre label from the last generation result,
        # falling back to sensible defaults. (title already derived above)
        genre_label = "Unknown"
        genre_id = None

        if self._last_result:
            genre_label = self._last_result.get("genre_label", genre_label)

        # Try to match genre_id from the combo selection
        genre_data = self.genre_combo.currentData()
        if genre_data is not None:
            genre_id = genre_data.get("id")

        user_input = self.input_text.toPlainText().strip() or None

        # Build a lore snapshot of selected lore titles
        selected_lore = self._get_selected_lore()
        lore_snapshot = None
        if selected_lore:
            lore_snapshot = json.dumps(
                [{"title": e["title"], "content": e["content"]} for e in selected_lore],
                indent=2,
            )

        try:
            song_id = self.db.add_song(
                title=title,
                genre_id=genre_id,
                genre_label=genre_label,
                prompt=prompt_text,
                lyrics=lyrics_text,
                user_input=user_input,
                lore_snapshot=lore_snapshot,
                status=status,
            )
            status_label = "saved" if status == "draft" else "queued"
            QMessageBox.information(
                self,
                "Song Saved",
                f'"{title}" has been {status_label} (ID: {song_id}).',
            )
            event_bus.songs_changed.emit()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Could not save song to the database:\n\n{exc}",
            )

    def copy_to_clipboard(self, text: str):
        """Copy the given text to the system clipboard."""
        if not text.strip():
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

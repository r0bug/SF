"""
Lore Editor Tab — manage lore entries used as generation context.

Provides a horizontal split layout with a filterable list on the left and a
full editor on the right.  Changes auto-save on a 2-second debounce timer
and when switching between entries.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QCheckBox,
    QLabel,
    QMessageBox,
    QGroupBox,
    QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from tabs.base_tab import BaseTab
from theme import Theme
from event_bus import event_bus
from validators import validate_lore

_CATEGORIES = ["people", "places", "events", "themes", "rules", "general"]
_FILTER_OPTIONS = ["All"] + _CATEGORIES

_STYLESHEET = f"""
    QWidget {{
        background-color: {Theme.BG};
        color: {Theme.TEXT};
    }}

    QSplitter::handle {{
        background-color: {Theme.PANEL};
        width: 2px;
    }}

    QListWidget {{
        background-color: {Theme.PANEL};
        border: 1px solid #444444;
        border-radius: 4px;
        padding: 4px;
        font-size: 13px;
    }}
    QListWidget::item {{
        padding: 6px 8px;
        border-bottom: 1px solid #444444;
    }}
    QListWidget::item:selected {{
        background-color: {Theme.ACCENT};
        color: #1e1e1e;
    }}

    QComboBox {{
        background-color: {Theme.PANEL};
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 5px 8px;
        color: {Theme.TEXT};
        min-height: 24px;
    }}
    QComboBox::drop-down {{
        border: none;
    }}
    QComboBox QAbstractItemView {{
        background-color: {Theme.PANEL};
        color: {Theme.TEXT};
        selection-background-color: {Theme.ACCENT};
        selection-color: #1e1e1e;
    }}

    QLineEdit {{
        background-color: {Theme.PANEL};
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 6px 8px;
        color: {Theme.TEXT};
        font-size: 14px;
    }}
    QLineEdit:focus {{
        border-color: {Theme.ACCENT};
    }}

    QTextEdit {{
        background-color: {Theme.PANEL};
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 6px;
        color: {Theme.TEXT};
        font-size: 13px;
    }}
    QTextEdit:focus {{
        border-color: {Theme.ACCENT};
    }}

    QCheckBox {{
        color: {Theme.TEXT};
        spacing: 8px;
        font-size: 13px;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 1px solid #555555;
        border-radius: 3px;
        background-color: {Theme.PANEL};
    }}
    QCheckBox::indicator:checked {{
        background-color: {Theme.ACCENT};
        border-color: {Theme.ACCENT};
    }}

    QPushButton {{
        background-color: {Theme.ACCENT};
        color: #1e1e1e;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: bold;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: #f0b848;
    }}
    QPushButton:pressed {{
        background-color: #d09828;
    }}

    QPushButton#deleteButton {{
        background-color: #c0392b;
        color: {Theme.TEXT};
    }}
    QPushButton#deleteButton:hover {{
        background-color: #e74c3c;
    }}
    QPushButton#deleteButton:pressed {{
        background-color: #a93226;
    }}

    QLabel {{
        color: {Theme.TEXT};
        font-size: 12px;
    }}
    QLabel#sectionLabel {{
        font-weight: bold;
        font-size: 13px;
        color: {Theme.ACCENT};
    }}
"""


class LoreEditorTab(BaseTab):
    """Lore management tab with list + editor split layout."""

    # The id of the lore entry currently loaded in the editor, or None.
    _current_id: int | None = None

    # Guard flag to suppress save while programmatically loading an entry.
    _loading: bool = False

    def __init__(self, db, parent=None):
        self._presets_cache: list[dict] = []
        super().__init__(db, parent)
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self):
        self.setStyleSheet(_STYLESHEET)
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root_layout.addWidget(splitter)

        # ---- Left sidebar ----
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(6)

        filter_label = QLabel("Filter by category")
        filter_label.setObjectName("sectionLabel")
        sidebar_layout.addWidget(filter_label)

        self.category_filter = QComboBox()
        self.category_filter.addItems(_FILTER_OPTIONS)
        sidebar_layout.addWidget(self.category_filter)

        # ---- Bulk toggle buttons ----
        bulk_row = QHBoxLayout()
        bulk_row.setSpacing(4)

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setFixedHeight(28)
        self.select_all_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; padding: 2px 8px; }}"
        )
        bulk_row.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.setFixedHeight(28)
        self.deselect_all_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; padding: 2px 8px; }}"
        )
        bulk_row.addWidget(self.deselect_all_btn)

        self.toggle_category_btn = QPushButton("Toggle Category")
        self.toggle_category_btn.setFixedHeight(28)
        self.toggle_category_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; padding: 2px 8px; }}"
        )
        self.toggle_category_btn.setEnabled(False)
        bulk_row.addWidget(self.toggle_category_btn)

        sidebar_layout.addLayout(bulk_row)

        self.lore_list = QListWidget()
        sidebar_layout.addWidget(self.lore_list, stretch=1)

        # ---- Presets section ----
        presets_group = QGroupBox("Presets")
        presets_group.setStyleSheet(
            f"QGroupBox {{ color: {Theme.ACCENT}; font-weight: bold; "
            f"border: 1px solid #555; border-radius: 4px; "
            f"margin-top: 6px; padding-top: 14px; }} "
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; }}"
        )
        presets_layout = QVBoxLayout(presets_group)
        presets_layout.setContentsMargins(6, 4, 6, 6)
        presets_layout.setSpacing(4)

        self.preset_combo = QComboBox()
        presets_layout.addWidget(self.preset_combo)

        preset_btn_row = QHBoxLayout()
        preset_btn_row.setSpacing(4)

        self.preset_apply_btn = QPushButton("Apply")
        self.preset_apply_btn.setFixedHeight(28)
        self.preset_apply_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; padding: 2px 8px; }}"
        )
        preset_btn_row.addWidget(self.preset_apply_btn)

        self.preset_save_btn = QPushButton("Save New")
        self.preset_save_btn.setFixedHeight(28)
        self.preset_save_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; padding: 2px 8px; }}"
        )
        preset_btn_row.addWidget(self.preset_save_btn)

        self.preset_update_btn = QPushButton("Update")
        self.preset_update_btn.setFixedHeight(28)
        self.preset_update_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; padding: 2px 8px; }}"
        )
        self.preset_update_btn.setToolTip(
            "Overwrite the selected preset with the currently active lore entries"
        )
        preset_btn_row.addWidget(self.preset_update_btn)

        self.preset_delete_btn = QPushButton("Delete")
        self.preset_delete_btn.setFixedHeight(28)
        self.preset_delete_btn.setObjectName("deleteButton")
        self.preset_delete_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; padding: 2px 8px; "
            f"background-color: #c0392b; color: {Theme.TEXT}; }} "
            f"QPushButton:hover {{ background-color: #e74c3c; }}"
        )
        preset_btn_row.addWidget(self.preset_delete_btn)

        presets_layout.addLayout(preset_btn_row)
        sidebar_layout.addWidget(presets_group)

        self.add_button = QPushButton("Add New Lore")
        sidebar_layout.addWidget(self.add_button)

        splitter.addWidget(sidebar)

        # ---- Main editor area ----
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(10)

        title_label = QLabel("Title")
        title_label.setObjectName("sectionLabel")
        editor_layout.addWidget(title_label)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Lore entry title...")
        editor_layout.addWidget(self.title_edit)

        category_label = QLabel("Category")
        category_label.setObjectName("sectionLabel")
        editor_layout.addWidget(category_label)

        self.category_combo = QComboBox()
        self.category_combo.addItems(_CATEGORIES)
        editor_layout.addWidget(self.category_combo)

        self.active_check = QCheckBox("Active (included in generation context)")
        editor_layout.addWidget(self.active_check)

        content_label = QLabel("Content")
        content_label.setObjectName("sectionLabel")
        editor_layout.addWidget(content_label)

        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("Write lore content in markdown...")
        mono_font = QFont("Courier New", 12)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.content_edit.setFont(mono_font)
        editor_layout.addWidget(self.content_edit, stretch=1)

        # ---- Button row ----
        btn_row = QHBoxLayout()

        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("saveButton")
        btn_row.addWidget(self.save_button)

        btn_row.addStretch()

        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("deleteButton")
        btn_row.addWidget(self.delete_button)

        editor_layout.addLayout(btn_row)

        splitter.addWidget(editor)

        # Sidebar ~30%, editor ~70%
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        # Start with editor disabled until an entry is selected.
        self._set_editor_enabled(False)

        # ---- Unsaved-changes tracking ----
        self._dirty = False

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self.lore_list.currentItemChanged.connect(self._on_item_changed)
        self.add_button.clicked.connect(self.add_new_lore)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.delete_button.clicked.connect(self.delete_lore)
        self.category_filter.currentIndexChanged.connect(self.on_category_filter_changed)

        # Bulk toggle buttons
        self.select_all_btn.clicked.connect(self._on_select_all)
        self.deselect_all_btn.clicked.connect(self._on_deselect_all)
        self.toggle_category_btn.clicked.connect(self._on_toggle_category)

        # Preset buttons
        self.preset_apply_btn.clicked.connect(self._on_preset_apply)
        self.preset_save_btn.clicked.connect(self._on_preset_save)
        self.preset_update_btn.clicked.connect(self._on_preset_update)
        self.preset_delete_btn.clicked.connect(self._on_preset_delete)

        # Editor fields mark the entry as dirty.
        self.title_edit.textChanged.connect(self._mark_dirty)
        self.content_edit.textChanged.connect(self._mark_dirty)
        self.category_combo.currentIndexChanged.connect(self._mark_dirty)
        self.active_check.stateChanged.connect(self._mark_dirty)

    # ------------------------------------------------------------------
    # Refresh (BaseTab contract)
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload the lore list and presets from the database."""
        self.load_lore_list()
        self.refresh_presets()

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def load_lore_list(self):
        """Reload the list widget, applying the active category filter."""
        self.lore_list.blockSignals(True)

        # Remember currently selected id so we can re-select it.
        prev_id = self._current_id

        self.lore_list.clear()
        all_lore = self.db.get_all_lore()

        selected_filter = self.category_filter.currentText()

        reselect_item: QListWidgetItem | None = None

        for entry in all_lore:
            if selected_filter != "All" and entry["category"] != selected_filter:
                continue

            tag = entry["category"] if entry["category"] else "general"
            display_text = f"{entry['title']}  [{tag}]"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])

            # Visual indicator for inactive entries: dimmed text.
            if not entry["active"]:
                item.setForeground(QColor(Theme.DIMMED))
            else:
                item.setForeground(QColor(Theme.TEXT))

            self.lore_list.addItem(item)

            if entry["id"] == prev_id:
                reselect_item = item

        self.lore_list.blockSignals(False)

        # Re-select the previously selected entry if it's still visible.
        if reselect_item is not None:
            self.lore_list.setCurrentItem(reselect_item)
        else:
            # Nothing selected — clear the editor.
            self._current_id = None
            self._clear_editor()
            self._set_editor_enabled(False)

    # ------------------------------------------------------------------
    # Item selection
    # ------------------------------------------------------------------

    def _on_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handle switching between list items."""
        # Save the entry we're leaving (if any) — quietly, no list refresh.
        if previous is not None and self._current_id is not None and self._dirty:
            self._save_to_db()

        if current is None:
            self._current_id = None
            self._clear_editor()
            self._set_editor_enabled(False)
            return

        self.on_item_selected(current)

    def on_item_selected(self, item: QListWidgetItem | None = None):
        """Load the selected lore entry into the editor fields."""
        if item is None:
            item = self.lore_list.currentItem()
        if item is None:
            return

        lore_id = item.data(Qt.ItemDataRole.UserRole)
        entry = self.db.get_lore(lore_id)
        if entry is None:
            return

        self._loading = True
        self._current_id = entry["id"]

        self.title_edit.setText(entry["title"])
        self.content_edit.setPlainText(entry["content"])

        cat_index = self.category_combo.findText(entry["category"])
        if cat_index >= 0:
            self.category_combo.setCurrentIndex(cat_index)
        else:
            self.category_combo.setCurrentIndex(0)

        self.active_check.setChecked(bool(entry["active"]))
        self._set_editor_enabled(True)
        self._dirty = False
        self._loading = False

    # ------------------------------------------------------------------
    # Save / auto-save
    # ------------------------------------------------------------------

    def _mark_dirty(self):
        """Track that the editor has unsaved changes."""
        if not self._loading and self._current_id is not None:
            self._dirty = True

    def _save_to_db(self):
        """Persist the current editor contents to the database (no list refresh)."""
        if self._current_id is None or self._loading:
            return

        title = self.title_edit.text().strip()
        content = self.content_edit.toPlainText()
        category = self.category_combo.currentText()
        active = int(self.active_check.isChecked())

        self.db.update_lore(
            self._current_id,
            title=title,
            content=content,
            category=category,
            active=active,
        )
        self._dirty = False

    def save_current(self):
        """Save and refresh — called by the Save button and other explicit actions."""
        self._save_to_db()
        self.load_lore_list()
        event_bus.lore_changed.emit()

    def _on_save_clicked(self):
        """Handle Save button click with validation."""
        if self._current_id is None:
            return

        title = self.title_edit.text().strip()
        content = self.content_edit.toPlainText()

        errors = validate_lore(title, content)
        if errors:
            msg = "\n".join(f"- {e.field}: {e.message}" for e in errors)
            QMessageBox.warning(self, "Validation Error", msg)
            return

        self.save_current()

    # ------------------------------------------------------------------
    # Add / delete
    # ------------------------------------------------------------------

    def add_new_lore(self):
        """Create a new lore entry with sensible defaults and select it."""
        # Save anything pending first.
        if self._current_id is not None and self._dirty:
            self._save_to_db()

        new_id = self.db.add_lore(
            title="New Lore Entry",
            content="",
            category="people",
            active=True,
        )

        self._current_id = new_id
        self.load_lore_list()
        event_bus.lore_changed.emit()

        # If the filter hides the new entry, switch filter to "All".
        if self.lore_list.currentItem() is None or (
            self.lore_list.currentItem()
            and self.lore_list.currentItem().data(Qt.ItemDataRole.UserRole) != new_id
        ):
            self.category_filter.setCurrentIndex(0)  # "All"
            self.load_lore_list()

        # Focus the title field for immediate editing.
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def delete_lore(self):
        """Delete the current lore entry after confirmation."""
        if self._current_id is None:
            return

        reply = QMessageBox.question(
            self,
            "Delete Lore Entry",
            "Are you sure you want to delete this lore entry?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.db.delete_lore(self._current_id)
        self._current_id = None
        self._clear_editor()
        self._set_editor_enabled(False)
        self.load_lore_list()
        event_bus.lore_changed.emit()

    # ------------------------------------------------------------------
    # Category filter
    # ------------------------------------------------------------------

    def on_category_filter_changed(self):
        """Re-filter the list when the category combo changes."""
        if self._current_id is not None and self._dirty:
            self._save_to_db()
        self.load_lore_list()
        self._update_toggle_category_label()

    # ------------------------------------------------------------------
    # Editor helpers
    # ------------------------------------------------------------------

    def _clear_editor(self):
        """Reset all editor fields to empty/default without triggering saves."""
        self._loading = True
        self.title_edit.clear()
        self.content_edit.clear()
        self.category_combo.setCurrentIndex(0)
        self.active_check.setChecked(True)
        self._loading = False

    def _set_editor_enabled(self, enabled: bool):
        """Enable or disable all editor widgets."""
        self.title_edit.setEnabled(enabled)
        self.content_edit.setEnabled(enabled)
        self.category_combo.setEnabled(enabled)
        self.active_check.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Bulk toggle handlers
    # ------------------------------------------------------------------

    def _on_select_all(self):
        """Activate all lore entries."""
        self.db.set_all_lore_active(True)
        self.load_lore_list()
        event_bus.lore_changed.emit()

    def _on_deselect_all(self):
        """Deactivate all lore entries."""
        self.db.set_all_lore_active(False)
        self.load_lore_list()
        event_bus.lore_changed.emit()

    def _on_toggle_category(self):
        """Toggle all entries in the currently filtered category."""
        selected_filter = self.category_filter.currentText()
        if selected_filter == "All":
            return

        # Determine majority state: if most are active, disable; otherwise enable.
        all_lore = self.db.get_all_lore()
        cat_entries = [e for e in all_lore if e["category"] == selected_filter]
        if not cat_entries:
            return
        active_count = sum(1 for e in cat_entries if e["active"])
        new_active = active_count <= len(cat_entries) // 2

        self.db.set_category_lore_active(selected_filter, new_active)
        self.load_lore_list()
        event_bus.lore_changed.emit()
        self._update_toggle_category_label()

    def _update_toggle_category_label(self):
        """Update the Toggle Category button label and enabled state."""
        selected_filter = self.category_filter.currentText()
        if selected_filter == "All":
            self.toggle_category_btn.setEnabled(False)
            self.toggle_category_btn.setText("Toggle Category")
            return

        self.toggle_category_btn.setEnabled(True)
        all_lore = self.db.get_all_lore()
        cat_entries = [e for e in all_lore if e["category"] == selected_filter]
        if not cat_entries:
            self.toggle_category_btn.setText(f"Enable {selected_filter}")
            return
        active_count = sum(1 for e in cat_entries if e["active"])
        if active_count > len(cat_entries) // 2:
            self.toggle_category_btn.setText(f"Disable {selected_filter}")
        else:
            self.toggle_category_btn.setText(f"Enable {selected_filter}")

    # ------------------------------------------------------------------
    # Preset handlers
    # ------------------------------------------------------------------

    def refresh_presets(self):
        """Reload the preset dropdown from the database."""
        self.preset_combo.clear()
        self._presets_cache = self.db.get_all_lore_presets()
        if not self._presets_cache:
            self.preset_combo.addItem("(no presets)")
            self.preset_apply_btn.setEnabled(False)
            self.preset_update_btn.setEnabled(False)
            self.preset_delete_btn.setEnabled(False)
            return
        self.preset_apply_btn.setEnabled(True)
        self.preset_update_btn.setEnabled(True)
        self.preset_delete_btn.setEnabled(True)
        for preset in self._presets_cache:
            self.preset_combo.addItem(preset["name"], preset["id"])

    def _on_preset_apply(self):
        """Apply the selected preset — deactivate all lore then activate preset IDs."""
        preset_id = self.preset_combo.currentData()
        if preset_id is None:
            return
        self.db.apply_lore_preset(preset_id)
        self.load_lore_list()
        event_bus.lore_changed.emit()

    def _on_preset_save(self):
        """Save the currently active lore IDs as a new preset."""
        name, ok = QInputDialog.getText(
            self, "Save Preset", "Preset name:"
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        active_lore = self.db.get_active_lore()
        if not active_lore:
            QMessageBox.warning(
                self, "No Active Lore",
                "Activate at least one lore entry before saving a preset.",
            )
            return

        lore_ids = [e["id"] for e in active_lore]
        try:
            self.db.add_lore_preset(name, lore_ids)
        except Exception as exc:
            QMessageBox.warning(
                self, "Save Failed",
                f"Could not save preset:\n\n{exc}",
            )
            return
        self.refresh_presets()

    def _on_preset_update(self):
        """Overwrite the selected preset with the currently active lore entries."""
        preset_id = self.preset_combo.currentData()
        if preset_id is None:
            return
        preset_name = self.preset_combo.currentText()

        active_lore = self.db.get_active_lore()
        if not active_lore:
            QMessageBox.warning(
                self, "No Active Lore",
                "Activate at least one lore entry before updating a preset.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Update Preset",
            f'Overwrite preset "{preset_name}" with the current active lore entries?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        lore_ids = [e["id"] for e in active_lore]
        self.db.update_lore_preset(preset_id, lore_ids=lore_ids)
        self.refresh_presets()

    def _on_preset_delete(self):
        """Delete the selected preset after confirmation."""
        preset_id = self.preset_combo.currentData()
        if preset_id is None:
            return
        preset_name = self.preset_combo.currentText()

        reply = QMessageBox.question(
            self,
            "Delete Preset",
            f'Delete preset "{preset_name}"?\n\nThis will not change any lore entries.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.db.delete_lore_preset(preset_id)
        self.refresh_presets()

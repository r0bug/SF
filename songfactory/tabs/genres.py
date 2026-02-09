"""
Genre Manager Tab

Provides a PyQt6 widget for managing music genres: viewing, creating,
editing, deleting, and toggling the active state of genre entries stored
in the Song Factory database.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QTextEdit,
    QCheckBox,
    QPushButton,
    QLabel,
    QMessageBox,
    QAbstractItemView,
    QSplitter,
)
from PyQt6.QtCore import Qt


# ---------------------------------------------------------------------------
# Stylesheet constants
# ---------------------------------------------------------------------------

_DARK_BG = "#2b2b2b"
_PANEL_BG = "#353535"
_TEXT_COLOR = "#e0e0e0"
_ACCENT = "#E8A838"
_ROW_ALT = "#2f2f2f"
_ROW_BASE = "#353535"
_SELECTION_BG = "#4a4a4a"
_BORDER_COLOR = "#555555"

_STYLESHEET = f"""
    QWidget {{
        background-color: {_DARK_BG};
        color: {_TEXT_COLOR};
        font-size: 13px;
    }}
    QTableWidget {{
        background-color: {_PANEL_BG};
        alternate-background-color: {_ROW_ALT};
        gridline-color: {_BORDER_COLOR};
        border: 1px solid {_BORDER_COLOR};
        selection-background-color: {_SELECTION_BG};
        selection-color: {_TEXT_COLOR};
    }}
    QTableWidget::item {{
        padding: 4px 8px;
    }}
    QHeaderView::section {{
        background-color: {_PANEL_BG};
        color: {_ACCENT};
        font-weight: bold;
        border: 1px solid {_BORDER_COLOR};
        padding: 6px 8px;
    }}
    QLineEdit, QTextEdit {{
        background-color: {_PANEL_BG};
        color: {_TEXT_COLOR};
        border: 1px solid {_BORDER_COLOR};
        border-radius: 4px;
        padding: 6px;
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border: 1px solid {_ACCENT};
    }}
    QLabel {{
        color: {_ACCENT};
        font-weight: bold;
        background-color: transparent;
    }}
    QCheckBox {{
        color: {_TEXT_COLOR};
        spacing: 6px;
        background-color: transparent;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {_BORDER_COLOR};
        border-radius: 3px;
        background-color: {_PANEL_BG};
    }}
    QCheckBox::indicator:checked {{
        background-color: {_ACCENT};
        border-color: {_ACCENT};
    }}
    QPushButton {{
        background-color: {_PANEL_BG};
        color: {_TEXT_COLOR};
        border: 1px solid {_BORDER_COLOR};
        border-radius: 4px;
        padding: 8px 18px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {_SELECTION_BG};
        border-color: {_ACCENT};
    }}
    QPushButton:pressed {{
        background-color: {_ACCENT};
        color: {_DARK_BG};
    }}
    QPushButton#saveBtn {{
        background-color: {_ACCENT};
        color: {_DARK_BG};
        border-color: {_ACCENT};
    }}
    QPushButton#saveBtn:hover {{
        background-color: #f0b848;
    }}
    QPushButton#deleteBtn {{
        border-color: #c0392b;
        color: #e74c3c;
    }}
    QPushButton#deleteBtn:hover {{
        background-color: #c0392b;
        color: {_TEXT_COLOR};
    }}
    QSplitter::handle {{
        background-color: {_BORDER_COLOR};
        height: 2px;
    }}
"""


class GenreManagerTab(QWidget):
    """Tab widget for managing genre definitions."""

    # Mapping of table column indices
    _COL_NAME = 0
    _COL_BPM = 1
    _COL_TEMPLATE = 2
    _COL_ACTIVE = 3

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._current_genre_id: int | None = None

        self._build_ui()
        self.setStyleSheet(_STYLESHEET)
        self.load_genres()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Assemble the full layout: table on top, detail panel below."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # --- Top: table ------------------------------------------------
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Name", "BPM Range", "Prompt Template", "Active"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            self._COL_NAME, QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(
            self._COL_BPM, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            self._COL_TEMPLATE, QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(
            self._COL_ACTIVE, QHeaderView.ResizeMode.ResizeToContents
        )

        self.table.itemSelectionChanged.connect(self.on_row_selected)

        table_layout.addWidget(self.table)
        splitter.addWidget(table_container)

        # --- Bottom: detail panel --------------------------------------
        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(8, 12, 8, 8)
        detail_layout.setSpacing(8)

        # Name
        detail_layout.addWidget(QLabel("Name"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Genre name")
        detail_layout.addWidget(self.name_edit)

        # Prompt Template
        detail_layout.addWidget(QLabel("Prompt Template"))
        self.template_edit = QTextEdit()
        self.template_edit.setPlaceholderText(
            "Default instrumental/vocal/tempo/mood description..."
        )
        self.template_edit.setMinimumHeight(80)
        self.template_edit.setMaximumHeight(160)
        detail_layout.addWidget(self.template_edit)

        # Description
        detail_layout.addWidget(QLabel("Description"))
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Notes about the genre style")
        detail_layout.addWidget(self.description_edit)

        # BPM Range
        detail_layout.addWidget(QLabel("BPM Range"))
        self.bpm_edit = QLineEdit()
        self.bpm_edit.setPlaceholderText("e.g. 110-130")
        detail_layout.addWidget(self.bpm_edit)

        # Active checkbox
        self.active_check = QCheckBox("Active")
        detail_layout.addWidget(self.active_check)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.clicked.connect(self.save_genre)

        self.add_btn = QPushButton("Add Genre")
        self.add_btn.clicked.connect(self.add_genre)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("deleteBtn")
        self.delete_btn.clicked.connect(self.delete_genre)

        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.add_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.delete_btn)

        detail_layout.addLayout(btn_row)
        detail_layout.addStretch()

        splitter.addWidget(detail_container)

        # Give the table more space by default (60/40 split)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        outer.addWidget(splitter)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_genres(self):
        """Reload the table contents from the database."""
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        genres = self.db.get_all_genres()

        self.table.setRowCount(len(genres))
        for row_idx, genre in enumerate(genres):
            # Name
            name_item = QTableWidgetItem(genre.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, genre["id"])
            self.table.setItem(row_idx, self._COL_NAME, name_item)

            # BPM Range
            bpm_item = QTableWidgetItem(genre.get("bpm_range", "") or "")
            self.table.setItem(row_idx, self._COL_BPM, bpm_item)

            # Prompt Template (truncated)
            template = genre.get("prompt_template", "") or ""
            truncated = (
                template[:57] + "..." if len(template) > 60 else template
            )
            template_item = QTableWidgetItem(truncated)
            template_item.setToolTip(template)
            self.table.setItem(row_idx, self._COL_TEMPLATE, template_item)

            # Active checkbox
            active_widget = QWidget()
            active_layout = QHBoxLayout(active_widget)
            active_layout.setContentsMargins(0, 0, 0, 0)
            active_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            active_cb = QCheckBox()
            active_cb.setChecked(bool(genre.get("active", False)))
            genre_id = genre["id"]
            active_cb.stateChanged.connect(
                lambda state, gid=genre_id: self.toggle_active(gid, state)
            )
            active_layout.addWidget(active_cb)
            self.table.setCellWidget(row_idx, self._COL_ACTIVE, active_widget)

        self.table.blockSignals(False)

        # Re-select the previously selected genre if it still exists
        if self._current_genre_id is not None:
            self._select_row_by_genre_id(self._current_genre_id)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def on_row_selected(self):
        """Populate the detail panel from the currently selected row."""
        selected = self.table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        name_item = self.table.item(row, self._COL_NAME)
        if name_item is None:
            return

        genre_id = name_item.data(Qt.ItemDataRole.UserRole)
        genre = self.db.get_genre(genre_id)
        if genre is None:
            return

        self._current_genre_id = genre_id
        self.name_edit.setText(genre.get("name", ""))
        self.template_edit.setPlainText(genre.get("prompt_template", "") or "")
        self.description_edit.setText(genre.get("description", "") or "")
        self.bpm_edit.setText(genre.get("bpm_range", "") or "")
        self.active_check.setChecked(bool(genre.get("active", False)))

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def save_genre(self):
        """Persist detail panel edits to the database for the selected genre."""
        if self._current_genre_id is None:
            QMessageBox.warning(
                self, "No Selection", "Select a genre to save changes."
            )
            return

        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Validation Error", "Genre name cannot be empty."
            )
            return

        prompt_template = self.template_edit.toPlainText().strip()
        if not prompt_template:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Prompt template cannot be empty.",
            )
            return

        self.db.update_genre(
            self._current_genre_id,
            name=name,
            prompt_template=prompt_template,
            description=self.description_edit.text().strip(),
            bpm_range=self.bpm_edit.text().strip(),
            active=int(self.active_check.isChecked()),
        )
        self.load_genres()

    def add_genre(self):
        """Create a new genre with default values, select it, and focus the
        name field for immediate editing."""
        new_id = self.db.add_genre(
            name="New Genre",
            prompt_template="Describe the genre style here...",
            description="",
            bpm_range="",
            active=True,
        )
        self._current_genre_id = new_id
        self.load_genres()
        self._select_row_by_genre_id(new_id)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def delete_genre(self):
        """Delete the selected genre after user confirmation."""
        if self._current_genre_id is None:
            QMessageBox.warning(
                self, "No Selection", "Select a genre to delete."
            )
            return

        genre = self.db.get_genre(self._current_genre_id)
        genre_name = genre.get("name", "this genre") if genre else "this genre"

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f'Are you sure you want to delete "{genre_name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.db.delete_genre(self._current_genre_id)
        self._current_genre_id = None
        self._clear_detail_panel()
        self.load_genres()

    def toggle_active(self, genre_id: int, state: int):
        """Toggle the active flag for a genre directly from the table checkbox."""
        self.db.toggle_genre_active(genre_id)

        # If the toggled genre is currently shown in the detail panel,
        # refresh its active checkbox to stay in sync.
        if genre_id == self._current_genre_id:
            genre = self.db.get_genre(genre_id)
            if genre is not None:
                self.active_check.setChecked(bool(genre.get("active", False)))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _select_row_by_genre_id(self, genre_id: int):
        """Find the table row holding *genre_id* and select it."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self._COL_NAME)
            if item and item.data(Qt.ItemDataRole.UserRole) == genre_id:
                self.table.selectRow(row)
                return

    def _clear_detail_panel(self):
        """Reset all detail panel fields to blank."""
        self.name_edit.clear()
        self.template_edit.clear()
        self.description_edit.clear()
        self.bpm_edit.clear()
        self.active_check.setChecked(False)

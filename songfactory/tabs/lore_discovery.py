"""
Lore Discovery Tab — search the web, summarize content, and save as lore.

Provides a two-panel layout: search results on the left with checkboxes,
and summarized lore entries on the right with inline editing and save
controls.  All network/API work runs on background QThreads.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QScrollArea,
    QCheckBox,
    QTextEdit,
    QFrame,
    QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from web_search import search, fetch_content, WebSearchError, SearchResult
from lore_summarizer import LoreSummarizer


# ---------------------------------------------------------------------------
# Style constants (dark theme — matches existing tabs)
# ---------------------------------------------------------------------------

_BG = "#2b2b2b"
_PANEL = "#353535"
_TEXT = "#e0e0e0"
_ACCENT = "#E8A838"
_DIMMED = "#808080"
_GREEN = "#4CAF50"
_RED = "#F44336"

_CATEGORIES = ["people", "places", "events", "themes", "rules"]

_STYLESHEET = f"""
    QWidget {{
        background-color: {_BG};
        color: {_TEXT};
    }}
    QSplitter::handle {{
        background-color: #454545;
        width: 3px;
    }}
    QLineEdit {{
        background-color: {_PANEL};
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 6px 8px;
        color: {_TEXT};
        font-size: 14px;
    }}
    QLineEdit:focus {{
        border-color: {_ACCENT};
    }}
    QComboBox {{
        background-color: {_PANEL};
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 5px 8px;
        color: {_TEXT};
        min-height: 24px;
    }}
    QComboBox::drop-down {{
        border: none;
    }}
    QComboBox QAbstractItemView {{
        background-color: {_PANEL};
        color: {_TEXT};
        selection-background-color: {_ACCENT};
        selection-color: #1e1e1e;
    }}
    QTextEdit {{
        background-color: {_PANEL};
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 6px;
        color: {_TEXT};
        font-size: 13px;
    }}
    QTextEdit:focus {{
        border-color: {_ACCENT};
    }}
    QCheckBox {{
        color: {_TEXT};
        spacing: 8px;
        font-size: 13px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid #555555;
        border-radius: 3px;
        background-color: {_PANEL};
    }}
    QCheckBox::indicator:checked {{
        background-color: {_ACCENT};
        border-color: {_ACCENT};
    }}
    QPushButton {{
        background-color: {_ACCENT};
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
    QPushButton:disabled {{
        background-color: #3a3a3a;
        color: #666666;
        border: 1px solid #444444;
    }}
    QPushButton#secondaryBtn {{
        background-color: #454545;
        color: {_TEXT};
        border: 1px solid #555555;
    }}
    QPushButton#secondaryBtn:hover {{
        background-color: #555555;
        border-color: {_ACCENT};
    }}
    QPushButton#secondaryBtn:disabled {{
        background-color: #3a3a3a;
        color: #666666;
    }}
    QLabel {{
        color: {_TEXT};
        font-size: 12px;
    }}
    QLabel#sectionLabel {{
        font-weight: bold;
        font-size: 13px;
        color: {_ACCENT};
    }}
    QLabel#statusLabel {{
        color: {_DIMMED};
        font-size: 12px;
    }}
    QScrollArea {{
        border: 1px solid #555555;
        border-radius: 4px;
        background-color: {_PANEL};
    }}
"""


# ===================================================================
# SearchWorker — runs DuckDuckGo search off the main thread
# ===================================================================

class SearchWorker(QThread):
    """Background worker for web searches."""

    results_ready = pyqtSignal(list)   # list[SearchResult]
    error = pyqtSignal(str)

    def __init__(self, query: str, max_results: int = 10, parent=None):
        super().__init__(parent)
        self._query = query
        self._max_results = max_results

    def run(self):
        try:
            results = search(self._query, max_results=self._max_results)
            self.results_ready.emit(results)
        except WebSearchError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"Search error: {exc}")


# ===================================================================
# SummarizeWorker — fetches pages + calls Anthropic to summarize
# ===================================================================

class SummarizeWorker(QThread):
    """Background worker that fetches page content and summarizes it."""

    progress = pyqtSignal(str)            # status message
    item_complete = pyqtSignal(int, dict)  # (index, summary_dict)
    item_error = pyqtSignal(int, str)      # (index, error_message)
    all_complete = pyqtSignal()

    def __init__(
        self,
        api_key: str,
        items: list[tuple[int, SearchResult]],  # (index, result)
        category: str = "general",
        parent=None,
    ):
        super().__init__(parent)
        self._api_key = api_key
        self._items = items
        self._category = category

    def run(self):
        summarizer = LoreSummarizer(api_key=self._api_key)

        for idx, result in self._items:
            self.progress.emit(f"Summarizing: {result.title}...")

            # Try fetching the full page; fall back to snippet
            content = result.snippet
            try:
                page_text = fetch_content(result.url)
                if page_text.strip():
                    content = page_text
            except WebSearchError:
                pass  # use snippet as fallback

            try:
                summary = summarizer.summarize(
                    title=result.title,
                    url=result.url,
                    content=content,
                    category=self._category,
                )
                self.item_complete.emit(idx, summary)
            except Exception as exc:
                self.item_error.emit(idx, str(exc))

        self.all_complete.emit()


# ===================================================================
# SummaryCard — inline editable summary widget
# ===================================================================

class SummaryCard(QFrame):
    """An editable card showing a single summarized lore entry."""

    def __init__(self, summary: dict, parent=None):
        super().__init__(parent)
        self.summary = summary
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"QFrame {{ background-color: {_PANEL}; border: 1px solid #555555; "
            f"border-radius: 6px; padding: 8px; }}"
        )
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Title
        title_label = QLabel("Title")
        title_label.setObjectName("sectionLabel")
        layout.addWidget(title_label)

        self.title_edit = QLineEdit(self.summary.get("title", ""))
        layout.addWidget(self.title_edit)

        # Category
        cat_label = QLabel("Category")
        cat_label.setObjectName("sectionLabel")
        layout.addWidget(cat_label)

        self.category_combo = QComboBox()
        self.category_combo.addItems(_CATEGORIES)
        cat = self.summary.get("category", "general")
        idx = self.category_combo.findText(cat)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        layout.addWidget(self.category_combo)

        # Content
        content_label = QLabel("Content")
        content_label.setObjectName("sectionLabel")
        layout.addWidget(content_label)

        self.content_edit = QTextEdit()
        self.content_edit.setPlainText(self.summary.get("content", ""))
        self.content_edit.setMinimumHeight(120)
        self.content_edit.setMaximumHeight(200)
        mono = QFont("Courier New", 11)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.content_edit.setFont(mono)
        layout.addWidget(self.content_edit)

        # Source
        source_url = self.summary.get("source_url", "")
        if source_url:
            src_label = QLabel(f"Source: {source_url}")
            src_label.setStyleSheet(f"color: {_DIMMED}; font-size: 11px;")
            src_label.setWordWrap(True)
            layout.addWidget(src_label)

        # Add to Lore button
        self.add_btn = QPushButton("Add This to Lore")
        self.add_btn.setObjectName("secondaryBtn")
        layout.addWidget(self.add_btn)

    def get_data(self) -> dict:
        """Return the current edited values."""
        return {
            "title": self.title_edit.text().strip(),
            "content": self.content_edit.toPlainText(),
            "category": self.category_combo.currentText(),
            "source_url": self.summary.get("source_url", ""),
        }


# ===================================================================
# SearchResultRow — checkbox + info for a single search result
# ===================================================================

class SearchResultRow(QFrame):
    """A checkbox row for a search result."""

    def __init__(self, index: int, result: SearchResult, parent=None):
        super().__init__(parent)
        self.index = index
        self.result = result
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            f"QFrame {{ border-bottom: 1px solid #444444; padding: 4px 0; }}"
        )
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.checkbox = QCheckBox(self.result.title)
        self.checkbox.setStyleSheet(f"font-weight: bold; font-size: 13px;")
        layout.addWidget(self.checkbox)

        snippet = QLabel(self.result.snippet[:200])
        snippet.setWordWrap(True)
        snippet.setStyleSheet(f"color: {_TEXT}; font-size: 12px; padding-left: 26px;")
        layout.addWidget(snippet)

        url_label = QLabel(self.result.url)
        url_label.setWordWrap(True)
        url_label.setStyleSheet(
            f"color: {_DIMMED}; font-size: 11px; padding-left: 26px;"
        )
        layout.addWidget(url_label)


# ===================================================================
# LoreDiscoveryTab
# ===================================================================

class LoreDiscoveryTab(QWidget):
    """Web research tab for discovering and importing lore."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._search_worker = None
        self._summarize_worker = None
        self._result_rows: list[SearchResultRow] = []
        self._summary_cards: list[SummaryCard] = []
        self._search_results: list[SearchResult] = []

        self.setStyleSheet(_STYLESHEET)
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ---- Top bar: search input + category + button ----
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for Yakima history, people, places...")
        self.search_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        top_bar.addWidget(self.search_input, stretch=3)

        cat_label = QLabel("Category:")
        top_bar.addWidget(cat_label)

        self.category_combo = QComboBox()
        self.category_combo.addItems(_CATEGORIES)
        top_bar.addWidget(self.category_combo)

        self.search_btn = QPushButton("Search")
        top_bar.addWidget(self.search_btn)

        root.addLayout(top_bar)

        # ---- Main splitter: results (left) | summaries (right) ----
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel — search results
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        results_label = QLabel("Search Results")
        results_label.setObjectName("sectionLabel")
        left_layout.addWidget(results_label)

        self._results_scroll = QScrollArea()
        self._results_scroll.setWidgetResizable(True)
        self._results_inner = QWidget()
        self._results_layout = QVBoxLayout(self._results_inner)
        self._results_layout.setContentsMargins(6, 6, 6, 6)
        self._results_layout.setSpacing(4)
        self._results_layout.addStretch()
        self._results_scroll.setWidget(self._results_inner)
        left_layout.addWidget(self._results_scroll, stretch=1)

        splitter.addWidget(left_widget)

        # Right panel — summaries
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        summary_label = QLabel("Summaries")
        summary_label.setObjectName("sectionLabel")
        right_layout.addWidget(summary_label)

        self._summary_scroll = QScrollArea()
        self._summary_scroll.setWidgetResizable(True)
        self._summary_inner = QWidget()
        self._summary_layout = QVBoxLayout(self._summary_inner)
        self._summary_layout.setContentsMargins(6, 6, 6, 6)
        self._summary_layout.setSpacing(8)
        self._summary_layout.addStretch()
        self._summary_scroll.setWidget(self._summary_inner)
        right_layout.addWidget(self._summary_scroll, stretch=1)

        # Add All to Lore button
        self.add_all_btn = QPushButton("Add All to Lore")
        self.add_all_btn.setEnabled(False)
        right_layout.addWidget(self.add_all_btn)

        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, stretch=1)

        # ---- Bottom bar: select all / deselect / summarize / status ----
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setObjectName("secondaryBtn")
        self.select_all_btn.setEnabled(False)
        bottom_bar.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.setObjectName("secondaryBtn")
        self.deselect_all_btn.setEnabled(False)
        bottom_bar.addWidget(self.deselect_all_btn)

        self.summarize_btn = QPushButton("Summarize Selected")
        self.summarize_btn.setEnabled(False)
        bottom_bar.addWidget(self.summarize_btn)

        bottom_bar.addStretch()

        self.status_label = QLabel("Status: Idle")
        self.status_label.setObjectName("statusLabel")
        bottom_bar.addWidget(self.status_label)

        root.addLayout(bottom_bar)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self.search_btn.clicked.connect(self._on_search)
        self.search_input.returnPressed.connect(self._on_search)
        self.select_all_btn.clicked.connect(self._select_all)
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        self.summarize_btn.clicked.connect(self._on_summarize)
        self.add_all_btn.clicked.connect(self._add_all_to_lore)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search(self):
        query = self.search_input.text().strip()
        if not query:
            return

        # Disable search button while running
        self.search_btn.setEnabled(False)
        self.search_btn.setText("Searching...")
        self.status_label.setText("Status: Searching...")

        # Clear previous results
        self._clear_results()

        self._search_worker = SearchWorker(query, parent=self)
        self._search_worker.results_ready.connect(self._on_search_results)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _on_search_results(self, results: list):
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")

        self._search_results = results

        if not results:
            self.status_label.setText("Status: No results found")
            return

        # Remove the stretch from results layout
        stretch_item = self._results_layout.takeAt(self._results_layout.count() - 1)

        for i, result in enumerate(results):
            row = SearchResultRow(i, result)
            self._result_rows.append(row)
            self._results_layout.addWidget(row)

        # Re-add stretch at end
        self._results_layout.addStretch()

        # Enable selection buttons
        self.select_all_btn.setEnabled(True)
        self.deselect_all_btn.setEnabled(True)
        self.summarize_btn.setEnabled(True)

        self.status_label.setText(f"Status: {len(results)} results found")

    def _on_search_error(self, error_msg: str):
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")
        self.status_label.setText("Status: Search failed")

        QMessageBox.warning(self, "Search Failed", error_msg)

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _select_all(self):
        for row in self._result_rows:
            row.checkbox.setChecked(True)

    def _deselect_all(self):
        for row in self._result_rows:
            row.checkbox.setChecked(False)

    def _get_selected(self) -> list[tuple[int, SearchResult]]:
        """Return (index, SearchResult) for every checked row."""
        selected = []
        for row in self._result_rows:
            if row.checkbox.isChecked():
                selected.append((row.index, row.result))
        return selected

    # ------------------------------------------------------------------
    # Summarize
    # ------------------------------------------------------------------

    def _on_summarize(self):
        selected = self._get_selected()
        if not selected:
            QMessageBox.warning(
                self,
                "Nothing Selected",
                "Please select one or more search results to summarize.",
            )
            return

        api_key = self.db.get_config("api_key")
        if not api_key:
            QMessageBox.warning(
                self,
                "API Key Missing",
                "Please set your Anthropic API key in the Settings tab.",
            )
            return

        # Disable controls while summarizing
        self.summarize_btn.setEnabled(False)
        self.summarize_btn.setText("Summarizing...")
        self.search_btn.setEnabled(False)

        category = self.category_combo.currentText()

        self._summarize_worker = SummarizeWorker(
            api_key=api_key,
            items=selected,
            category=category,
            parent=self,
        )
        self._summarize_worker.progress.connect(self._on_summarize_progress)
        self._summarize_worker.item_complete.connect(self._on_item_complete)
        self._summarize_worker.item_error.connect(self._on_item_error)
        self._summarize_worker.all_complete.connect(self._on_all_complete)
        self._summarize_worker.start()

    def _on_summarize_progress(self, msg: str):
        self.status_label.setText(f"Status: {msg}")

    def _on_item_complete(self, index: int, summary: dict):
        # Remove stretch, add card, re-add stretch
        if self._summary_layout.count() > 0:
            self._summary_layout.takeAt(self._summary_layout.count() - 1)

        card = SummaryCard(summary)
        card.add_btn.clicked.connect(lambda checked, c=card: self._add_card_to_lore(c))
        self._summary_cards.append(card)
        self._summary_layout.addWidget(card)
        self._summary_layout.addStretch()

        self.add_all_btn.setEnabled(True)

    def _on_item_error(self, index: int, error_msg: str):
        # Show error inline as a label
        if self._summary_layout.count() > 0:
            self._summary_layout.takeAt(self._summary_layout.count() - 1)

        title = ""
        if 0 <= index < len(self._search_results):
            title = self._search_results[index].title

        err_label = QLabel(f"Failed to summarize \"{title}\": {error_msg}")
        err_label.setWordWrap(True)
        err_label.setStyleSheet(f"color: {_RED}; font-size: 12px; padding: 8px;")
        self._summary_layout.addWidget(err_label)
        self._summary_layout.addStretch()

    def _on_all_complete(self):
        self.summarize_btn.setEnabled(True)
        self.summarize_btn.setText("Summarize Selected")
        self.search_btn.setEnabled(True)
        self.status_label.setText("Status: Summarization complete")

    # ------------------------------------------------------------------
    # Save to lore
    # ------------------------------------------------------------------

    def _add_card_to_lore(self, card: SummaryCard):
        """Save a single summary card to the lore database."""
        data = card.get_data()
        if not data["title"].strip() or not data["content"].strip():
            QMessageBox.warning(self, "Empty Entry", "Title and content are required.")
            return

        self.db.add_lore(
            title=data["title"],
            content=data["content"],
            category=data["category"],
            active=True,
        )

        # Visual feedback — disable the button
        card.add_btn.setText("Added!")
        card.add_btn.setEnabled(False)
        self.status_label.setText(f'Status: Added "{data["title"]}" to lore')

    def _add_all_to_lore(self):
        """Save all summary cards to the lore database."""
        added = 0
        for card in self._summary_cards:
            if not card.add_btn.isEnabled():
                continue  # already added
            data = card.get_data()
            if not data["title"].strip() or not data["content"].strip():
                continue

            self.db.add_lore(
                title=data["title"],
                content=data["content"],
                category=data["category"],
                active=True,
            )
            card.add_btn.setText("Added!")
            card.add_btn.setEnabled(False)
            added += 1

        if added > 0:
            self.status_label.setText(f"Status: Added {added} entries to lore")
        else:
            self.status_label.setText("Status: Nothing new to add")

    # ------------------------------------------------------------------
    # Cleanup helpers
    # ------------------------------------------------------------------

    def _clear_results(self):
        """Remove all search result rows."""
        self._result_rows.clear()
        self._search_results.clear()

        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._results_layout.addStretch()

        self.select_all_btn.setEnabled(False)
        self.deselect_all_btn.setEnabled(False)
        self.summarize_btn.setEnabled(False)

    def _clear_summaries(self):
        """Remove all summary cards."""
        self._summary_cards.clear()

        while self._summary_layout.count():
            item = self._summary_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._summary_layout.addStretch()
        self.add_all_btn.setEnabled(False)

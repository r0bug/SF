"""
Song Factory - Search Bar Widget

A search input field with configurable debounce timer.
Emits ``search_changed(str)`` after the debounce delay.
"""

from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtCore import QTimer, pyqtSignal

from theme import Theme


class SearchBar(QLineEdit):
    """Search input with debounce timer.

    Signals:
        search_changed(str): Emitted after the debounce delay with the
            current text.

    Args:
        placeholder: Placeholder text to display.
        debounce_ms: Debounce delay in milliseconds (default 300).
    """

    search_changed = pyqtSignal(str)

    def __init__(
        self, placeholder: str = "Search...", debounce_ms: int = 300, parent=None
    ):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._emit_search)

        self.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, _text: str) -> None:
        self._timer.start()

    def _emit_search(self) -> None:
        self.search_changed.emit(self.text())

"""
Song Factory - Log Viewer Widget

A read-only, auto-scrolling text display for status logs.
"""

from datetime import datetime

from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import Qt

from theme import Theme


class LogViewer(QTextEdit):
    """Read-only, auto-scrolling log display.

    Args:
        max_lines: Maximum number of lines to keep (0 = unlimited).
        show_timestamps: Whether to prepend timestamps to each line.
    """

    def __init__(
        self, max_lines: int = 500, show_timestamps: bool = True, parent=None
    ):
        super().__init__(parent)
        self.setReadOnly(True)
        self._max_lines = max_lines
        self._show_timestamps = show_timestamps
        self._line_count = 0
        self.setStyleSheet(
            f"QTextEdit {{"
            f"  background-color: {Theme.BG};"
            f"  color: {Theme.TEXT};"
            f"  border: 1px solid {Theme.BORDER};"
            f"  border-radius: 4px;"
            f"  font-family: monospace;"
            f"  font-size: 12px;"
            f"}}"
        )

    def append_line(self, message: str) -> None:
        """Append a line to the log, with optional timestamp."""
        if self._show_timestamps:
            ts = datetime.now().strftime("%H:%M:%S")
            line = f"[{ts}] {message}"
        else:
            line = message
        self.append(line)
        self._line_count += 1

        if self._max_lines and self._line_count > self._max_lines:
            self._trim()

        # Auto-scroll to bottom
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _trim(self) -> None:
        """Remove oldest lines to stay under max_lines."""
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        for _ in range(self._line_count - self._max_lines):
            cursor.movePosition(cursor.MoveOperation.EndOfBlock, cursor.MoveMode.KeepAnchor)
            cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        self._line_count = self._max_lines

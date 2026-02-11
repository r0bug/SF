"""
Song Factory - Status Badge Widget

A colored label that displays a status string with matching background color.
Used in Song Library, CD Master, and Distribution tabs.
"""

from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt

from theme import Theme


class StatusBadge(QLabel):
    """Colored status indicator label.

    Uses ``Theme.STATUS_COLORS`` for song statuses and
    ``Theme.DIST_STATUS_COLORS`` for distribution statuses.

    Args:
        status: The status string (e.g., "draft", "completed").
        color_map: Optional override for the status→color mapping.
                   Defaults to ``Theme.STATUS_COLORS``.
    """

    def __init__(self, status: str = "", color_map: dict = None, parent=None):
        super().__init__(parent)
        self._color_map = color_map or Theme.STATUS_COLORS
        self.set_status(status)

    def set_status(self, status: str) -> None:
        """Update the displayed status and color."""
        self.setText(status.capitalize())
        color = self._color_map.get(status, Theme.DIMMED)
        self.setStyleSheet(
            f"QLabel {{"
            f"  background-color: {color};"
            f"  color: white;"
            f"  padding: 2px 8px;"
            f"  border-radius: 3px;"
            f"  font-size: 11px;"
            f"  font-weight: bold;"
            f"}}"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

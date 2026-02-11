"""Song Factory - Tag Chips Widget

Renders a list of tag dicts as small colored chip labels in a horizontal
flow layout. Limits display to 4 visible chips with a "+N" overflow
indicator.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy


_MAX_VISIBLE = 4


class TagChipsWidget(QWidget):
    """Displays a row of colored tag chips for use in table cells."""

    def __init__(self, tags: list[dict], parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        visible = tags[:_MAX_VISIBLE]
        overflow = len(tags) - _MAX_VISIBLE

        for tag in visible:
            chip = QLabel(tag.get("name", ""))
            color = tag.get("color", "#888888")
            # Pick foreground based on color brightness
            fg = self._foreground_for(color)
            chip.setStyleSheet(
                f"background-color: {color};"
                f"color: {fg};"
                "border-radius: 3px;"
                "padding: 1px 6px;"
                "font-size: 10px;"
                "font-weight: bold;"
            )
            chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            chip.setFixedHeight(18)
            layout.addWidget(chip)

        if overflow > 0:
            more = QLabel(f"+{overflow}")
            more.setStyleSheet(
                "color: #AAAAAA;"
                "font-size: 10px;"
                "font-weight: bold;"
                "padding: 1px 4px;"
            )
            more.setFixedHeight(18)
            layout.addWidget(more)

        layout.addStretch()

    @staticmethod
    def _foreground_for(hex_color: str) -> str:
        """Return black or white foreground depending on background brightness."""
        try:
            c = hex_color.lstrip("#")
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            return "#000000" if luminance > 150 else "#FFFFFF"
        except (ValueError, IndexError):
            return "#FFFFFF"

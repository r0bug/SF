"""
Song Factory - Analytics Tab

Displays song production metrics using pure PyQt6 painting.
No external chart libraries required.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QRect, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush

from tabs.base_tab import BaseTab
from theme import Theme


class StatCard(QFrame):
    """A card widget showing a single metric with a large number and label."""

    def __init__(self, title: str, value: str = "0", color: str = Theme.ACCENT, parent=None):
        super().__init__(parent)
        self.setFixedHeight(90)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"QFrame {{ background-color: {Theme.PANEL}; border: 1px solid {Theme.BORDER}; "
            f"border-radius: 8px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        self._value_label = QLabel(value)
        self._value_label.setStyleSheet(
            f"color: {color}; font-size: 28px; font-weight: bold; "
            "background: transparent; border: none;"
        )
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._value_label)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(
            f"color: {Theme.DIMMED}; font-size: 11px; "
            "background: transparent; border: none;"
        )
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label)

    def set_value(self, value: str):
        self._value_label.setText(value)


class BarChartWidget(QWidget):
    """A simple horizontal bar chart widget using QPainter."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        self._data: list[tuple[str, int, str]] = []  # (label, value, color)
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, data: list[tuple[str, int, str]]):
        """Set chart data as list of (label, value, color) tuples."""
        self._data = data
        min_h = max(120, 30 + len(data) * 28)
        self.setMinimumHeight(min_h)
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Title
        painter.setPen(QColor(Theme.ACCENT))
        painter.setFont(QFont("sans-serif", 12, QFont.Weight.Bold))
        painter.drawText(QRect(8, 4, w - 16, 24), Qt.AlignmentFlag.AlignLeft, self._title)

        max_val = max((v for _, v, _ in self._data), default=1) or 1
        label_width = 100
        bar_start = label_width + 8
        bar_max_width = w - bar_start - 60
        y = 32

        painter.setFont(QFont("sans-serif", 10))

        for label, value, color in self._data:
            # Label
            painter.setPen(QColor(Theme.TEXT))
            painter.drawText(
                QRect(8, y, label_width, 22),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                label[:14],
            )

            # Bar
            bar_width = max(2, int((value / max_val) * bar_max_width))
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(bar_start, y + 2, bar_width, 18), 3, 3)

            # Value text
            painter.setPen(QColor(Theme.TEXT))
            painter.drawText(
                QRect(bar_start + bar_width + 6, y, 50, 22),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                str(value),
            )

            y += 26

        painter.end()


class AnalyticsTab(BaseTab):
    """Analytics dashboard showing song production metrics."""

    def __init__(self, db, parent=None):
        super().__init__(db, parent)
        self.refresh()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {Theme.BG}; }}")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Title
        title = QLabel("Analytics Dashboard")
        title.setStyleSheet(
            f"color: {Theme.ACCENT}; font-size: 18px; font-weight: bold;"
        )
        layout.addWidget(title)

        # Stat cards row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        self.total_songs_card = StatCard("Total Songs", "0", Theme.ACCENT)
        cards_row.addWidget(self.total_songs_card)

        self.completed_card = StatCard("Completed", "0", Theme.SUCCESS)
        cards_row.addWidget(self.completed_card)

        self.queued_card = StatCard("Queued", "0", "#2196F3")
        cards_row.addWidget(self.queued_card)

        self.error_card = StatCard("Errors", "0", Theme.ERROR)
        cards_row.addWidget(self.error_card)

        self.distributed_card = StatCard("Distributed", "0", "#9C27B0")
        cards_row.addWidget(self.distributed_card)

        layout.addLayout(cards_row)

        # Charts row
        charts_row = QHBoxLayout()
        charts_row.setSpacing(12)

        self.status_chart = BarChartWidget("Status Distribution")
        self.status_chart.setStyleSheet(
            f"background-color: {Theme.PANEL}; border: 1px solid {Theme.BORDER}; "
            "border-radius: 8px;"
        )
        charts_row.addWidget(self.status_chart)

        self.genre_chart = BarChartWidget("Top Genres")
        self.genre_chart.setStyleSheet(
            f"background-color: {Theme.PANEL}; border: 1px solid {Theme.BORDER}; "
            "border-radius: 8px;"
        )
        charts_row.addWidget(self.genre_chart)

        layout.addLayout(charts_row)

        # Monthly chart
        self.monthly_chart = BarChartWidget("Songs Created Per Month (Last 6 Months)")
        self.monthly_chart.setStyleSheet(
            f"background-color: {Theme.PANEL}; border: 1px solid {Theme.BORDER}; "
            "border-radius: 8px;"
        )
        layout.addWidget(self.monthly_chart)

        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def refresh(self):
        """Reload analytics data from the database."""
        songs = self.db.get_all_songs()
        distributions = []
        try:
            distributions = self.db.get_all_distributions()
        except Exception:
            pass

        # Stat cards
        total = len(songs)
        status_counts = Counter(s.get("status", "draft") for s in songs)
        completed = status_counts.get("completed", 0)
        queued = status_counts.get("queued", 0)
        errors = status_counts.get("error", 0)
        dist_count = sum(1 for d in distributions if d.get("status") == "uploaded")

        self.total_songs_card.set_value(str(total))
        self.completed_card.set_value(str(completed))
        self.queued_card.set_value(str(queued))
        self.error_card.set_value(str(errors))
        self.distributed_card.set_value(str(dist_count))

        # Status chart
        status_colors = {
            "draft": "#888888",
            "queued": "#2196F3",
            "processing": "#FF9800",
            "submitted": "#9C27B0",
            "completed": "#4CAF50",
            "error": "#F44336",
            "imported": "#00BCD4",
        }
        status_data = [
            (status, count, status_colors.get(status, "#888888"))
            for status, count in status_counts.most_common()
        ]
        self.status_chart.set_data(status_data)

        # Genre chart (top 10)
        genre_counts = Counter(
            s.get("genre_label") or "Unknown" for s in songs
        )
        genre_colors = ["#E8A838", "#4CAF50", "#2196F3", "#9C27B0", "#FF9800",
                        "#00BCD4", "#F44336", "#8BC34A", "#FF5722", "#607D8B"]
        genre_data = [
            (genre, count, genre_colors[i % len(genre_colors)])
            for i, (genre, count) in enumerate(genre_counts.most_common(10))
        ]
        self.genre_chart.set_data(genre_data)

        # Monthly chart (last 6 months)
        now = datetime.now()
        monthly = defaultdict(int)
        for s in songs:
            created = s.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    key = dt.strftime("%Y-%m")
                    monthly[key] += 1
                except (ValueError, TypeError):
                    pass

        month_data = []
        for i in range(5, -1, -1):
            d = now - timedelta(days=30 * i)
            key = d.strftime("%Y-%m")
            label = d.strftime("%b %Y")
            month_data.append((label, monthly.get(key, 0), Theme.ACCENT))
        self.monthly_chart.set_data(month_data)

"""
Song Factory - Centralized Theme Module

All color constants, status colors, button styles, and the global application
stylesheet live here.  Individual tabs import from this module instead of
defining their own local color constants.
"""


class Theme:
    """Application-wide color and style constants."""

    # --- Core palette ---
    BG = "#2b2b2b"
    PANEL = "#353535"
    TEXT = "#e0e0e0"
    ACCENT = "#E8A838"
    DARK_TEXT = "#1a1a1a"
    DIMMED = "#808080"

    # --- Semantic colors ---
    SUCCESS = "#4CAF50"
    ERROR = "#F44336"
    WARNING = "#FF9800"
    INFO = "#2196F3"

    # --- Structural colors ---
    BORDER = "#555555"
    HOVER = "#454545"
    PRESSED = "#E8A838"
    DISABLED_BG = "#3a3a3a"
    DISABLED_TEXT = "#666666"
    ROW_ALT = "#2f2f2f"
    ROW_BASE = "#353535"
    SELECTION_BG = "#4a4a4a"
    ROW_EVEN = "#2b2b2b"
    ROW_ODD = "#323232"
    STATUSBAR_BG = "#1e1e1e"

    # --- Song status colors ---
    STATUS_COLORS = {
        "draft":      "#888888",
        "queued":     "#2196F3",
        "processing": "#FFC107",
        "submitted":  "#9C27B0",
        "completed":  "#4CAF50",
        "error":      "#F44336",
        "imported":   "#00BCD4",
    }

    # --- Distribution status colors ---
    DIST_STATUS_COLORS = {
        "draft":     "#888888",
        "ready":     "#2196F3",
        "uploading": "#FFC107",
        "submitted": "#9C27B0",
        "live":      "#4CAF50",
        "error":     "#F44336",
    }

    # -----------------------------------------------------------------
    # Reusable style fragments
    # -----------------------------------------------------------------

    @staticmethod
    def accent_button_style() -> str:
        """Gold accent button style (primary actions)."""
        return f"""
            QPushButton {{
                background-color: {Theme.ACCENT};
                color: {Theme.DARK_TEXT};
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #F0B848;
            }}
            QPushButton:pressed {{
                background-color: #D09830;
            }}
            QPushButton:disabled {{
                background-color: {Theme.DISABLED_BG};
                color: {Theme.DISABLED_TEXT};
            }}
        """

    @staticmethod
    def secondary_button_style() -> str:
        """Gray secondary button style."""
        return f"""
            QPushButton {{
                background-color: {Theme.HOVER};
                color: {Theme.TEXT};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Theme.BORDER};
                border-color: {Theme.ACCENT};
            }}
            QPushButton:pressed {{
                background-color: {Theme.ACCENT};
                color: {Theme.DARK_TEXT};
            }}
            QPushButton:disabled {{
                background-color: {Theme.DISABLED_BG};
                color: {Theme.DISABLED_TEXT};
                border-color: #444444;
            }}
        """

    @staticmethod
    def danger_button_style() -> str:
        """Red danger button style (destructive actions)."""
        return f"""
            QPushButton {{
                background-color: {Theme.ERROR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #E53935;
            }}
            QPushButton:pressed {{
                background-color: #C62828;
            }}
        """

    @staticmethod
    def collapsible_toggle_style() -> str:
        """Transparent toggle button with accent text."""
        return f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {Theme.ACCENT};
                font-size: 13px;
                font-weight: bold;
                text-align: left;
                padding: 4px 0;
            }}
            QPushButton:hover {{
                color: #F0B848;
            }}
        """

    @staticmethod
    def panel_style() -> str:
        """Base panel input styling (for inner panels)."""
        return f"""
            QWidget {{
                background-color: {Theme.PANEL};
                color: {Theme.TEXT};
            }}
            QTextEdit, QLineEdit, QComboBox {{
                background-color: {Theme.BG};
                color: {Theme.TEXT};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 4px;
            }}
            QLabel {{
                color: {Theme.TEXT};
            }}
            QCheckBox {{
                color: {Theme.TEXT};
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
        """

    @staticmethod
    def global_stylesheet() -> str:
        """Return the full application stylesheet."""
        return f"""
QMainWindow {{
    background-color: {Theme.BG};
}}
QTabWidget::pane {{
    border: 1px solid {Theme.BORDER};
    background-color: {Theme.BG};
}}
QTabBar::tab {{
    background-color: {Theme.PANEL};
    color: {Theme.TEXT};
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    background-color: {Theme.ACCENT};
    color: {Theme.DARK_TEXT};
    font-weight: bold;
}}
QTabBar::tab:hover:!selected {{
    background-color: {Theme.HOVER};
}}
QWidget {{
    background-color: {Theme.BG};
    color: {Theme.TEXT};
}}
QLabel {{
    color: {Theme.TEXT};
}}
QTextEdit, QLineEdit, QPlainTextEdit {{
    background-color: {Theme.PANEL};
    color: {Theme.TEXT};
    border: 1px solid {Theme.BORDER};
    border-radius: 4px;
    padding: 4px;
    selection-background-color: {Theme.ACCENT};
    selection-color: {Theme.DARK_TEXT};
}}
QTextEdit:focus, QLineEdit:focus {{
    border: 1px solid {Theme.ACCENT};
}}
QPushButton {{
    background-color: {Theme.HOVER};
    color: {Theme.TEXT};
    border: 1px solid {Theme.BORDER};
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {Theme.BORDER};
    border-color: {Theme.ACCENT};
}}
QPushButton:pressed {{
    background-color: {Theme.ACCENT};
    color: {Theme.DARK_TEXT};
}}
QPushButton:disabled {{
    background-color: {Theme.DISABLED_BG};
    color: {Theme.DISABLED_TEXT};
    border-color: #444444;
}}
QComboBox {{
    background-color: {Theme.PANEL};
    color: {Theme.TEXT};
    border: 1px solid {Theme.BORDER};
    border-radius: 4px;
    padding: 6px 10px;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {Theme.PANEL};
    color: {Theme.TEXT};
    selection-background-color: {Theme.ACCENT};
    selection-color: {Theme.DARK_TEXT};
    border: 1px solid {Theme.BORDER};
}}
QTableWidget {{
    background-color: {Theme.PANEL};
    color: {Theme.TEXT};
    gridline-color: {Theme.HOVER};
    border: 1px solid {Theme.BORDER};
    selection-background-color: {Theme.ACCENT};
    selection-color: {Theme.DARK_TEXT};
    alternate-background-color: {Theme.DISABLED_BG};
}}
QTableWidget::item {{
    padding: 4px;
}}
QHeaderView::section {{
    background-color: #404040;
    color: {Theme.TEXT};
    padding: 6px;
    border: 1px solid {Theme.BORDER};
    font-weight: bold;
}}
QListWidget {{
    background-color: {Theme.PANEL};
    color: {Theme.TEXT};
    border: 1px solid {Theme.BORDER};
    border-radius: 4px;
}}
QListWidget::item {{
    padding: 6px;
}}
QListWidget::item:selected {{
    background-color: {Theme.ACCENT};
    color: {Theme.DARK_TEXT};
}}
QListWidget::item:hover:!selected {{
    background-color: {Theme.HOVER};
}}
QCheckBox {{
    color: {Theme.TEXT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {Theme.BORDER};
    border-radius: 3px;
    background-color: {Theme.PANEL};
}}
QCheckBox::indicator:checked {{
    background-color: {Theme.ACCENT};
    border-color: {Theme.ACCENT};
}}
QSpinBox {{
    background-color: {Theme.PANEL};
    color: {Theme.TEXT};
    border: 1px solid {Theme.BORDER};
    border-radius: 4px;
    padding: 4px;
}}
QGroupBox {{
    color: {Theme.ACCENT};
    border: 1px solid {Theme.BORDER};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}
QSplitter::handle {{
    background-color: {Theme.HOVER};
    width: 3px;
    height: 3px;
}}
QScrollBar:vertical {{
    background-color: {Theme.BG};
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {Theme.BORDER};
    border-radius: 6px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {Theme.ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background-color: {Theme.BG};
    height: 12px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background-color: {Theme.BORDER};
    border-radius: 6px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {Theme.ACCENT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QStatusBar {{
    background-color: {Theme.STATUSBAR_BG};
    color: {Theme.DIMMED};
    border-top: 1px solid {Theme.HOVER};
    font-size: 12px;
}}
QMessageBox {{
    background-color: {Theme.BG};
}}
QMessageBox QLabel {{
    color: {Theme.TEXT};
}}
"""

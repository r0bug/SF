#!/usr/bin/env python3
"""Song Factory — Yakima Finds: AI-powered song creation pipeline."""

import sys
import os

# Add the songfactory directory to the path (skip when frozen via PyInstaller)
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logging_config import setup_logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QIcon
from theme import Theme
from app import MainWindow
from platform_utils import get_resource_dir


def main():
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("Song Factory")
    app.setOrganizationName("Yakima Finds")
    app.setStyleSheet(Theme.global_stylesheet())

    # Set application icon
    icon_path = os.path.join(get_resource_dir(), "icon.svg")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

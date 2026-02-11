#!/usr/bin/env python3
"""Song Factory — Yakima Finds: AI-powered song creation pipeline."""

import sys
import os

# Add the songfactory directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logging_config import setup_logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from theme import Theme
from app import MainWindow


def main():
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("Song Factory")
    app.setOrganizationName("Yakima Finds")
    app.setStyleSheet(Theme.global_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Song Factory — Yakima Finds: AI-powered song creation pipeline."""

import sys
import os

# Add the songfactory directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from app import MainWindow, DARK_STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Song Factory")
    app.setOrganizationName("Yakima Finds")
    app.setStyleSheet(DARK_STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

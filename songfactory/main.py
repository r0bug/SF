#!/usr/bin/env python3
"""Song Factory — Yakima Finds: AI-powered song creation pipeline."""

import sys
import os

# Add the songfactory directory to the path (skip when frozen via PyInstaller)
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import faulthandler
import logging

from logging_config import setup_logging, LOG_DIR
from PyQt6.QtCore import QtMsgType, qInstallMessageHandler
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QIcon
from theme import Theme
from app import MainWindow
from platform_utils import get_resource_dir


_crash_log = None


def _install_crash_handlers():
    """Make hard crashes leave a trace in ~/.songfactory/logs/.

    - faulthandler: Python stacks of all threads on SIGSEGV/SIGABRT
    - Qt message handler: Qt warnings/fatals (e.g. "QThread: Destroyed
      while thread is still running") go to the app log
    - excepthook: uncaught exceptions in slots/threads are logged before
      PyQt aborts
    """
    global _crash_log
    log = logging.getLogger("songfactory.crash")

    _crash_log = open(os.path.join(LOG_DIR, "crash.log"), "a", encoding="utf-8")
    faulthandler.enable(file=_crash_log, all_threads=True)

    def qt_handler(msg_type, context, message):
        if msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            log.critical("Qt: %s", message)
        elif msg_type == QtMsgType.QtWarningMsg:
            log.warning("Qt: %s", message)
        else:
            log.debug("Qt: %s", message)
    qInstallMessageHandler(qt_handler)

    prev_hook = sys.excepthook

    def excepthook(exc_type, exc, tb):
        log.critical("Uncaught exception", exc_info=(exc_type, exc, tb))
        prev_hook(exc_type, exc, tb)
    sys.excepthook = excepthook


def main():
    setup_logging()
    _install_crash_handlers()

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

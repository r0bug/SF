"""
Song Factory - Base Tab Class

Provides ``BaseTab(QWidget)`` with a standard lifecycle contract for all
Song Factory tabs: UI construction, signal wiring, data refresh, and
worker cleanup.

Subclasses must implement ``_init_ui()``; other hooks are optional.
"""

from PyQt6.QtWidgets import QWidget, QMessageBox
from PyQt6.QtCore import QThread

from database import Database


class BaseTab(QWidget):
    """Base class for all Song Factory tabs.

    Lifecycle:
        ``__init__``  → ``_init_ui()`` → ``_connect_signals()`` → ``refresh()``

    Subclasses override the hook methods.  The base class manages worker
    registration and cleanup.
    """

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._workers: list[QThread] = []
        self._init_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Lifecycle hooks (override in subclasses)
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        """Build the UI.  Called once during ``__init__``."""
        raise NotImplementedError

    def _connect_signals(self) -> None:
        """Connect signals to slots.  Called once after ``_init_ui``."""
        pass

    def refresh(self) -> None:
        """Reload data from the database.

        Called by ``app.py`` on tab activation and after relevant edits.
        The default implementation does nothing.
        """
        pass

    def cleanup(self) -> None:
        """Stop running workers and release resources.

        Called by ``MainWindow.closeEvent()``.  Subclasses that hold
        additional resources should call ``super().cleanup()`` first.
        """
        for w in self._workers:
            if w.isRunning():
                if hasattr(w, "request_stop"):
                    w.request_stop()
                elif hasattr(w, "stop"):
                    w.stop()
                else:
                    w.requestInterruption()
                w.wait(3000)

    # ------------------------------------------------------------------
    # Shared utilities
    # ------------------------------------------------------------------

    def register_worker(self, worker: QThread) -> None:
        """Track a worker thread for cleanup on close."""
        self._workers.append(worker)

    def show_error(self, title: str, message: str) -> None:
        """Display an error message box."""
        QMessageBox.critical(self, title, message)

    def show_warning(self, title: str, message: str) -> None:
        """Display a warning message box."""
        QMessageBox.warning(self, title, message)

    def show_info(self, title: str, message: str) -> None:
        """Display an informational message box."""
        QMessageBox.information(self, title, message)

    def confirm(self, title: str, message: str) -> bool:
        """Show a Yes/No confirmation dialog.  Returns True if Yes."""
        result = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

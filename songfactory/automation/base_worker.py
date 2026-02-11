"""Base worker class for Song Factory background threads."""

import logging
from PyQt6.QtCore import QThread, pyqtSignal
from database import Database

logger = logging.getLogger("songfactory.automation")


class BaseWorker(QThread):
    """Base class for all background worker threads.

    Provides shared infrastructure: stop flag, thread-local DB connection,
    progress/error signals, and structured run lifecycle.

    Subclasses override ``_execute()`` with their main logic.
    """
    progress_update = pyqtSignal(str)
    error_occurred = pyqtSignal(str, str)  # (context, error_message)

    def __init__(self, db_path: str, config: dict = None, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._config = config or {}
        self._stop_flag = False
        self._db = None  # Created in run() for thread safety

    def request_stop(self):
        """Request graceful stop. Check with _should_stop()."""
        self._stop_flag = True

    # Keep backward compat alias
    def stop(self):
        """Alias for request_stop()."""
        self.request_stop()

    def _should_stop(self) -> bool:
        """Return True if stop has been requested."""
        return self._stop_flag

    def _open_db(self) -> Database:
        """Create a thread-local DB connection."""
        self._db = Database(db_path=self._db_path)
        return self._db

    def _close_db(self):
        """Close the thread-local DB connection."""
        if self._db:
            self._db.close()
            self._db = None

    def _emit_progress(self, message: str):
        """Emit a progress update signal."""
        self.progress_update.emit(message)
        logger.info(message)

    def run(self):
        """Main thread entry point. Opens DB, calls _execute(), cleans up."""
        try:
            self._open_db()
            self._execute()
        except Exception as e:
            logger.error("Worker %s failed: %s", self.__class__.__name__, e)
            self.error_occurred.emit("", str(e))
        finally:
            self._close_db()

    def _execute(self):
        """Override in subclasses. Called inside run() with DB available as self._db."""
        raise NotImplementedError

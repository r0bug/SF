"""
Song Factory - Data Event Bus

Application-wide signal bus for cross-tab data change notifications.
Emitting a signal from one tab causes subscribed tabs to refresh.

Usage::

    from event_bus import event_bus
    event_bus.songs_changed.emit()          # after saving a song
    event_bus.songs_changed.connect(self.load_songs)  # in another tab
"""

from PyQt6.QtCore import QObject, pyqtSignal


class DataEventBus(QObject):
    """Singleton event bus for data change notifications."""

    songs_changed = pyqtSignal()
    lore_changed = pyqtSignal()
    genres_changed = pyqtSignal()
    config_changed = pyqtSignal(str)        # config key that changed
    distributions_changed = pyqtSignal()
    cd_projects_changed = pyqtSignal()
    personal_data_changed = pyqtSignal()
    tags_changed = pyqtSignal()


# Module-level singleton
event_bus = DataEventBus()

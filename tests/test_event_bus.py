"""Tests for the data event bus."""


def test_event_bus_is_singleton():
    from event_bus import event_bus, DataEventBus
    assert isinstance(event_bus, DataEventBus)


def test_songs_changed_signal(qt_app):
    from event_bus import event_bus
    received = []
    event_bus.songs_changed.connect(lambda: received.append(True))
    event_bus.songs_changed.emit()
    assert len(received) == 1


def test_config_changed_signal(qt_app):
    from event_bus import event_bus
    received = []
    event_bus.config_changed.connect(lambda key: received.append(key))
    event_bus.config_changed.emit("api_key")
    assert received == ["api_key"]

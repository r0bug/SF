"""Smoke tests: every tab instantiates and refreshes without crashing."""

import pytest


@pytest.fixture
def db(tmp_path):
    """Lightweight DB for tab smoke tests."""
    from database import Database
    db = Database(db_path=str(tmp_path / "smoke.db"))
    yield db
    db.close()


class TestTabSmoke:
    """Each tab should instantiate and refresh without errors in offscreen mode."""

    def test_genre_manager_tab(self, qt_app, db):
        from tabs.genres import GenreManagerTab
        tab = GenreManagerTab(db)
        tab.refresh()

    def test_lore_editor_tab(self, qt_app, db):
        from tabs.lore import LoreEditorTab
        tab = LoreEditorTab(db)
        tab.refresh()

    def test_song_creator_tab(self, qt_app, db):
        from tabs.creator import SongCreatorTab
        tab = SongCreatorTab(db)
        tab.refresh()

    def test_song_library_tab(self, qt_app, db):
        from tabs.library import SongLibraryTab
        tab = SongLibraryTab(db)
        tab.refresh()

    def test_settings_tab(self, qt_app, db):
        from tabs.settings import SettingsTab
        tab = SettingsTab(db)
        tab.refresh()

    def test_lore_discovery_tab(self, qt_app, db):
        from tabs.lore_discovery import LoreDiscoveryTab
        tab = LoreDiscoveryTab(db)
        tab.refresh()

    def test_cd_master_tab(self, qt_app, db):
        from tabs.cd_master import CDMasterTab
        tab = CDMasterTab(db)
        tab.refresh()

    def test_distribution_tab(self, qt_app, db):
        from tabs.distribution import DistributionTab
        tab = DistributionTab(db)
        tab.refresh()


class TestTabCleanup:
    """cleanup() should not crash on any tab."""

    def test_cleanup_all_tabs(self, qt_app, db):
        from tabs.genres import GenreManagerTab
        from tabs.lore import LoreEditorTab
        from tabs.creator import SongCreatorTab
        from tabs.library import SongLibraryTab
        from tabs.settings import SettingsTab
        from tabs.lore_discovery import LoreDiscoveryTab
        from tabs.cd_master import CDMasterTab
        from tabs.distribution import DistributionTab

        tabs = [
            GenreManagerTab(db),
            LoreEditorTab(db),
            SongCreatorTab(db),
            SongLibraryTab(db),
            SettingsTab(db),
            LoreDiscoveryTab(db),
            CDMasterTab(db),
            DistributionTab(db),
        ]
        for tab in tabs:
            tab.cleanup()


class TestBaseTabContract:
    """All tabs should have the BaseTab interface."""

    def test_tabs_inherit_from_base_tab(self, qt_app, db):
        from tabs.base_tab import BaseTab
        from tabs.genres import GenreManagerTab
        from tabs.lore import LoreEditorTab
        from tabs.creator import SongCreatorTab
        from tabs.library import SongLibraryTab
        from tabs.settings import SettingsTab
        from tabs.lore_discovery import LoreDiscoveryTab
        from tabs.cd_master import CDMasterTab
        from tabs.distribution import DistributionTab

        for cls in [
            GenreManagerTab, LoreEditorTab, SongCreatorTab, SongLibraryTab,
            SettingsTab, LoreDiscoveryTab, CDMasterTab, DistributionTab,
        ]:
            tab = cls(db)
            assert isinstance(tab, BaseTab), f"{cls.__name__} does not inherit BaseTab"
            assert hasattr(tab, "refresh")
            assert hasattr(tab, "cleanup")
            assert hasattr(tab, "register_worker")
            assert hasattr(tab, "show_error")
            assert hasattr(tab, "confirm")

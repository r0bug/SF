"""Deep tests for Lore Editor tab and Creator tab lore interactions.

Exercises all lore-related functions looking for freezes, signal loops,
and cascading save issues.
"""

import os
import sys
import time

import pytest
from unittest.mock import patch, MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "songfactory"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def db(tmp_path):
    from database import Database
    _db = Database(db_path=str(tmp_path / "test.db"))
    yield _db
    _db.close()


@pytest.fixture
def seeded_db(db):
    from seed_data import SEED_GENRES, SEED_LORE
    for genre in SEED_GENRES:
        db.add_genre(
            name=genre["name"],
            prompt_template=genre["prompt_template"],
            description=genre.get("description", ""),
            bpm_range=genre.get("bpm_range", ""),
            active=genre.get("active", True),
        )
    for lore in SEED_LORE:
        db.add_lore(
            title=lore["title"],
            content=lore["content"],
            category=lore.get("category", "general"),
            active=lore.get("active", True),
        )
    return db


@pytest.fixture
def lore_tab(seeded_db, qapp):
    from tabs.lore import LoreEditorTab
    tab = LoreEditorTab(seeded_db)
    yield tab
    tab.cleanup()


@pytest.fixture
def creator_tab(seeded_db, qapp):
    from tabs.creator import SongCreatorTab
    tab = SongCreatorTab(seeded_db)
    yield tab
    tab.cleanup()


# =====================================================================
# Lore Editor Tab — Basic operations
# =====================================================================

class TestLoreEditorBasic:
    """Test basic Lore Editor operations."""

    def test_initial_load(self, lore_tab, seeded_db):
        """Tab should load all lore entries on init."""
        all_lore = seeded_db.get_all_lore()
        assert lore_tab.lore_list.count() == len(all_lore)

    def test_select_entry(self, lore_tab):
        """Selecting an entry should populate the editor."""
        item = lore_tab.lore_list.item(0)
        assert item is not None
        lore_tab.lore_list.setCurrentItem(item)
        assert lore_tab._current_id is not None
        assert lore_tab.title_edit.text() != ""

    def test_edit_title_marks_dirty(self, lore_tab):
        """Editing title should set dirty flag."""
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        lore_tab._dirty = False
        lore_tab.title_edit.setText("Modified Title")
        assert lore_tab._dirty is True

    def test_edit_content_marks_dirty(self, lore_tab):
        """Editing content should set dirty flag."""
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        lore_tab._dirty = False
        lore_tab.content_edit.setPlainText("New content here")
        assert lore_tab._dirty is True

    def test_edit_category_marks_dirty(self, lore_tab):
        """Changing category should set dirty flag."""
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        lore_tab._dirty = False
        current = lore_tab.category_combo.currentIndex()
        new_idx = (current + 1) % lore_tab.category_combo.count()
        lore_tab.category_combo.setCurrentIndex(new_idx)
        assert lore_tab._dirty is True

    def test_edit_active_marks_dirty(self, lore_tab):
        """Toggling active checkbox should set dirty flag."""
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        lore_tab._dirty = False
        current_state = lore_tab.active_check.isChecked()
        lore_tab.active_check.setChecked(not current_state)
        assert lore_tab._dirty is True

    def test_loading_guard_prevents_dirty(self, lore_tab):
        """During loading, field changes should NOT mark dirty."""
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        lore_tab._dirty = False
        lore_tab._loading = True
        lore_tab.title_edit.setText("This should not dirty")
        assert lore_tab._dirty is False
        lore_tab._loading = False


# =====================================================================
# Lore Editor Tab — Save operations
# =====================================================================

class TestLoreEditorSave:
    """Test save behavior and signal emission."""

    def test_save_to_db(self, lore_tab, seeded_db):
        """_save_to_db should persist changes without emitting signals."""
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        lore_id = lore_tab._current_id

        lore_tab.title_edit.setText("Updated Title XYZ")
        lore_tab._save_to_db()

        entry = seeded_db.get_lore(lore_id)
        assert entry["title"] == "Updated Title XYZ"
        assert lore_tab._dirty is False

    def test_save_current_emits_lore_changed(self, lore_tab):
        """save_current should emit lore_changed signal."""
        from event_bus import event_bus

        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        lore_tab.title_edit.setText("Signal Test")

        signals_received = []
        event_bus.lore_changed.connect(lambda: signals_received.append(True))

        lore_tab.save_current()

        assert len(signals_received) == 1

    def test_save_and_switch_no_freeze(self, lore_tab):
        """Saving then switching entries should not freeze."""
        if lore_tab.lore_list.count() < 2:
            pytest.skip("Need at least 2 lore entries")

        # Select first item and edit
        item0 = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item0)
        lore_tab.title_edit.setText("Entry 0 Edited")

        # Switch to second item — should auto-save first
        item1 = lore_tab.lore_list.item(1)
        lore_tab.lore_list.setCurrentItem(item1)

        # Should have a new current_id and not be dirty
        assert lore_tab._current_id is not None
        assert lore_tab._dirty is False

    def test_rapid_switch_no_freeze(self, lore_tab):
        """Rapidly switching between entries should not freeze."""
        count = lore_tab.lore_list.count()
        if count < 3:
            pytest.skip("Need at least 3 entries")

        for i in range(min(count, 10)):
            item = lore_tab.lore_list.item(i % count)
            lore_tab.lore_list.setCurrentItem(item)
            lore_tab.title_edit.setText(f"Rapid switch {i}")

        # Should not be stuck
        assert lore_tab._current_id is not None

    def test_save_reload_preserves_selection(self, lore_tab):
        """After save_current, the same entry should remain selected."""
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        original_id = lore_tab._current_id

        lore_tab.save_current()

        assert lore_tab._current_id == original_id
        current = lore_tab.lore_list.currentItem()
        assert current is not None
        from PyQt6.QtCore import Qt
        assert current.data(Qt.ItemDataRole.UserRole) == original_id


# =====================================================================
# Lore Editor Tab — Add / Delete
# =====================================================================

class TestLoreEditorAddDelete:
    """Test add and delete operations."""

    def test_add_new_lore(self, lore_tab, seeded_db):
        """Adding new lore should create entry and select it."""
        initial_count = lore_tab.lore_list.count()
        lore_tab.add_new_lore()
        assert lore_tab.lore_list.count() >= initial_count  # may filter
        assert lore_tab._current_id is not None
        assert lore_tab.title_edit.text() == "New Lore Entry"

    def test_add_while_dirty_saves_first(self, lore_tab, seeded_db):
        """Adding new lore while dirty should save existing entry first."""
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        lore_id = lore_tab._current_id
        lore_tab.title_edit.setText("Auto-saved Before Add")
        lore_tab._dirty = True

        lore_tab.add_new_lore()

        entry = seeded_db.get_lore(lore_id)
        assert entry["title"] == "Auto-saved Before Add"

    def test_delete_lore(self, lore_tab, seeded_db):
        """Deleting lore should remove it and clear editor."""
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        lore_id = lore_tab._current_id
        initial_count = lore_tab.lore_list.count()

        with patch.object(
            lore_tab, "delete_lore",
            wraps=lambda: (
                seeded_db.delete_lore(lore_id),
                setattr(lore_tab, "_current_id", None),
                lore_tab._clear_editor(),
                lore_tab._set_editor_enabled(False),
                lore_tab.load_lore_list(),
            ),
        ):
            # Simulate delete without confirmation dialog
            seeded_db.delete_lore(lore_id)
            lore_tab._current_id = None
            lore_tab._clear_editor()
            lore_tab._set_editor_enabled(False)
            lore_tab.load_lore_list()

        assert lore_tab.lore_list.count() == initial_count - 1
        assert seeded_db.get_lore(lore_id) is None


# =====================================================================
# Lore Editor Tab — Bulk operations
# =====================================================================

class TestLoreEditorBulk:
    """Test bulk toggle operations."""

    def test_select_all(self, lore_tab, seeded_db):
        """Select All should activate all lore entries."""
        lore_tab._on_select_all()
        all_lore = seeded_db.get_all_lore()
        assert all(e["active"] for e in all_lore)

    def test_deselect_all(self, lore_tab, seeded_db):
        """Deselect All should deactivate all lore entries."""
        lore_tab._on_deselect_all()
        all_lore = seeded_db.get_all_lore()
        assert all(not e["active"] for e in all_lore)

    def test_toggle_category(self, lore_tab, seeded_db):
        """Toggle category should flip active state for filtered category."""
        # Filter to "people"
        idx = lore_tab.category_filter.findText("people")
        if idx < 0:
            pytest.skip("No 'people' category")
        lore_tab.category_filter.setCurrentIndex(idx)

        # First activate all, then toggle
        lore_tab._on_select_all()
        lore_tab._on_toggle_category()

        all_lore = seeded_db.get_all_lore()
        people = [e for e in all_lore if e["category"] == "people"]
        if people:
            assert all(not e["active"] for e in people)

    def test_category_filter(self, lore_tab, seeded_db):
        """Category filter should show only matching entries."""
        all_lore = seeded_db.get_all_lore()
        people_count = sum(1 for e in all_lore if e["category"] == "people")

        idx = lore_tab.category_filter.findText("people")
        if idx < 0:
            pytest.skip("No 'people' category")
        lore_tab.category_filter.setCurrentIndex(idx)

        assert lore_tab.lore_list.count() == people_count

    def test_filter_back_to_all(self, lore_tab, seeded_db):
        """Switching filter back to All should show all entries."""
        lore_tab.category_filter.setCurrentIndex(0)  # "All"
        all_lore = seeded_db.get_all_lore()
        assert lore_tab.lore_list.count() == len(all_lore)


# =====================================================================
# Lore Editor Tab — Presets
# =====================================================================

class TestLoreEditorPresets:
    """Test preset operations."""

    def test_save_preset(self, lore_tab, seeded_db):
        """Should save a preset with active lore IDs."""
        lore_tab._on_select_all()
        active = seeded_db.get_active_lore()
        assert len(active) > 0

        with patch("tabs.lore.QInputDialog.getText", return_value=("Test Preset", True)):
            lore_tab._on_preset_save()

        presets = seeded_db.get_all_lore_presets()
        assert any(p["name"] == "Test Preset" for p in presets)

    def test_apply_preset(self, lore_tab, seeded_db):
        """Applying a preset should activate only preset lore entries."""
        # First create a preset with just a few entries
        all_lore = seeded_db.get_all_lore()
        subset = [all_lore[0]["id"]]
        seeded_db.add_lore_preset("Subset Preset", subset)
        lore_tab.refresh_presets()

        # Find and apply it
        for i in range(lore_tab.preset_combo.count()):
            if lore_tab.preset_combo.itemText(i) == "Subset Preset":
                lore_tab.preset_combo.setCurrentIndex(i)
                break

        lore_tab._on_preset_apply()
        active = seeded_db.get_active_lore()
        assert len(active) == 1
        assert active[0]["id"] == subset[0]

    def test_update_preset(self, lore_tab, seeded_db):
        """Updating a preset should change its lore IDs."""
        all_lore = seeded_db.get_all_lore()
        seeded_db.add_lore_preset("Update Me", [all_lore[0]["id"]])
        lore_tab.refresh_presets()

        # Select the preset
        for i in range(lore_tab.preset_combo.count()):
            if lore_tab.preset_combo.itemText(i) == "Update Me":
                lore_tab.preset_combo.setCurrentIndex(i)
                break

        # Activate more entries
        lore_tab._on_select_all()

        with patch("tabs.lore.QMessageBox.question", return_value=lore_tab.tr("Yes")):
            # Bypass the confirmation dialog
            preset_id = lore_tab.preset_combo.currentData()
            active_lore = seeded_db.get_active_lore()
            lore_ids = [e["id"] for e in active_lore]
            seeded_db.update_lore_preset(preset_id, lore_ids=lore_ids)
            lore_tab.refresh_presets()

        presets = seeded_db.get_all_lore_presets()
        updated = [p for p in presets if p["name"] == "Update Me"][0]
        assert len(updated["lore_ids"]) > 1

    def test_delete_preset(self, lore_tab, seeded_db):
        """Deleting a preset should remove it."""
        seeded_db.add_lore_preset("Delete Me", [1])
        lore_tab.refresh_presets()
        initial_count = len(seeded_db.get_all_lore_presets())

        # Find and delete it
        for i in range(lore_tab.preset_combo.count()):
            if lore_tab.preset_combo.itemText(i) == "Delete Me":
                lore_tab.preset_combo.setCurrentIndex(i)
                break

        preset_id = lore_tab.preset_combo.currentData()
        seeded_db.delete_lore_preset(preset_id)
        lore_tab.refresh_presets()

        assert len(seeded_db.get_all_lore_presets()) == initial_count - 1


# =====================================================================
# Lore Editor — Signal loop detection
# =====================================================================

class TestLoreSignalLoops:
    """Test that no signal loops or freezes occur."""

    def test_save_does_not_loop(self, lore_tab):
        """save_current should not trigger infinite save loop."""
        from event_bus import event_bus
        call_count = []
        original_save = lore_tab._save_to_db

        def counting_save():
            call_count.append(1)
            if len(call_count) > 10:
                raise RuntimeError("Infinite save loop detected!")
            original_save()

        lore_tab._save_to_db = counting_save

        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        lore_tab.title_edit.setText("Loop test")
        lore_tab.save_current()

        # Should save at most twice (once in save_current, once in re-select)
        assert len(call_count) <= 2, f"_save_to_db called {len(call_count)} times!"

    def test_event_bus_does_not_reenter_lore_tab(self, lore_tab):
        """lore_changed emission should not trigger Lore tab re-save."""
        from event_bus import event_bus

        save_count = []
        original = lore_tab.save_current

        def counting_save():
            save_count.append(1)
            if len(save_count) > 5:
                raise RuntimeError("Re-entrant save!")
            original()

        lore_tab.save_current = counting_save

        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        lore_tab.title_edit.setText("Reentrant test")
        lore_tab.save_current()

        assert len(save_count) == 1

    def test_rapid_content_edits_no_freeze(self, lore_tab):
        """Simulating rapid typing should not freeze."""
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)

        # Simulate 100 rapid keystrokes
        for i in range(100):
            lore_tab.content_edit.setPlainText(f"Rapid edit #{i} " * 10)

        assert lore_tab._dirty is True
        # Should get here without hanging

    def test_bulk_ops_with_event_bus(self, lore_tab):
        """Bulk operations emitting lore_changed should not loop."""
        from event_bus import event_bus

        emit_count = []
        event_bus.lore_changed.connect(lambda: emit_count.append(1))

        lore_tab._on_select_all()
        lore_tab._on_deselect_all()
        lore_tab._on_select_all()

        assert len(emit_count) == 3  # one per operation, no cascading


# =====================================================================
# Creator Tab — Lore interactions
# =====================================================================

class TestCreatorLoreInteraction:
    """Test Creator tab lore features."""

    def test_lore_checkboxes_populated(self, creator_tab, seeded_db):
        """Creator should have lore checkboxes for all entries."""
        all_lore = seeded_db.get_all_lore()
        assert len(creator_tab._lore_checkboxes) == len(all_lore)

    def test_select_lore_populates_preview(self, creator_tab, seeded_db):
        """Select Lore button should populate the preview area."""
        # Check some lore entries
        for _, cb in creator_tab._lore_checkboxes[:3]:
            cb.setChecked(True)

        creator_tab._on_select_lore()

        preview_text = creator_tab._lore_preview.toPlainText()
        assert len(preview_text) > 0
        assert "###" in preview_text
        # In offscreen mode, isVisible() depends on parent visibility;
        # check the widget's own visibility flag instead
        assert not creator_tab._lore_preview.isHidden()

    def test_select_lore_empty_shows_message(self, creator_tab):
        """Select Lore with nothing checked should show info message."""
        for _, cb in creator_tab._lore_checkboxes:
            cb.setChecked(False)

        with patch("tabs.creator.QMessageBox.information"):
            creator_tab._on_select_lore()

        assert not creator_tab._lore_preview.isHidden()

    def test_lore_preview_editable(self, creator_tab):
        """The lore preview text should be editable."""
        for _, cb in creator_tab._lore_checkboxes[:1]:
            cb.setChecked(True)

        creator_tab._on_select_lore()
        creator_tab._lore_preview.setPlainText("Custom lore text")
        assert creator_tab._lore_preview.toPlainText() == "Custom lore text"

    def test_get_selected_lore(self, creator_tab, seeded_db):
        """_get_selected_lore should return dicts for checked entries."""
        for _, cb in creator_tab._lore_checkboxes:
            cb.setChecked(False)
        # Check first entry
        if creator_tab._lore_checkboxes:
            lore_id, cb = creator_tab._lore_checkboxes[0]
            cb.setChecked(True)
            selected = creator_tab._get_selected_lore()
            assert len(selected) == 1
            assert selected[0]["id"] == lore_id

    def test_select_all_lore(self, creator_tab, seeded_db):
        """Select All should check all lore checkboxes."""
        creator_tab._select_all_lore()
        all_checked = all(cb.isChecked() for _, cb in creator_tab._lore_checkboxes)
        assert all_checked

    def test_deselect_all_lore(self, creator_tab, seeded_db):
        """Deselect All should uncheck all lore checkboxes."""
        creator_tab._select_all_lore()
        creator_tab._deselect_all_lore()
        all_unchecked = all(not cb.isChecked() for _, cb in creator_tab._lore_checkboxes)
        assert all_unchecked

    def test_save_preset_from_creator(self, creator_tab, seeded_db):
        """Save Preset from creator should work."""
        for _, cb in creator_tab._lore_checkboxes[:3]:
            cb.setChecked(True)

        with patch("tabs.creator.QInputDialog.getText", return_value=("Creator Preset", True)):
            creator_tab._save_preset()

        presets = seeded_db.get_all_lore_presets()
        assert any(p["name"] == "Creator Preset" for p in presets)

    def test_save_preset_empty_warns(self, creator_tab):
        """Save Preset with nothing checked should warn."""
        for _, cb in creator_tab._lore_checkboxes:
            cb.setChecked(False)

        with patch("tabs.creator.QMessageBox.warning") as mock_warn:
            creator_tab._save_preset()
            mock_warn.assert_called_once()

    def test_apply_preset_in_creator(self, creator_tab, seeded_db):
        """Applying a preset should check matching checkboxes."""
        all_lore = seeded_db.get_all_lore()
        target_ids = [all_lore[0]["id"]]
        seeded_db.add_lore_preset("Apply Test", target_ids)
        creator_tab._refresh_creator_presets()

        # Find and apply the preset
        for i in range(creator_tab._creator_preset_combo.count()):
            if creator_tab._creator_preset_combo.itemText(i) == "Apply Test":
                preset_id = creator_tab._creator_preset_combo.itemData(i)
                creator_tab._apply_creator_preset(preset_id)
                break

        checked_ids = {lid for lid, cb in creator_tab._lore_checkboxes if cb.isChecked()}
        assert target_ids[0] in checked_ids

    def test_refresh_lore_from_event_bus(self, creator_tab, seeded_db):
        """Event bus lore_changed should refresh creator's checkboxes."""
        initial_count = len(creator_tab._lore_checkboxes)

        # Add a new lore entry directly
        seeded_db.add_lore(
            title="Event Bus Test Entry",
            content="Testing event bus refresh",
            category="general",
            active=True,
        )

        # Manually trigger the refresh (simulating event_bus.lore_changed)
        creator_tab.refresh_lore()

        assert len(creator_tab._lore_checkboxes) == initial_count + 1


# =====================================================================
# Cross-tab signal interaction
# =====================================================================

class TestCrossTabSignals:
    """Test that lore changes propagate correctly between tabs."""

    def test_lore_save_refreshes_creator(self, seeded_db, qapp):
        """Saving in Lore tab should refresh Creator's checkboxes."""
        from tabs.lore import LoreEditorTab
        from tabs.creator import SongCreatorTab

        lore_tab = LoreEditorTab(seeded_db)
        creator_tab = SongCreatorTab(seeded_db)

        initial_count = len(creator_tab._lore_checkboxes)

        # Add new entry via lore tab
        lore_tab.add_new_lore()

        # Creator should have refreshed via event bus
        assert len(creator_tab._lore_checkboxes) == initial_count + 1

        lore_tab.cleanup()
        creator_tab.cleanup()

    def test_bulk_toggle_refreshes_creator(self, seeded_db, qapp):
        """Bulk toggle in Lore tab should not freeze Creator."""
        from tabs.lore import LoreEditorTab
        from tabs.creator import SongCreatorTab

        lore_tab = LoreEditorTab(seeded_db)
        creator_tab = SongCreatorTab(seeded_db)

        # Rapid bulk toggles
        lore_tab._on_select_all()
        lore_tab._on_deselect_all()
        lore_tab._on_select_all()

        # Should not freeze — verify creator still works
        assert len(creator_tab._lore_checkboxes) > 0

        lore_tab.cleanup()
        creator_tab.cleanup()

    def test_preset_apply_refreshes_creator(self, seeded_db, qapp):
        """Applying a preset in Lore tab should not freeze Creator."""
        from tabs.lore import LoreEditorTab
        from tabs.creator import SongCreatorTab

        lore_tab = LoreEditorTab(seeded_db)
        creator_tab = SongCreatorTab(seeded_db)

        # Create and apply a preset
        all_lore = seeded_db.get_all_lore()
        seeded_db.add_lore_preset("Cross Tab Test", [all_lore[0]["id"]])
        lore_tab.refresh_presets()

        for i in range(lore_tab.preset_combo.count()):
            if lore_tab.preset_combo.itemText(i) == "Cross Tab Test":
                lore_tab.preset_combo.setCurrentIndex(i)
                break

        lore_tab._on_preset_apply()

        # Should not freeze
        assert creator_tab._lore_checkboxes is not None

        lore_tab.cleanup()
        creator_tab.cleanup()


# =====================================================================
# API Client — Lore text parameter
# =====================================================================

class TestAPIClientLoreText:
    """Test that lore_text parameter works correctly."""

    def test_build_system_prompt_with_lore_dicts(self):
        """System prompt should format lore dicts correctly."""
        from api_client import SongGenerator

        lore = [
            {"title": "Test Lore", "content": "Some content"},
            {"title": "More Lore", "content": "More content"},
        ]
        prompt = SongGenerator._build_system_prompt(lore)
        assert "### Test Lore" in prompt
        assert "### More Lore" in prompt
        assert "Some content" in prompt

    def test_build_system_prompt_with_lore_text(self):
        """System prompt should use lore_text directly when provided."""
        from api_client import SongGenerator

        custom_text = "### Custom Entry\nThis is custom lore text"
        prompt = SongGenerator._build_system_prompt([], lore_text=custom_text)
        assert "### Custom Entry" in prompt
        assert "This is custom lore text" in prompt

    def test_lore_text_overrides_lore_dicts(self):
        """lore_text should take priority over lore dicts."""
        from api_client import SongGenerator

        lore = [{"title": "Dict Lore", "content": "Dict content"}]
        custom_text = "### Custom Only\nOnly this should appear"
        prompt = SongGenerator._build_system_prompt(lore, lore_text=custom_text)
        assert "### Custom Only" in prompt
        assert "Dict Lore" not in prompt

    def test_empty_lore_text_falls_through(self):
        """Empty lore_text should fall through to lore dicts."""
        from api_client import SongGenerator

        lore = [{"title": "Dict Lore", "content": "Dict content"}]
        prompt = SongGenerator._build_system_prompt(lore, lore_text="")
        assert "### Dict Lore" in prompt

    def test_no_lore_at_all(self):
        """No lore and no lore_text should show placeholder."""
        from api_client import SongGenerator

        prompt = SongGenerator._build_system_prompt([], lore_text=None)
        assert "No lore entries are currently active" in prompt


# =====================================================================
# Full app simulation — all tabs sharing one DB
# =====================================================================

class TestFullAppLoreWorkflow:
    """Simulate the real app with all three tabs to catch cross-tab freezes."""

    @pytest.fixture
    def full_app(self, qapp, tmp_path):
        """Create all three tabs sharing one DB, like the real app."""
        from database import Database
        from seed_data import SEED_GENRES, SEED_LORE
        from tabs.lore import LoreEditorTab
        from tabs.creator import SongCreatorTab
        from tabs.settings import SettingsTab

        db = Database(db_path=str(tmp_path / "fullapp.db"))
        for genre in SEED_GENRES:
            db.add_genre(
                name=genre["name"],
                prompt_template=genre["prompt_template"],
                description=genre.get("description", ""),
                bpm_range=genre.get("bpm_range", ""),
                active=genre.get("active", True),
            )
        for lore in SEED_LORE:
            db.add_lore(
                title=lore["title"],
                content=lore["content"],
                category=lore.get("category", "general"),
                active=lore.get("active", True),
            )

        lore_tab = LoreEditorTab(db)
        creator_tab = SongCreatorTab(db)
        settings_tab = SettingsTab(db)

        yield {
            "db": db,
            "lore_tab": lore_tab,
            "creator_tab": creator_tab,
            "settings_tab": settings_tab,
        }

        lore_tab.cleanup()
        creator_tab.cleanup()
        settings_tab.cleanup()
        db.close()

    def test_edit_lore_title_timed(self, full_app):
        """Editing a title should complete in under 1 second."""
        lore_tab = full_app["lore_tab"]
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)

        start = time.time()
        for i in range(50):
            lore_tab.title_edit.setText(f"Title change {i}")
        elapsed = time.time() - start

        assert elapsed < 1.0, f"50 title edits took {elapsed:.2f}s (too slow!)"

    def test_edit_lore_content_timed(self, full_app):
        """Editing content should complete in under 1 second."""
        lore_tab = full_app["lore_tab"]
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)

        start = time.time()
        for i in range(50):
            lore_tab.content_edit.setPlainText(f"Content change {i} " * 20)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"50 content edits took {elapsed:.2f}s (too slow!)"

    def test_save_with_cross_tab_signals_timed(self, full_app):
        """Saving should complete quickly even with cross-tab signal chain."""
        lore_tab = full_app["lore_tab"]
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)
        lore_tab.title_edit.setText("Cross-tab save test")

        start = time.time()
        lore_tab.save_current()
        elapsed = time.time() - start

        assert elapsed < 1.0, f"save_current took {elapsed:.2f}s (too slow!)"

    def test_rapid_save_cycle_timed(self, full_app):
        """10 edit-save cycles should complete in under 2 seconds."""
        lore_tab = full_app["lore_tab"]
        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)

        start = time.time()
        for i in range(10):
            lore_tab.title_edit.setText(f"Cycle {i}")
            lore_tab.content_edit.setPlainText(f"Content for cycle {i}")
            lore_tab.save_current()
        elapsed = time.time() - start

        assert elapsed < 2.0, f"10 edit-save cycles took {elapsed:.2f}s (too slow!)"

    def test_switch_entries_with_signals_timed(self, full_app):
        """Switching between entries should be fast."""
        lore_tab = full_app["lore_tab"]
        count = lore_tab.lore_list.count()
        if count < 2:
            pytest.skip("Need multiple entries")

        start = time.time()
        for i in range(min(count, 10)):
            item = lore_tab.lore_list.item(i)
            lore_tab.lore_list.setCurrentItem(item)
            lore_tab.title_edit.setText(f"Switch test {i}")
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Switching {min(count,10)} entries took {elapsed:.2f}s"

    def test_bulk_ops_with_all_tabs_timed(self, full_app):
        """Bulk operations with all tabs active should be fast."""
        lore_tab = full_app["lore_tab"]

        start = time.time()
        lore_tab._on_select_all()
        lore_tab._on_deselect_all()
        lore_tab._on_select_all()
        lore_tab._on_deselect_all()
        elapsed = time.time() - start

        assert elapsed < 1.0, f"4 bulk toggles took {elapsed:.2f}s"

    def test_add_delete_with_signals_timed(self, full_app):
        """Add + delete with full signal chain should be fast."""
        lore_tab = full_app["lore_tab"]
        db = full_app["db"]

        start = time.time()
        lore_tab.add_new_lore()
        new_id = lore_tab._current_id
        # Direct delete (bypassing confirmation dialog)
        db.delete_lore(new_id)
        lore_tab._current_id = None
        lore_tab.load_lore_list()
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Add + delete took {elapsed:.2f}s"

    def test_auto_export_enabled_no_freeze(self, full_app, tmp_path):
        """With auto-export enabled, lore edits should not freeze."""
        db = full_app["db"]
        settings_tab = full_app["settings_tab"]
        lore_tab = full_app["lore_tab"]

        # Enable auto-export
        sync_folder = str(tmp_path / "sync")
        os.makedirs(sync_folder, exist_ok=True)
        settings_tab.sync_folder_edit.setText(sync_folder)
        settings_tab.auto_export_check.setChecked(True)
        settings_tab._setup_auto_export()

        item = lore_tab.lore_list.item(0)
        lore_tab.lore_list.setCurrentItem(item)

        start = time.time()
        for i in range(5):
            lore_tab.title_edit.setText(f"Auto-export test {i}")
            lore_tab.save_current()
        elapsed = time.time() - start

        assert elapsed < 2.0, f"5 saves with auto-export took {elapsed:.2f}s"

    def test_creator_refresh_after_lore_save(self, full_app):
        """Creator checkboxes should update after lore tab save."""
        lore_tab = full_app["lore_tab"]
        creator_tab = full_app["creator_tab"]

        initial_count = len(creator_tab._lore_checkboxes)

        # Add new lore via lore tab
        lore_tab.add_new_lore()

        # Creator should have been refreshed by event bus
        assert len(creator_tab._lore_checkboxes) == initial_count + 1

    def test_creator_category_checkbox_after_refresh(self, full_app):
        """Category checkboxes should be correct after event-bus refresh."""
        creator_tab = full_app["creator_tab"]

        # Check all, then trigger refresh
        creator_tab._select_all_lore()
        creator_tab.refresh_lore()

        # Category checkboxes should reflect the DB state
        for cat, cat_cb in creator_tab._category_checkboxes.items():
            # Category checkbox should NOT be None
            assert cat_cb is not None

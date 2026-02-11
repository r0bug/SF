# Song Factory 2.0 — Standardization & Growth

## Introduction
Song Factory is a PyQt6 desktop application (~12,000 LOC, 30+ modules) for AI-powered song creation, management, CD mastering, and distribution via lalals.com. It was built feature-first and now needs architectural standardization, hardening, and future-proofing. This PRD decomposes the full specification into right-sized, dependency-ordered user stories for autonomous execution.

## Goals
- Establish shared base classes and patterns (Theme, BaseTab, BaseWorker)
- Fix data integrity issues (FK cascades, indexes, schema versioning)
- Add centralized logging, validation, retry, and secure credential storage
- Build test infrastructure covering all modules
- Add user-facing features: export/import, batch ops, AI model flexibility, keyboard shortcuts
- Future-proof: distributor plugins, multi-artist, analytics, cloud sync design

## User Stories

### US-001: Schema Versioning (F-001)
Implement PRAGMA user_version-based migration framework in database.py. Wrap existing _migrate_songs_table() as version 1. Set current schema version. All future migrations go through this framework.
- [ ] `_run_migrations()` method reads `PRAGMA user_version` and runs numbered migrations
- [ ] Existing `_migrate_songs_table()` runs as migration version 1
- [ ] `PRAGMA user_version` set to current version after all migrations
- [ ] Existing databases upgrade without data loss (idempotent)
- [ ] New installs create tables and skip to current version
- [ ] `py_compile songfactory/database.py` passes

### US-002: Database Indexes (F-002)
Add indexes on frequently-queried columns via the versioned migration framework from US-001.
- [ ] Migration version 2 creates 9 indexes: idx_songs_status, idx_songs_genre_id, idx_songs_created_at, idx_songs_task_id, idx_lore_category, idx_lore_active, idx_distributions_status, idx_distributions_song_id, idx_cd_tracks_project_id
- [ ] All use CREATE INDEX IF NOT EXISTS for idempotency
- [ ] `py_compile songfactory/database.py` passes
- [ ] App launches successfully with `QT_QPA_PLATFORM=offscreen python3 songfactory/main.py`

### US-003: Foreign Key Integrity (F-003)
Add proper ON DELETE behavior to songs.genre_id (SET NULL) and distributions.song_id (CASCADE) via table rebuild migration.
- [ ] Migration version 3 rebuilds songs table with `genre_id REFERENCES genres(id) ON DELETE SET NULL`
- [ ] Migration version 3 rebuilds distributions table with `song_id REFERENCES songs(id) ON DELETE CASCADE`
- [ ] Uses CREATE new → INSERT SELECT → DROP old → RENAME pattern
- [ ] All existing data preserved after migration
- [ ] `PRAGMA foreign_key_check` returns empty after migration
- [ ] `py_compile songfactory/database.py` passes

### US-004: Centralized Theme Module (F-004)
Create theme.py with all color constants, status colors, and the global stylesheet. Update app.py to import from theme.py.
- [ ] New file `songfactory/theme.py` with Theme class containing BG, PANEL, TEXT, ACCENT, ERROR, SUCCESS, WARNING constants
- [ ] Theme.STATUS_COLORS dict with all 7 status colors
- [ ] `Theme.global_stylesheet()` returns the full dark stylesheet (moved from app.py DARK_STYLESHEET)
- [ ] `Theme.accent_button_style()` and `Theme.danger_button_style()` helper methods
- [ ] `app.py` imports and uses `Theme.global_stylesheet()` instead of inline DARK_STYLESHEET
- [ ] `py_compile` passes on both files
- [ ] App launches with identical visual appearance

### US-005: BaseTab Class (F-005 part 1)
Create tabs/base_tab.py with BaseTab(QWidget) base class providing lifecycle hooks and shared utilities. Convert genres.py as the first tab.
- [ ] New file `songfactory/tabs/base_tab.py` with BaseTab class
- [ ] BaseTab provides: `_init_ui()`, `_connect_signals()`, `refresh()`, `cleanup()` lifecycle hooks
- [ ] BaseTab provides: `show_error()`, `show_warning()`, `confirm()`, `register_worker()` utilities
- [ ] `tabs/genres.py` GenreManagerTab inherits from BaseTab instead of QWidget
- [ ] GenreManagerTab.refresh() calls load_genres()
- [ ] `py_compile` passes on base_tab.py and genres.py
- [ ] App launches and Genre Manager tab works identically

### US-006: BaseTab Migration — Lore, Discovery, Settings (F-005 part 2)
Convert lore.py, lore_discovery.py, and settings.py to inherit from BaseTab.
- [ ] LoreEditorTab inherits from BaseTab; refresh() calls load_lore_list()
- [ ] LoreDiscoveryTab inherits from BaseTab
- [ ] SettingsTab inherits from BaseTab; refresh() calls load_settings()
- [ ] All three tabs function identically after migration
- [ ] `py_compile` passes on all three files

### US-007: BaseTab Migration — Creator, Library, CD Master, Distribution (F-005 part 3)
Convert the remaining 4 tabs to inherit from BaseTab. Update app.py closeEvent to call cleanup() on all tabs.
- [ ] SongCreatorTab inherits from BaseTab; refresh() calls refresh_genres() + refresh_lore()
- [ ] SongLibraryTab inherits from BaseTab; refresh() calls load_songs()
- [ ] CDMasterTab inherits from BaseTab; refresh() calls refresh_projects()
- [ ] DistributionTab inherits from BaseTab; refresh() calls load_distributions()
- [ ] app.py closeEvent calls cleanup() on each tab before db.close()
- [ ] app.py _on_tab_changed() calls widget.refresh() uniformly
- [ ] `py_compile` passes on all files
- [ ] App launches with all tabs working

### US-008: Logging Infrastructure (F-006)
Create logging_config.py with rotating file handlers. Update main.py to call setup_logging() at startup.
- [ ] New file `songfactory/logging_config.py` with `setup_logging()` function
- [ ] Configures root logger `songfactory` with DEBUG level
- [ ] RotatingFileHandler at `~/.songfactory/logs/songfactory.log`, 5MB max, 3 backups
- [ ] Formatter: `%(asctime)s [%(name)s] %(levelname)s: %(message)s`
- [ ] `main.py` calls `setup_logging()` before creating QApplication
- [ ] `py_compile` passes on both files

### US-009: Fix Seed Data Integrity (S-005)
Fix the 2 seed songs that reference missing genres (INDIE ROCK, POP ROCK). Add those genres to SEED_GENRES or fix the song labels.
- [ ] All 29 SEED_SONGS resolve to a valid genre when matched against SEED_GENRES
- [ ] Either SEED_GENRES has entries for "Indie Rock" and "Pop Rock" OR song genre_labels are corrected
- [ ] `py_compile songfactory/seed_data.py` passes

### US-010: Test Infrastructure — conftest and Database Tests (F-007 part 1)
Set up pytest with conftest.py fixtures and comprehensive database CRUD tests.
- [ ] New directory `songfactory/tests/` with `__init__.py` and `conftest.py`
- [ ] `conftest.py` has `temp_db` fixture (temp file DB), `qt_app` fixture (offscreen)
- [ ] New file `tests/test_database.py` with tests for all 8 tables: CRUD for lore, genres, songs, config, cd_projects, cd_tracks, lore_presets, distributions
- [ ] Tests cover: add, get, update, delete, list operations
- [ ] Tests cover: schema versioning migration runs without error
- [ ] `pytest songfactory/tests/test_database.py` passes with 0 failures

### US-011: Test Infrastructure — Seed, Theme, Tab Smoke Tests (F-007 part 2)
Add tests for seed data integrity, theme module, and tab smoke tests.
- [ ] New file `tests/test_seed_data.py` — validates all seed songs match a genre
- [ ] New file `tests/test_theme.py` — Theme constants exist, stylesheet is non-empty string
- [ ] New file `tests/test_tabs_smoke.py` — each of 8 tabs instantiates without crash (offscreen)
- [ ] `pytest songfactory/tests/` runs all tests, exits with 0 failures

### US-012: Worker Base Class (S-002)
Create automation/base_worker.py with BaseWorker(QThread). Provides stop flag, DB lifecycle, progress signal.
- [ ] New file `songfactory/automation/base_worker.py` with BaseWorker class
- [ ] BaseWorker provides: `progress_update` signal, `error_occurred` signal
- [ ] BaseWorker provides: `request_stop()`, `_should_stop()`, `_open_db()`, `_close_db()`
- [ ] BaseWorker.run() opens DB, calls `_execute()`, closes DB in finally
- [ ] `py_compile songfactory/automation/base_worker.py` passes

### US-013: Configuration-Driven Timeouts (S-003)
Create a timeouts module with default values and config-table override support.
- [ ] New file `songfactory/timeouts.py` with TIMEOUTS dict and `get_timeout(db, key)` function
- [ ] Default timeout keys: login_wait_s, generation_poll_s, element_visible_ms, page_load_ms, api_request_s, ffmpeg_convert_s, download_s, xvfb_startup_s
- [ ] `get_timeout()` checks `db.get_config(f"timeout_{key}")` before falling back to default
- [ ] `py_compile songfactory/timeouts.py` passes

### US-014: Atomic File Operations (H-002)
Add atomic_write utility and apply to download_manager file saves.
- [ ] New file `songfactory/automation/atomic_io.py` with `atomic_write(target_path, write_fn)` function
- [ ] Uses tempfile.mkstemp + shutil.move pattern
- [ ] Cleans up temp file on failure
- [ ] `py_compile songfactory/automation/atomic_io.py` passes

### US-015: Retry & Backoff Utility (H-003)
Create a shared retry decorator for network operations.
- [ ] New file `songfactory/automation/retry.py` with `with_retry()` decorator
- [ ] Supports configurable max_attempts, backoff_base, retryable_exceptions
- [ ] Logs retry attempts with warning level (uses logging module)
- [ ] `py_compile songfactory/automation/retry.py` passes

### US-016: Input Validation Layer (H-005)
Create validators.py with validation functions for songs, distributions, and genres.
- [ ] New file `songfactory/validators.py` with ValidationError exception class
- [ ] `validate_song(title, prompt, lyrics, max_prompt_length)` returns list of errors
- [ ] `validate_distribution(song_id, songwriter, cover_art_path)` returns list of errors
- [ ] `validate_genre(name, prompt_template)` returns list of errors
- [ ] `py_compile songfactory/validators.py` passes

### US-017: Data Event Bus (S-004)
Create event_bus.py with signals for cross-tab data change notifications. Wire into creator.py and library.py.
- [ ] New file `songfactory/event_bus.py` with DataEventBus(QObject) singleton
- [ ] Signals: songs_changed, lore_changed, genres_changed, config_changed, distributions_changed, cd_projects_changed
- [ ] Creator tab emits songs_changed after saving a song
- [ ] Library tab connects to songs_changed to refresh
- [ ] Genre Manager emits genres_changed; Creator connects to refresh dropdown
- [ ] No circular refresh loops
- [ ] `py_compile` passes on all modified files

### US-018: Keyboard Shortcuts (S-006)
Add keyboard shortcuts for common actions: tab switching, generate, save, search, refresh.
- [ ] Ctrl+1 through Ctrl+8 switch to tabs 1-8 (registered in app.py)
- [ ] Ctrl+G triggers Generate in Creator tab
- [ ] Ctrl+S triggers Save in context-dependent tab
- [ ] Ctrl+F focuses search bar in Library/Lore Discovery
- [ ] F5 refreshes current tab
- [ ] `py_compile` passes on all modified files

### US-019: Secure Credential Storage (H-001)
Create secure_config.py using system keyring with DB fallback. Update settings.py to use it.
- [ ] New file `songfactory/secure_config.py` with get_secret() and set_secret()
- [ ] SENSITIVE_KEYS set: api_key, musicgpt_api_key, lalals_password, dk_password
- [ ] Falls back to db.get_config() when keyring is unavailable
- [ ] settings.py save/load uses secure_config for sensitive keys
- [ ] `py_compile` passes on both files

### US-020: Browser Profile Management (H-004)
Create automation/browser_profiles.py with centralized profile path management.
- [ ] New file `songfactory/automation/browser_profiles.py` with get_profile_path(), clear_profile(), clear_all_profiles()
- [ ] Profiles stored under `~/.songfactory/profiles/{service}/`
- [ ] `py_compile songfactory/automation/browser_profiles.py` passes

### US-021: Selector Health Check (H-006)
Create automation/selector_health.py with health check for lalals.com and DistroKid selectors.
- [ ] New file `songfactory/automation/selector_health.py` with SelectorHealthCheck class
- [ ] LALALS_CHECKS and DK_CHECKS lists of (name, url, selector) tuples
- [ ] `run_checks()` method navigates to pages and tests selectors
- [ ] Returns list of dicts with name, ok (bool), optional error
- [ ] `py_compile songfactory/automation/selector_health.py` passes

### US-022: Shared Widget Library — StatusBadge and SearchBar (S-001 part 1)
Create widgets/ package with StatusBadge and SearchBar. Use StatusBadge in library.py.
- [ ] New directory `songfactory/widgets/` with `__init__.py`
- [ ] New file `widgets/status_badge.py` — StatusBadge(QLabel) using Theme.STATUS_COLORS
- [ ] New file `widgets/search_bar.py` — SearchBar(QWidget) with debounce timer and search_changed signal
- [ ] Library tab uses StatusBadge from widgets package (replacing inline StatusBadgeWidget if present)
- [ ] `py_compile` passes on all files

### US-023: Shared Widget Library — LogViewer and FilePickerWithPreview (S-001 part 2)
Create LogViewer and FilePickerWithPreview shared widgets.
- [ ] New file `widgets/log_viewer.py` — LogViewer(QTextEdit) with append_line(), auto-scroll, read-only
- [ ] New file `widgets/file_picker.py` — FilePickerWithPreview(QWidget) with file_selected signal, image preview, validation
- [ ] `py_compile` passes on both files

### US-024: Export / Import (FT-001)
Create export_import.py with JSON export and import for songs, lore, genres.
- [ ] New file `songfactory/export_import.py`
- [ ] `export_to_json(db, entity_types, file_path)` — exports selected entities as versioned JSON
- [ ] `export_songs_csv(db, file_path)` — exports songs as flat CSV
- [ ] `import_from_json(db, file_path)` — imports with duplicate detection by title
- [ ] `preview_import(file_path)` — returns counts of new/existing/skipped items
- [ ] `py_compile songfactory/export_import.py` passes

### US-025: Batch Operations in Library (FT-002)
Add multi-select checkboxes and batch action menu to Library tab.
- [ ] Library song table has checkbox column for multi-select
- [ ] "Batch Actions" button with menu: Delete Selected, Set Status
- [ ] Batch delete shows confirmation with count, executes on confirm
- [ ] Batch status change shows status dropdown, applies to selected songs
- [ ] `py_compile songfactory/tabs/library.py` passes

### US-026: AI Model Flexibility (FT-003)
Abstract AI interface with model selection support. Update api_client.py and settings.py.
- [ ] api_client.py SongGenerator accepts model name parameter
- [ ] lore_summarizer.py uses configured model instead of hardcoded value
- [ ] Settings tab has model dropdown with available Claude models
- [ ] `py_compile` passes on api_client.py, lore_summarizer.py, settings.py

### US-027: Distributor Plugin Interface (FT-004)
Create automation/distributor_base.py with DistributorPlugin interface. Refactor DistroKid as first plugin.
- [ ] New file `songfactory/automation/distributor_base.py` with DistributorPlugin base class
- [ ] DistributorPlugin defines: name, requires_browser, genre_map, validate_release(), create_driver(), create_worker()
- [ ] DistroKid driver/worker implements DistributorPlugin interface
- [ ] `py_compile` passes on all files

### US-028: Analytics Dashboard (FT-005)
Create tabs/analytics.py with production metrics visualizations. Register in app.py.
- [ ] New file `songfactory/tabs/analytics.py` with AnalyticsTab
- [ ] Shows 4+ metrics: songs per month, status distribution, genre distribution, total counts
- [ ] Uses pure PyQt6 painting (no matplotlib dependency) for charts
- [ ] Charts readable in dark theme
- [ ] Registered as new tab in app.py
- [ ] `py_compile` passes; app launches with Analytics tab

### US-029: Multi-Artist Support (FP-001)
Add artists table with "Yakima Finds" as default. Update CD Master and Distribution to reference artist.
- [ ] Migration adds artists table via versioned migration framework
- [ ] "Yakima Finds" seeded as default artist (is_default=1)
- [ ] Database CRUD methods for artists: get_all_artists, get_default_artist, add_artist, update_artist
- [ ] CD projects and distributions reference artist by concept (not hardcoded)
- [ ] `py_compile songfactory/database.py` passes

### US-030: Xvfb Conflict Resolution (FP-003)
Update xvfb_manager.py to auto-detect available display numbers.
- [ ] `_find_free_display()` checks /tmp/.X{N}-lock files for displays 99-199
- [ ] XvfbManager.start() uses first available display
- [ ] Display number stored and communicated via DISPLAY env var
- [ ] `py_compile songfactory/automation/xvfb_manager.py` passes

### US-031: Cloud Sync Design Document (FP-002)
Create architecture document for future cloud sync capability.
- [ ] New file `docs/cloud-sync-design.md` with sync architecture
- [ ] Covers: JSON change log export, audio hash-based sync, conflict resolution
- [ ] Documents incremental sync via updated_at timestamps
- [ ] No code changes required

### US-032: Final Integration Test Suite
Run full test suite and app launch verification. Fix any remaining issues.
- [ ] `pytest songfactory/tests/` exits with 0 failures
- [ ] `QT_QPA_PLATFORM=offscreen python3 songfactory/main.py` launches without errors (timeout kill = success)
- [ ] `py_compile` passes on every .py file in songfactory/
- [ ] All 32 user stories marked complete

## Non-Goals
- Browser automation E2E tests (requires live browser + credentials)
- CD burning integration tests (requires physical hardware)
- Production deployment automation
- GUI regression screenshot testing

## Technical Notes
- Python 3.10+, PyQt6, SQLite WAL mode
- Test with `QT_QPA_PLATFORM=offscreen` for headless Qt
- Ubuntu pip needs `--break-system-packages` flag
- Database at `~/.songfactory/songfactory.db`
- All new modules must pass `py_compile` before marking complete
- Preserve all existing behavior — no functional regressions

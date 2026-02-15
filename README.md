# Song Factory — Yakima Finds

A PyQt6 desktop application for AI-powered song creation, management, and CD mastering. Song Factory uses the Anthropic API to generate lore-aware, genre-sensitive lyrics and music prompts for AI music generation via lalals.com.

## Features

- **Song Creator** — Generate songs with AI using customizable lore context, genre selection, and style notes. Lore preview lets you review and edit the exact lore context before generation. Background threaded API calls keep the UI responsive.
- **Lore Editor** — Manage world-building lore entries (people, places, events, themes, rules, general) with category filtering, bulk toggle controls, saveable presets, and lore-only export/import.
- **Lore Discovery** — Search the web, summarize content with AI, and save results directly as lore entries.
- **Genre Manager** — Create and manage genre definitions with prompt templates, BPM ranges, and descriptions.
- **Song Library** — Browse, search, and filter songs by genre, status, or tag. Includes browser automation queue for submitting songs to lalals.com and downloading results. Multi-select with batch delete/status/export. User-defined song tags with colored chips, context-menu tagging, and a Manage Tags dialog. Inline rename via detail panel or context menu. Error recovery via headless home-page download. "Wrong Song" button deletes mismatched downloads and triggers re-download.
- **CD Master** — Create audio CD projects with track ordering, CD-TEXT metadata, cover art generation, and cross-platform ISO export via pycdlib.
- **Distribution** — Upload finished songs to streaming platforms (Spotify, Apple Music, etc.) via DistroKid browser automation. Includes release form, genre mapping, cover art validation/resize, AI cover art generation (Segmind API), AI disclosure, and upload queue with login/2FA support.
- **Analytics** — Song statistics, status breakdown charts, and generation history.
- **Settings** — Configure API keys (Anthropic, MusicGPT, Segmind), lalals.com credentials, DistroKid credentials, browser automation paths, Xvfb virtual display, pipeline diagnostics, debug screenshots, database backup/restore, and personal data sync (Dropbox/Google Drive cloud sync with auto-export).

## Tech Stack

| Component | Technology |
|-----------|-----------|
| UI Framework | PyQt6 |
| AI Backend | Anthropic API (Claude) |
| Database | SQLite (WAL mode) |
| Music Generation | lalals.com (browser automation + MusicGPT API) |
| Cover Art Generation | Segmind API (Flux 1.1 Pro, SDXL, Vega) |
| Distribution | DistroKid (browser automation) |
| Browser Automation | Playwright |
| ISO Export | pycdlib (cross-platform) |
| Web Search | DuckDuckGo Search |

## Installation

```bash
# Clone the repository
git clone https://github.com/r0bug/SF.git
cd SF

# Install dependencies
pip install -r requirements.txt

# Or install as a package (editable mode)
pip install -e .

# Install Playwright browsers (for lalals.com automation)
playwright install chromium

# Run the application
python songfactory/main.py
# or via entry point (if installed with pip install -e .)
songfactory
```

### Pre-built Binaries

See [BUILD.md](BUILD.md) for instructions on building standalone executables for Linux, macOS, and Windows using PyInstaller.

## Configuration

On first launch, the app creates a SQLite database at `~/.songfactory/songfactory.db` and seeds it with default genres, lore entries, and sample songs.

### Required Settings

1. **Anthropic API Key** — Set in the Settings tab. Required for song generation.

### Optional Settings

2. **Lalals.com Credentials** — Email/password for browser automation song submission.
3. **MusicGPT API Key** — For direct API submission mode (alternative to browser automation).
4. **DistroKid Credentials** — Email, password, default artist name, and songwriter legal name for distribution uploads.
5. **Segmind API Key** — For AI cover art generation (Flux 1.1 Pro, SDXL, Vega models).
6. **Download Directory** — Where generated audio files are saved (default: `~/Music/SongFactory`).

### Backup & Restore

Database backups are stored as timestamped files (`songfactory_backup_YYYYMMDD_HHMMSS.db`) in the download directory. Use **Backup Now** in Settings to create a backup, or **Restore from Backup** to recover from one. On a fresh install, the app automatically detects backups in the download directory and offers to restore.

## Project Structure

```
songfactory/
  main.py                  # Entry point
  app.py                   # MainWindow, tab setup, seed logic
  database.py              # Database class — all CRUD, migrations, presets
  api_client.py            # SongGenerator — Anthropic API wrapper
  seed_data.py             # Default genres, lore, and sample songs
  theme.py                 # Centralized colors/styles (Theme class)
  event_bus.py             # DataEventBus singleton (cross-tab signals)
  validators.py            # Input validation (song, genre, lore, distribution)
  secure_config.py         # Keyring-backed credential storage with DB fallback
  logging_config.py        # RotatingFileHandler (5MB, 3 backups)
  timeouts.py              # Config-driven timeouts with DB override
  ai_models.py             # Central model registry (DEFAULT_MODEL, get_model_choices)
  export_import.py         # JSON/CSV export, JSON import, personal bundle sync
  web_search.py            # DuckDuckGo web search integration
  lore_summarizer.py       # AI-powered content summarization for lore
  platform_utils.py        # Cross-platform detection (Linux/macOS/Windows, frozen app)
  icon.svg                 # Application icon
  icon.ico                 # Windows icon (multi-resolution)
  icon.icns                # macOS icon
  tabs/
    base_tab.py            # BaseTab(QWidget) lifecycle: _init_ui, _connect_signals, refresh, cleanup
    creator.py             # Song Creator tab — grouped lore, presets, generation
    lore.py                # Lore Editor tab — bulk toggles, presets, auto-save
    lore_discovery.py      # Lore Discovery tab — web search + summarize
    genres.py              # Genre Manager tab — table + detail panel
    library.py             # Song Library tab — search, filter, queue, automation, recovery
    settings.py            # Settings tab — API keys, diagnostics, pipeline testing
    cd_master.py           # CD Master tab — projects, tracks, art, burning
    distribution.py        # Distribution tab — DistroKid upload queue & form
    analytics.py           # Analytics tab — statistics and charts
    history_import_dialog.py  # Dialog for importing lalals.com history
    song_picker_dialog.py  # Dialog for selecting songs (CD track picker)
    cover_art_dialog.py    # Dialog for AI cover art generation (Segmind)
  widgets/
    status_badge.py        # StatusBadge colored label widget
    search_bar.py          # SearchBar with filter controls
    log_viewer.py          # LogViewer for automation logs
    tag_chips.py           # TagChipsWidget for colored song tag chips
  automation/
    base_worker.py         # BaseWorker(QThread) with stop flag, DB lifecycle
    browser_worker.py      # LalalsWorker QThread — submit/download pipeline
    lalals_driver.py       # Playwright browser driver for lalals.com
    browser_profiles.py    # Centralized profile paths, cache clearing
    selector_health.py     # CSS selector health checks for lalals.com
    selector_registry.py   # Self-healing CSS selector registry with promote/demote learning
    pipeline_diagnostics.py # 5-phase browser pipeline diagnostic worker
    retry.py               # with_retry decorator, exponential backoff
    atomic_io.py           # Atomic file write utilities
    distrokid_driver.py    # Playwright browser driver for distrokid.com
    distrokid_worker.py    # DistroKid upload QThread — login/2FA, form fill, upload
    distributor_base.py    # DistributorPlugin ABC, DistroKidPlugin
    cover_art_preparer.py  # Cover art validation and resize for distribution
    download_manager.py    # File download + audio validation (Playwright + HTTP)
    image_generator.py     # Segmind API client for AI cover art generation
    api_worker.py          # MusicGPT API worker thread
    history_importer.py    # Lalals.com history import thread
    song_detail_syncer.py  # Sync prompt/lyrics from lalals.com profile API
    profile_scraper.py     # Profile page scraper with Load More support
    xvfb_manager.py        # Xvfb virtual display manager
    network_sniffer.py     # Network traffic debugging tool
    chrome_bridge.py       # File-based Chrome extension protocol
    audio_converter.py     # Audio format conversion for CD burning
    cd_art_generator.py    # CD cover/disc art generation (platform-aware fonts)
    iso_builder.py         # Cross-platform ISO image builder (pycdlib)
    data_session_builder.py # CD-Extra data session builder
  tests/
    test_lalals_fixes.py   # Tests for browser integration bug fixes
    test_pipeline_diagnostics.py # Tests for diagnostic tool
    test_personal_bundle.py # Tests for personal data bundle export/import
pyproject.toml             # Project metadata and pip install config
songfactory.spec           # PyInstaller build spec
scripts/
  build_linux.sh           # Linux build script (+ optional AppImage)
  build_macos.sh           # macOS build script (+ DMG)
  build_windows.bat        # Windows build script
  convert_icons.py         # SVG → ICO/ICNS icon converter
BUILD.md                   # Build instructions for all platforms
tests/                     # Main test suite (311 tests)
```

## Database

SQLite database at `~/.songfactory/songfactory.db` with WAL journaling and foreign keys enabled. See [Schema.md](Schema.md) for full table definitions.

## License

Private project — Yakima Finds.

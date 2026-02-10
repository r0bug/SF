# Song Factory — Yakima Finds

A PyQt6 desktop application for AI-powered song creation, management, and CD mastering. Song Factory uses the Anthropic API to generate lore-aware, genre-sensitive lyrics and music prompts for AI music generation via lalals.com.

## Features

- **Song Creator** — Generate songs with AI using customizable lore context, genre selection, and style notes. Background threaded API calls keep the UI responsive.
- **Lore Editor** — Manage world-building lore entries (people, places, events, themes, rules, general) with category filtering, bulk toggle controls, and saveable presets.
- **Lore Discovery** — Search the web, summarize content with AI, and save results directly as lore entries.
- **Genre Manager** — Create and manage genre definitions with prompt templates, BPM ranges, and descriptions.
- **Song Library** — Browse, search, and filter songs by status. Includes browser automation queue for submitting songs to lalals.com and downloading results.
- **CD Master** — Create audio CD projects with track ordering, CD-TEXT metadata, cover art generation, and disc burning via cdrdao/wodim.
- **Distribution** — Upload finished songs to streaming platforms (Spotify, Apple Music, etc.) via DistroKid browser automation. Includes release form, genre mapping, cover art validation/resize, AI disclosure, and upload queue with login/2FA support.
- **Settings** — Configure API keys (Anthropic, MusicGPT), lalals.com credentials, DistroKid credentials, browser automation paths, Xvfb virtual display, network diagnostics, and database backup/restore.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| UI Framework | PyQt6 |
| AI Backend | Anthropic API (Claude) |
| Database | SQLite (WAL mode) |
| Music Generation | lalals.com (browser automation + MusicGPT API) |
| Distribution | DistroKid (browser automation) |
| Browser Automation | Playwright |
| CD Burning | cdrdao, wodim |
| Web Search | DuckDuckGo Search |

## Installation

```bash
# Clone the repository
git clone https://github.com/r0bug/SF.git
cd SF

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for lalals.com automation)
playwright install chromium

# Run the application
cd songfactory
python main.py
```

## Configuration

On first launch, the app creates a SQLite database at `~/.songfactory/songfactory.db` and seeds it with default genres, lore entries, and sample songs.

### Required Settings

1. **Anthropic API Key** — Set in the Settings tab. Required for song generation.

### Optional Settings

2. **Lalals.com Credentials** — Email/password for browser automation song submission.
3. **MusicGPT API Key** — For direct API submission mode (alternative to browser automation).
4. **DistroKid Credentials** — Email, password, default artist name, and songwriter legal name for distribution uploads.
5. **Download Directory** — Where generated audio files are saved (default: `~/Music/SongFactory`).

### Backup & Restore

Database backups are stored as timestamped files (`songfactory_backup_YYYYMMDD_HHMMSS.db`) in the download directory. Use **Backup Now** in Settings to create a backup, or **Restore from Backup** to recover from one. On a fresh install, the app automatically detects backups in the download directory and offers to restore.

## Project Structure

```
songfactory/
  main.py                  # Entry point
  app.py                   # MainWindow, dark theme, tab setup, seed logic
  database.py              # Database class — all CRUD, migrations, presets
  api_client.py            # SongGenerator — Anthropic API wrapper
  seed_data.py             # Default genres, lore, and sample songs
  web_search.py            # DuckDuckGo web search integration
  lore_summarizer.py       # AI-powered content summarization for lore
  icon.svg                 # Application icon
  tabs/
    creator.py             # Song Creator tab — grouped lore, presets, generation
    lore.py                # Lore Editor tab — bulk toggles, presets, auto-save
    lore_discovery.py      # Lore Discovery tab — web search + summarize
    genres.py              # Genre Manager tab — table + detail panel
    library.py             # Song Library tab — search, filter, queue, automation
    settings.py            # Settings tab — API keys, paths, diagnostics
    cd_master.py           # CD Master tab — projects, tracks, art, burning
    distribution.py        # Distribution tab — DistroKid upload queue & form
    history_import_dialog.py  # Dialog for importing lalals.com history
    song_picker_dialog.py  # Dialog for selecting songs (CD track picker)
  automation/
    browser_worker.py      # LalalsWorker QThread — submit/download pipeline
    lalals_driver.py       # Playwright browser driver for lalals.com
    distrokid_driver.py    # Playwright browser driver for distrokid.com
    distrokid_worker.py    # DistroKid upload QThread — login/2FA, form fill, upload
    cover_art_preparer.py  # Cover art validation and resize for distribution
    download_manager.py    # File download utilities (Playwright + HTTP)
    api_worker.py          # MusicGPT API worker thread
    history_importer.py    # Lalals.com history import thread
    song_detail_syncer.py  # Sync prompt/lyrics from lalals.com profile API
    profile_scraper.py     # Profile page scraper with Load More support
    xvfb_manager.py        # Xvfb virtual display manager
    network_sniffer.py     # Network traffic debugging tool
    chrome_bridge.py       # File-based Chrome extension protocol
    audio_converter.py     # Audio format conversion for CD burning
    cd_art_generator.py    # CD cover/disc art generation
    cd_burn_worker.py      # CD burning worker thread (cdrdao/wodim)
    data_session_builder.py # CD-Extra data session builder
    toc_generator.py       # CD TOC file generator
```

## Database

SQLite database at `~/.songfactory/songfactory.db` with WAL journaling and foreign keys enabled. See [Schema.md](Schema.md) for full table definitions.

## License

Private project — Yakima Finds.

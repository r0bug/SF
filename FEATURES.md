# Song Factory — Feature Documentation

## Song Creator

The primary workflow tab for generating AI songs.

### Input Panel
- **Creative Prompt** — Free-text description of the desired song
- **Genre Selection** — Dropdown of active genres from the Genre Manager, or "Auto" to let AI choose
- **Style Notes** — Optional style reference (e.g., "in the style of Beach Bunny")
- **Lore Context** — Collapsible section with grouped lore checkboxes

### Lore Context Controls
- **Grouped by Category** — Lore entries organized under bold category headers (People, Places, Events, Themes, Rules, General)
- **Category Toggle** — Tri-state checkbox per category to select/deselect all entries in that group
- **Select All / Deselect All** — Quick buttons to check or uncheck every lore entry
- **Preset Dropdown** — Apply saved lore presets to quickly configure lore selections without modifying database active flags
- **Save Preset** — Save the currently checked lore entries as a new named preset directly from the Creator tab
- Scroll area (350px max height) accommodates the grouped layout

### Lore Preview
- **Select Lore** button — Formats all checked lore entries and loads them into an editable preview area
- **Editable preview** — Review, edit, add, or remove lore text before generation. The exact text in this box is sent as the lore context to the AI.
- If no lore entries are checked, the preview opens empty with an informational message; you can type custom lore directly
- When the preview is visible, Generate Song uses its contents; when hidden, it falls back to the checkbox selection

### Output Panel
- **Generated Prompt** — Editable prompt field with character counter (300 char target for lalals.com)
- **Generated Lyrics** — Editable lyrics with verse/chorus/bridge structure markers
- **Actions** — Save to Database, Queue for Lalals, Copy Prompt, Copy Lyrics
- **No duplicates** — Saving and queueing the same generated song (in either order) updates one library entry; a queued song is never downgraded back to draft. A new generation creates a new entry

### Generation
- Background QThread prevents UI freezing during API calls
- Uses Anthropic Claude API with lore-aware system prompts
- "Yakima" always spelled "Yak-eh-Mah" for correct AI vocal pronunciation

---

## Lore Editor

Manage world-building lore entries used as context for song generation.

### Layout
- Horizontal splitter: filterable list (left) + full editor (right)
- Auto-save on 2-second debounce and when switching between entries

### Categories
- people, places, events, themes, rules, general
- Filter dropdown to show entries by category

### Bulk Toggle Controls
- **Select All** — Activate all lore entries across all categories
- **Deselect All** — Deactivate all lore entries
- **Toggle Category** — Enable/disable all entries in the currently filtered category. Button label dynamically shows "Enable {category}" or "Disable {category}" based on majority state. Only enabled when a specific category filter is selected.

### Lore Presets
- **Apply** — Deactivates all lore, then activates only the entries saved in the selected preset
- **Save New** — Prompts for a name and saves all currently active lore entry IDs as a new preset
- **Update** — Overwrites the selected preset with the currently active lore entries (with confirmation)
- **Delete** — Removes the selected preset after confirmation (does not affect lore entries)

### Lore Export / Import
- **Export Lore** — Export lore entries to a portable JSON bundle (lore-only mode)
- **Import Lore** — Import lore entries from a personal bundle file, with upsert-by-name (creates new or updates existing)

### Editor
- Title, category dropdown, active checkbox, and markdown content editor
- Dimmed text in the list for inactive entries
- Unsaved-changes tracking with dirty flag

---

## Lore Discovery

Search the web, summarize content with AI, and import as lore entries.

- DuckDuckGo web search integration
- AI-powered content summarization via Anthropic API
- Category assignment and inline editing before saving
- Background QThreads for search and summarization
- **Summarize & Merge** — Check two or more search results; each is summarized, then Claude merges them into one lore entry (duplicate facts combined, every name/place/story kept, conflicting sources noted, all sources listed). Only the merged card is shown; if the merge fails the individual summaries are shown instead
- **Merge Selected Summaries** — Every summary card has an "Include in merge" checkbox; merge any two or more (including edits and previously merged entries) into a new card labelled "Merged from N sources"

---

## Genre Manager

Create and manage genre definitions.

- Table view with name, description, BPM range, active status
- Detail panel for editing prompt templates
- Prompt templates guide the AI when generating songs in that genre

---

## Song Library

Browse, search, and manage all songs with automation controls.

### Search & Filter
- Text search across title, lyrics, prompt, and notes
- Genre filter dropdown
- Status filter dropdown (draft, queued, processing, submitted, completed, error, imported)
- Tag filter dropdown — show only songs with a specific tag

### Song Table
- Colored status badges per song
- Tag chips column showing up to 4 colored tag chips per song with "+N" overflow
- Expandable detail area for viewing/editing individual songs (including inline title editing)

### Song Rename
- **Detail panel** — Title is an editable text field; changes saved with the Save button
- **Context menu** — Right-click → Rename opens an input dialog for quick title changes

### Song Tags
- **6 built-in tags**: Favorite, Released, Needs Lyrics, Halloween, Love Song, Instrumental
- **User-created tags** with custom names and colors
- **Context menu** — Right-click a song → Tags submenu with checkable items + "Create New Tag..."
- **Detail area** — Tags row with colored chips and "Edit Tags" button (opens checkable list dialog)
- **Manage Tags dialog** — Add, rename, change color, delete tags (built-in tags cannot be deleted)
- **Tag filter** — Dropdown in the filter bar to show only songs with a specific tag

### Automation Queue
- **Browser Mode** — Playwright-based headless browser automation: submit songs to lalals.com, wait for processing, download results
- **API Mode** — Direct submission via MusicGPT API with automatic polling and download
- **Sync** — Import song details (prompt, lyrics, metadata) from lalals.com profile API
- **History Import** — Discover and import previously generated songs from lalals.com account (one library song per generated version, lyrics filled from project detail; in-progress generations are skipped)
- **Download All History** — One click in the Import History dialog: discovers the whole history and imports every song not already in the library
- **Play Version 2** — Context menu plays either generated take ("Play Song (Version 1)" / "Play Version 2")
- Always headless — browser runs in background, cannot be interrupted by user interaction
- Centralized browser profile at `~/.songfactory/profiles/lalals/` preserves login session
- Retry with exponential backoff on download failures

### Error Recovery
All recovery paths share `automation/lalals_recovery.py`, so a failed "Song is Done - Refresh" can always be retried later:

1. **Saved IDs** — the version IDs (`conversion_id_1/2`, or `task_id` for history imports) stored at submit time are looked up via `projects/front/get-one-by-id`
2. **Prompt match** — songs without IDs are found in the full lalals history by their prompt; the newest finished generation (both versions) is used

- **Re-download / Recover from Lalals** — Right-click a single song
- **Recover Error Songs** — Batch-recover every song in `error` status
- **Recover Downloads** — Batch-recover every song with lalals IDs but no audio file
- A summary lists songs not found (still generating, failed on lalals, or audio no longer available)
- **Wrong Song** — Orange button in the detail panel and "Wrong Song — Re-download" context menu action. Deletes all downloaded files (file_path_1, file_path_2, vocals, instrumental), removes empty parent directories, sets status to "error", and re-downloads via the recovery lookup. Available only when a downloaded file exists.
- **Refresh Library** button reloads the song list from the database

### Download Verification
- **Audio header validation** — Downloaded files are checked for valid MP3 (sync word `0xFF 0xE0` or ID3 tag), WAV (RIFF), OGG, or FLAC headers
- **Minimum size check** — Files under 10 KB are rejected (likely error pages or empty responses)
- **HTML/JSON error detection** — Files starting with `<`, `{`, or `[` are identified as text/markup and rejected
- **Size mismatch detection** — When an expected file size is provided, downloads differing by more than 5% are rejected
- **Automatic cleanup** — Invalid files are deleted immediately after detection
- **File size propagation** — `file_size_1` and `file_size_2` database columns are always populated from actual on-disk file sizes after every download path (API, browser, home page recovery)
- **Date-prefixed download folders** — Downloads are organized into `~/Music/SongFactory/YYYY-MM-DD_song-title/` directories, making it easy to identify when files were downloaded. Re-downloads on a different day automatically get a new folder. Old songs with non-dated paths continue to work via stored absolute paths in the database.

### Self-Healing Selectors
- **SelectorRegistry** — Persists CSS selector priority order to `~/.songfactory/selector_registry.json`
- **Promote on success** — When a selector matches a visible element, it moves to the front of its group for next time
- **Demote on failure** — When a selector fails, it moves to the back of its group
- **Grouped selectors** — `prompt_textarea`, `lyrics_toggle`, `lyrics_textarea`, `generate_button`, `home_nav`
- **Register-once semantics** — Default selector order is only written for new groups; learned ordering persists across sessions

### lalals.com API (`automation/lalals_api.py`)
lalals.com (2026 redesign) serves its backend through a same-origin proxy at `https://lalals.com/api/backend/`, authenticated by browser session cookies. All calls run inside the Playwright page (`page.evaluate(fetch)`); mutating requests send `X-Lalals-Auth-Version: 2` and the `X-Lalals-CSRF` token from `GET auth/session` (which also serves as the login check — 401 when logged out). The old `devapi.lalals.com` host no longer exists.

### Submission (Co-Producer workflow)
1. `POST v1/workflows` — `{workflowId: "produce_track_v1", initialContext: {prompt, lyrics, workflow_mode: "MUSIC_AI", make_instrumental, extendDuration}}`
2. `POST v1/workflows/{projectId}/action` — `{action: "generate_music_ai", payload: {..., prompt_intensity, lyrics_intensity, uniqueness}}` (0.6 defaults, matching the UI)
3. The two generated versions appear in `POST user/{uid}/projects` within seconds; their IDs are stored as `conversion_id_1/2` (matched by prompt + submit time)
4. Workflow states: INITIAL, GENERATING_LYRICS, WAITING_FOR_LYRICS_APPROVAL, GENERATING_AUDIO, PARTIAL_COMPLETED, COMPLETED, ERROR

No form filling or DOM selectors are needed, so page redesigns don't break submission.

### Download Strategies (Priority Order)
1. **Projects API** — Look up the version IDs in `user/{uid}/projects` and download each `track_url`
2. **Project detail** — `projects/front/get-one-by-id/{id}` per version
3. **S3 fallback** — Built URLs are a last resort only: new generations are served from `cdn1.musicgpt.com` (not derivable), mid-2026 ones from `conversions/web/standard/`, older ones from `conversions/standard/` (also used for early-2026 projects whose `track_url` is broken)

History pagination sends the response's `nextCursor` (`{page, limit}`) as top-level body fields.

### Song Statuses
| Status | Description |
|--------|-------------|
| draft | Saved but not submitted |
| queued | Ready for submission |
| processing | Submitted, awaiting generation |
| submitted | Sent to lalals.com |
| completed | Generated and downloaded |
| error | Failed during processing |
| imported | Imported from lalals.com history |

---

## CD Master

Create audio CD projects with full CD-TEXT metadata and cross-platform ISO export.

### Project Management
- Create, duplicate, and delete CD projects
- Artist, album title, songwriter, and message metadata

### Track Editor
- Add songs from the library via picker dialog
- Reorder tracks with drag-and-drop
- Per-track metadata: performer, songwriter, pregap
- Duration tracking with 74-minute warning and 80-minute Red Book limit

### Disc Options
- Include data session (CD-Extra) with selectable content: source files, lyrics, MP3s
- Cover art, disc art, and back art with generate/import options

### ISO Export
- **Export ISO** — Creates a standards-compliant ISO 9660 image (Level 4 + Joliet + Rock Ridge) using pycdlib (pure Python, cross-platform)
- Audio conversion to WAV via ffmpeg
- Data session includes MP3s, lyrics text files, album info, and optional Song Factory source code
- File dialog with suggested filename from album title
- Progress tracking during build with file-by-file status

---

## Distribution

Upload finished songs to streaming platforms (Spotify, Apple Music, etc.) via DistroKid browser automation.

### Distribution Queue
- List of distribution records filtered by status (draft, ready, uploading, submitted, live, error)
- Create new distributions from completed songs
- Delete unwanted distribution records

### Release Form
- **Song Selection** — Dropdown of all songs (with audio file indicator)
- **Artist Name** — Defaults to configured DistroKid artist (must match registered DK artist)
- **Release Title** — Defaults to song title for singles
- **Songwriter** — Legal name (required by DistroKid)
- **Genre** — Song Factory genre with automatic mapping to DistroKid's genre list (23 mappings)
- **Language** — Dropdown with common languages
- **Cover Art** — File picker with preview, validation (min 1000x1000, square, JPG/PNG), auto-resize to 3000x3000, or AI-generated via Segmind API
- **Instrumental Flag** — Checkbox for instrumental tracks
- **AI Disclosure** — Checkbox for AI-generated content (checked by default)
- **Release Date** — Calendar picker
- **Record Label** — Optional
- **Lyrics** — Auto-populated from song, submitted as plain text

### Genre Mapping (Song Factory → DistroKid)
All 23 Song Factory genres are mapped to DistroKid's fixed genre list:
- Pop → Pop, Hip-Hop → Hip-Hop/Rap, Rock → Rock, Country → Country
- EDM/Dance → Dance, R&B/Soul → R&B/Soul, Folk/Americana → Singer/Songwriter
- Afrobeats → Worldwide, K-Pop → K-Pop, Reggae → Reggae, Funk → Funk
- Alt-Rock/Indie Pop-Rock → Alternative, Electropop → Electronic
- Unmapped genres fall back to "Pop"

### Cover Art Preparation
- Validates format (JPG/PNG only), dimensions (minimum 1000x1000), and aspect ratio (must be square)
- Auto-resizes to 3000x3000 using Lanczos resampling (requires Pillow)

### AI Cover Art Generation
- **Generate Art** button in the Distribution form opens a cover art generation dialog
- Requires a Segmind API key (configured in Settings)
- Generates cover art from the song's lyrics using AI image models
- Supported Segmind models: Flux 1.1 Pro (default), SDXL 1.0, Segmind Vega
- Generates at 1024x1024 resolution for speed, auto-resized to 3000x3000 for distribution
- Generates multiple candidates (default 4) for the user to choose from
- WEBP responses from Segmind are automatically converted to PNG via Pillow for Qt compatibility
- Selected image is saved and auto-fills the cover art path

### Upload Workflow
1. Mark distribution as "Ready" (validates required fields)
2. Click "Upload Now" — launches Playwright browser with persistent profile
3. If not logged in, opens DistroKid sign-in page for manual login + 2FA
4. Worker polls until login completes, then fills the upload form automatically
5. Uploads audio file and cover art, submits the release
6. Status updates: draft → ready → uploading → submitted → live / error

### Authentication
- DistroKid requires email/password + mandatory 2FA (6-digit code to email)
- Persistent browser profile at `~/.songfactory/dk_browser_profile` preserves session cookies
- Same manual login pattern as lalals.com automation

### Distribution Statuses
| Status | Description |
|--------|-------------|
| draft | Created but not validated |
| ready | Validated, waiting for upload |
| uploading | Browser automation in progress |
| submitted | Successfully uploaded to DistroKid |
| live | Confirmed live on streaming platforms |
| error | Upload failed (see error message) |

---

## Analytics

Song statistics and generation history.

- Status breakdown with counts per status
- Generation timeline and trends
- Quick-access filters to Song Library by status

---

## Export / Import

- **Export** — JSON or CSV export of selected songs (batch or individual)
- **Import** — JSON import with duplicate detection based on title + lyrics hash

---

## Personal Data Sync

Portable bundle export/import for syncing data across machines via cloud storage (Dropbox, Google Drive, etc.).

### Bundle Contents
- Lore entries (title, content, category, active status)
- Genres (name, prompt template, description, BPM range)
- Lore presets (with lore titles resolved for portability — not raw IDs)
- Artists (name, legal name, bio)
- Non-sensitive config keys (ai_model, submission_mode, browser_path, download_dir, max_prompt_length, use_xvfb)
- Excludes API keys, passwords, and credentials

### Sync Features
- **Export Now** — Manual export to sync folder as `songfactory_personal.json`
- **Import Now** — Manual import from sync folder bundle
- **Auto-export on data changes** — Debounced (2-second) auto-export triggered by lore/genre changes
- **Auto-import on startup** — Checks bundle timestamp vs. last import; imports only if newer
- **Lore-only mode** — Export/import just lore entries (available in Lore Editor sidebar)

### Portability
- Uses names/titles as unique keys (not database IDs)
- Upsert semantics: creates new entries or updates existing ones by name
- Preset lore references stored as titles, resolved back to IDs on import

---

## Settings

### API Settings
- Anthropic API key with show/hide toggle and connection test
- AI model selection (Claude Sonnet / Opus)
- Segmind API key with show/hide toggle and connection test (for AI cover art generation)

### Song Submission
- Submission mode: Browser Automation or MusicGPT API (Direct)
- MusicGPT API key with test button

### Lalals.com Settings
- Username (for profile scraping)
- Email and password (for browser automation login)
- Browser executable path

### General
- Download directory (default: ~/Music/SongFactory)
- Max prompt length

### DistroKid (Distribution)
- DistroKid email and password
- Default artist name (must match registered DistroKid artist)
- Default songwriter legal name (required for all releases)

### Personal Data Sync
- Sync folder path (Dropbox, Google Drive, or any directory)
- Export Now / Import Now buttons
- Auto-export on data changes (lore, genres — debounced 2 seconds)
- Auto-import on startup (compares bundle timestamp)
- Sync status label showing last export/import times

### Automation
- Xvfb virtual display toggle for headless browser operation

### Diagnostics
- **Pipeline Diagnostic** — 5-phase test of the lalals.com browser pipeline: Browser Launch + Login, Form Elements, Form Fill, API Submit (opt-in, uses 1 credit), Download URLs. Per-phase pass/fail with StatusBadge indicators and full HTML report.
- **Open Screenshots Folder** — Quick access to `~/.songfactory/screenshots/` (max 20, auto-rotated)
- **Selector Health Checks** — Validates that lalals.com CSS selectors (prompt textarea, lyrics toggle, generate button, home page cards) still match the live site
- Network sniffer (60-second browser traffic capture)
- Log viewers for sniffer and automation logs

### Error Categories
Automation errors are categorized for actionable user messages:
| Category | Description |
|----------|-------------|
| SELECTOR_NOT_FOUND | UI selectors no longer match the site |
| SESSION_EXPIRED | Login session has expired |
| API_TIMEOUT | Server too slow to respond |
| DOWNLOAD_FAILED | Generated files could not be downloaded |
| NETWORK_ERROR | Connection lost during processing |

### Backup & Restore
- **Backup Now** — Creates a timestamped copy of the database in the download directory using SQLite's online backup API (safe while the app is running)
- **Restore from Backup** — Lists available backups (newest first with date and size), or browse for a `.db` file manually. Creates a safety copy (`songfactory_pre_restore.db`) before overwriting.
- **Startup Detection** — On fresh install (no user-created songs), automatically scans the download directory for backups and offers to restore the newest one. This allows backups stored alongside music files to travel to a new machine.

---

## Cross-Platform Support

Song Factory runs on Linux, macOS, and Windows with platform-aware behavior.

### Platform Detection (`platform_utils.py`)
- `is_linux()`, `is_macos()`, `is_windows()` — Platform detection
- `is_frozen()` — PyInstaller frozen bundle detection
- `get_resource_dir()` — Returns `sys._MEIPASS` when frozen, source dir otherwise
- `get_font_search_paths()` — OS-specific font paths for CD art generation
- `supports_xvfb()` — True only on Linux

### Platform-Specific Behavior
- **Xvfb** — Virtual display manager auto-skips on non-Linux; checkbox hidden in Settings
- **CD art fonts** — Finds Liberation/DejaVu on Linux, Helvetica/Arial on macOS, Arial/Calibri/Segoe on Windows
- **ISO export** — Uses pycdlib (pure Python) instead of platform-specific CD burning tools
- **Frozen app support** — `main.py` and `data_session_builder.py` handle PyInstaller paths

### PyInstaller Packaging
- `songfactory.spec` — Build configuration with platform-specific icons
- `scripts/build_linux.sh` — Linux build with optional AppImage
- `scripts/build_macos.sh` — macOS build with .app bundle and .dmg
- `scripts/build_windows.bat` — Windows build
- `scripts/convert_icons.py` — Generates .ico (Windows) and .icns (macOS) from SVG
- `pyproject.toml` — Enables `pip install -e .` with `songfactory` entry point
- See [BUILD.md](BUILD.md) for full build instructions

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
- Scroll area (350px max height) accommodates the grouped layout

### Output Panel
- **Generated Prompt** — Editable prompt field with character counter (300 char target for lalals.com)
- **Generated Lyrics** — Editable lyrics with verse/chorus/bridge structure markers
- **Actions** — Save to Database, Queue for Lalals, Copy Prompt, Copy Lyrics

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
- Status filter dropdown (draft, queued, processing, submitted, completed, error, imported)

### Song Table
- Colored status badges per song
- Expandable detail area for viewing/editing individual songs

### Automation Queue
- **Browser Mode** — Playwright-based browser automation: submit songs to lalals.com, wait for processing, download results
- **API Mode** — Direct submission via MusicGPT API with automatic polling and download
- **Sync** — Import song details (prompt, lyrics, metadata) from lalals.com profile API
- **History Import** — Discover and import previously generated songs from lalals.com account
- Xvfb support for headless browser automation

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

Create audio CD projects with full CD-TEXT metadata and CD-Extra data sessions.

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

### Burning
- Audio conversion to WAV via ffmpeg
- TOC file generation for cdrdao
- CD-Extra data session building via wodim
- Progress tracking during burn

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
- **Cover Art** — File picker with preview, validation (min 1000x1000, square, JPG/PNG), auto-resize to 3000x3000
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

## Settings

### API Settings
- Anthropic API key with show/hide toggle and connection test
- AI model selection (Claude Sonnet / Opus)

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

### Automation
- Xvfb virtual display toggle for headless browser operation

### Diagnostics
- Network sniffer (60-second browser traffic capture)
- Log viewers for sniffer and automation logs

### Backup & Restore
- **Backup Now** — Creates a timestamped copy of the database in the download directory using SQLite's online backup API (safe while the app is running)
- **Restore from Backup** — Lists available backups (newest first with date and size), or browse for a `.db` file manually. Creates a safety copy (`songfactory_pre_restore.db`) before overwriting.
- **Startup Detection** — On fresh install (no user-created songs), automatically scans the download directory for backups and offers to restore the newest one. This allows backups stored alongside music files to travel to a new machine.

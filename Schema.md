# Song Factory — Database Schema

Database: `~/.songfactory/songfactory.db` (SQLite, WAL journal mode, foreign keys ON)

---

## lore

Lore entries used as world-building context for AI song generation.

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | PK AUTOINCREMENT | Unique identifier |
| title | TEXT | NOT NULL | Entry title |
| content | TEXT | NOT NULL | Full lore content (markdown) |
| category | TEXT | 'general' | Category: people, places, events, themes, rules, general |
| active | BOOLEAN | 1 | Whether included in generation context |
| created_at | TIMESTAMP | CURRENT_TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | CURRENT_TIMESTAMP | Last modification time |

---

## lore_presets

Saved lore selection presets for quick bulk activation.

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | PK AUTOINCREMENT | Unique identifier |
| name | TEXT | NOT NULL UNIQUE | Preset display name |
| lore_ids | TEXT | NOT NULL | JSON array of lore entry IDs, e.g. `[1, 3, 7, 12]` |
| created_at | TIMESTAMP | CURRENT_TIMESTAMP | Creation time |

---

## genres

Genre definitions with prompt templates for AI song generation.

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | PK AUTOINCREMENT | Unique identifier |
| name | TEXT | NOT NULL UNIQUE | Genre name |
| prompt_template | TEXT | NOT NULL | Template for the lalals.com prompt field |
| description | TEXT | NULL | Genre description |
| bpm_range | TEXT | NULL | Typical BPM range (e.g. "120-140") |
| active | BOOLEAN | 1 | Whether available for selection |
| created_at | TIMESTAMP | CURRENT_TIMESTAMP | Creation time |

---

## songs

Generated and imported songs with full metadata.

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | PK AUTOINCREMENT | Unique identifier |
| title | TEXT | NOT NULL | Song title |
| genre_id | INTEGER | FK → genres(id) | Associated genre |
| genre_label | TEXT | NULL | Display label (e.g. "COUNTRY (Americana)") |
| prompt | TEXT | NOT NULL | The ≤300 char prompt for lalals.com |
| lyrics | TEXT | NOT NULL | Full lyrics with structure markers |
| user_input | TEXT | NULL | Original user creative prompt |
| lore_snapshot | TEXT | NULL | JSON snapshot of lore used during generation |
| status | TEXT | 'draft' | Song status (draft/queued/processing/submitted/completed/error/imported) |
| file_path_1 | TEXT | NULL | Path to downloaded audio file (version 1) |
| file_path_2 | TEXT | NULL | Path to downloaded audio file (version 2) |
| notes | TEXT | NULL | User notes |
| created_at | TIMESTAMP | CURRENT_TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | CURRENT_TIMESTAMP | Last modification time |

### Metadata columns (added via migration)

| Column | Type | Description |
|--------|------|-------------|
| task_id | TEXT | Lalals.com task/project ID |
| conversion_id_1 | TEXT | Conversion ID for version 1 |
| conversion_id_2 | TEXT | Conversion ID for version 2 |
| audio_url_1 | TEXT | Direct audio URL for version 1 |
| audio_url_2 | TEXT | Direct audio URL for version 2 |
| music_style | TEXT | Music style descriptor |
| duration_seconds | REAL | Song duration in seconds |
| file_format | TEXT | Audio file format |
| file_size_1 | INTEGER | File size in bytes (version 1) |
| file_size_2 | INTEGER | File size in bytes (version 2) |
| voice_used | TEXT | AI voice model used |
| lalals_created_at | TEXT | Creation timestamp from lalals.com |
| lyrics_timestamped | TEXT | Timestamped lyrics from lalals.com |
| file_path_vocals | TEXT | Path to isolated vocals track |
| file_path_instrumental | TEXT | Path to isolated instrumental track |

---

## config

Key-value store for application settings.

| Column | Type | Description |
|--------|------|-------------|
| key | TEXT | PK — Setting name |
| value | TEXT | Setting value |

### Known keys

| Key | Description |
|-----|-------------|
| api_key | Anthropic API key |
| ai_model | Default AI model name |
| musicgpt_api_key | MusicGPT API key |
| submission_mode | "browser" or "api" |
| lalals_username | Lalals.com profile username |
| lalals_email | Lalals.com login email |
| lalals_password | Lalals.com login password |
| browser_path | Path to browser executable |
| download_dir | Download directory path |
| max_prompt_length | Max prompt character count |
| use_xvfb | "true" or "false" |
| dk_email | DistroKid login email |
| dk_password | DistroKid login password |
| dk_artist | Default DistroKid artist name |
| dk_songwriter | Default songwriter legal name |

---

## distributions

Distribution records for uploading songs to streaming platforms via DistroKid.

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | PK AUTOINCREMENT | Unique identifier |
| song_id | INTEGER | FK → songs(id) NOT NULL | Associated song |
| distributor | TEXT | 'distrokid' | Distribution service name |
| release_type | TEXT | 'single' | Release type (single/album) |
| artist_name | TEXT | 'Yakima Finds' | Artist name for release |
| album_title | TEXT | NULL | Release/album title |
| songwriter | TEXT | NOT NULL | Songwriter legal name |
| language | TEXT | 'English' | Release language |
| primary_genre | TEXT | NULL | Song Factory genre name (mapped to DK genre) |
| cover_art_path | TEXT | NULL | Path to cover art file |
| is_instrumental | BOOLEAN | 0 | Whether track is instrumental |
| lyrics_submitted | TEXT | NULL | Plain text lyrics submitted with release |
| release_date | TEXT | NULL | Release date (YYYY-MM-DD) |
| record_label | TEXT | NULL | Record label name (Musician Plus+ only) |
| ai_disclosure | BOOLEAN | 1 | AI-generated content disclosure |
| distrokid_url | TEXT | NULL | DistroKid release URL after upload |
| status | TEXT | 'draft' | Distribution status |
| error_message | TEXT | NULL | Error description on failure |
| notes | TEXT | NULL | User notes |
| created_at | TIMESTAMP | CURRENT_TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | CURRENT_TIMESTAMP | Last modification time |

### Status flow

`draft` → `ready` → `uploading` → `submitted` → `live` / `error`

---

## cd_projects

CD mastering projects.

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | PK AUTOINCREMENT | Unique identifier |
| name | TEXT | NOT NULL | Project name |
| artist | TEXT | 'Yakima Finds' | Artist name for CD-TEXT |
| album_title | TEXT | '' | Album title for CD-TEXT |
| songwriter | TEXT | '' | Songwriter for CD-TEXT |
| message | TEXT | '' | CD-TEXT message |
| total_duration | REAL | 0 | Total duration in seconds |
| status | TEXT | 'draft' | Project status |
| include_data | BOOLEAN | 1 | Include data session (CD-Extra) |
| include_source | BOOLEAN | 1 | Include source files in data session |
| include_lyrics | BOOLEAN | 1 | Include lyrics in data session |
| include_mp3 | BOOLEAN | 1 | Include MP3 files in data session |
| disc_art_path | TEXT | NULL | Path to disc art image |
| cover_art_path | TEXT | NULL | Path to cover art image |
| back_art_path | TEXT | NULL | Path to back cover art image |
| created_at | TIMESTAMP | CURRENT_TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | CURRENT_TIMESTAMP | Last modification time |

---

## cd_tracks

Individual tracks within a CD project.

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | PK AUTOINCREMENT | Unique identifier |
| project_id | INTEGER | FK → cd_projects(id) CASCADE | Parent CD project |
| song_id | INTEGER | FK → songs(id) | Associated song (optional) |
| track_number | INTEGER | NOT NULL | Track position on disc |
| title | TEXT | NOT NULL | Track title for CD-TEXT |
| performer | TEXT | 'Yakima Finds' | Performer for CD-TEXT |
| songwriter | TEXT | '' | Songwriter for CD-TEXT |
| source_path | TEXT | NOT NULL | Path to source audio file |
| wav_path | TEXT | NULL | Path to converted WAV file |
| duration_seconds | REAL | 0 | Track duration in seconds |
| pregap_seconds | REAL | 2.0 | Pregap before track (seconds) |
| created_at | TIMESTAMP | CURRENT_TIMESTAMP | Creation time |

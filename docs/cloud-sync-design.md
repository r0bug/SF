# Cloud Sync Architecture Design

**Status:** Design only (no implementation)
**Date:** 2026-02-10
**Author:** Song Factory Engineering

---

## 1. Overview

This document outlines the architecture for syncing Song Factory data between
multiple machines. The goal is to enable a user to work on songs from different
computers while keeping the SQLite database and audio files consistent.

## 2. Sync Model

### 2.1 Change Tracking

All Song Factory tables already include `created_at` and `updated_at` timestamp
columns. The sync mechanism leverages these for incremental sync:

```
last_sync_at  = timestamp of last successful sync
changed_rows  = SELECT * FROM <table> WHERE updated_at > last_sync_at
```

A new `sync_metadata` table tracks sync state:

```sql
CREATE TABLE sync_metadata (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Keys: last_sync_at, device_id, sync_provider
```

### 2.2 Data Export Format

Each sync cycle produces a JSON change log:

```json
{
  "device_id": "uuid-of-this-machine",
  "sync_version": 1,
  "timestamp": "2026-02-10T12:00:00Z",
  "changes": {
    "songs": [{"op": "upsert", "id": 42, "data": {...}}],
    "lore":  [{"op": "upsert", "id": 7, "data": {...}}],
    "genres": [{"op": "delete", "id": 3}],
    "artists": [],
    "distributions": [],
    "cd_projects": [],
    "cd_tracks": [],
    "config": [{"key": "ai_model", "value": "claude-sonnet-4-5-20250929"}]
  }
}
```

Sensitive config keys (from `SENSITIVE_KEYS`) are excluded from sync.

### 2.3 Audio File Sync

Audio files are referenced by path in the database (`file_path_1`, `file_path_2`,
`source_path`, `wav_path`, `cover_art_path`). For sync:

1. Hash each audio file (SHA-256) and store in a new `file_hash` column
2. Upload files to cloud storage keyed by hash (deduplication)
3. On the receiving device, download missing files by hash
4. Update local paths to match the receiving device's download directory

File manifest format:

```json
{
  "files": [
    {"hash": "abc123...", "size": 4521678, "original_name": "song_v1.mp3"}
  ]
}
```

## 3. Cloud Storage Backends

The sync layer should be provider-agnostic. Supported backends:

| Provider | Mechanism | Auth |
|----------|-----------|------|
| Google Drive | PyDrive2 API | OAuth2 |
| Dropbox | Dropbox SDK | OAuth2 |
| S3-compatible | boto3 | Access key |
| Local folder | shutil/rsync | N/A (LAN sync) |

### 3.1 Storage Interface

```python
class SyncStorage(ABC):
    """Abstract interface for cloud storage backends."""

    @abstractmethod
    def upload(self, local_path: str, remote_key: str) -> str:
        """Upload a file. Returns the remote URL/key."""

    @abstractmethod
    def download(self, remote_key: str, local_path: str) -> bool:
        """Download a file. Returns True on success."""

    @abstractmethod
    def list_keys(self, prefix: str = "") -> list[str]:
        """List remote keys with optional prefix filter."""

    @abstractmethod
    def delete(self, remote_key: str) -> bool:
        """Delete a remote file."""
```

## 4. Conflict Resolution

**Strategy: Last-Write-Wins (LWW) with field-level merge.**

When the same record is modified on two devices:

1. Compare `updated_at` timestamps
2. For each field, take the value from the most recently updated device
3. Exception: `status` field uses a priority ordering:
   `draft < queued < processing < submitted < completed`
   (higher status always wins regardless of timestamp)

### 4.1 Deletion Handling

- Soft delete: add a `deleted_at` column (future migration)
- Deleted records sync as `{"op": "delete", "id": N}`
- A delete always wins over an older edit, but loses to a newer edit

### 4.2 Conflict Log

All conflicts are logged to `~/.songfactory/logs/sync_conflicts.log` with
both versions so the user can manually resolve if needed.

## 5. Sync Workflow

```
1. User clicks "Sync Now" in Settings
2. Generate change log since last_sync_at
3. Upload change log JSON to cloud storage
4. Upload any new/modified audio files (by hash)
5. Download remote change logs from other devices
6. Apply remote changes with conflict resolution
7. Download missing audio files
8. Update last_sync_at
9. Show summary: "Synced: 5 songs updated, 2 new, 1 conflict"
```

## 6. Security Considerations

- Sensitive keys (`api_key`, passwords) are NEVER synced
- Change logs and audio files can optionally be encrypted at rest
  (AES-256-GCM with a user-provided passphrase)
- OAuth tokens for cloud providers stored in system keyring (via `secure_config`)

## 7. Prerequisites (Already Done)

- All tables have `updated_at` columns
- Schema versioning via `PRAGMA user_version`
- `secure_config` module for credential management
- `atomic_io` module for safe file writes

## 8. Future Implementation Notes

- Add `device_id` generation on first launch (UUID4, stored in config)
- Add `file_hash` column to songs table via migration
- Background sync worker (QThread) with progress signals
- Settings UI: sync provider dropdown, sync interval, manual sync button
- Automatic sync on app launch and close (configurable)

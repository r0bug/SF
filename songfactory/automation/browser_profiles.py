"""Centralized browser profile management for Song Factory.

All browser automation modules should use get_profile_path() to get
the storage directory for their browser profile.  This ensures a
consistent location, provides cache-clearing utilities, and handles
corruption recovery.
"""

import logging
import os
import shutil

logger = logging.getLogger("songfactory.automation.browser_profiles")

PROFILES_DIR = os.path.join(os.path.expanduser("~"), ".songfactory", "profiles")

# Legacy paths (pre-centralization) — used for migration
_LEGACY_PATHS = {
    "lalals": os.path.join(os.path.expanduser("~"), ".songfactory", "browser_profile"),
    "distrokid": os.path.join(os.path.expanduser("~"), ".songfactory", "dk_browser_profile"),
}


def get_profile_path(service: str) -> str:
    """Return the profile directory for *service*, creating it if needed.

    Migrates legacy profile paths to the new centralized location on
    first call.

    Args:
        service: Service identifier (e.g. "lalals", "distrokid").

    Returns:
        Absolute path to the profile directory.
    """
    path = os.path.join(PROFILES_DIR, service)

    # Migrate legacy path if it exists and the new one doesn't
    legacy = _LEGACY_PATHS.get(service)
    if legacy and os.path.isdir(legacy) and not os.path.isdir(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            shutil.move(legacy, path)
            logger.info("Migrated legacy profile %s -> %s", legacy, path)
        except OSError as e:
            logger.warning("Could not migrate legacy profile: %s", e)
            # Fall back to legacy path
            return legacy

    os.makedirs(path, exist_ok=True)
    return path


def clear_cache(service: str) -> bool:
    """Delete browser cache for *service* while preserving cookies/storage.

    Returns:
        True if cache was found and removed.
    """
    profile = get_profile_path(service)
    cache_dirs = [
        os.path.join(profile, "Default", "Cache"),
        os.path.join(profile, "Default", "Code Cache"),
        os.path.join(profile, "Default", "GPUCache"),
    ]
    removed = False
    for cache_dir in cache_dirs:
        if os.path.isdir(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                logger.info("Cleared cache: %s", cache_dir)
                removed = True
            except OSError as e:
                logger.warning("Failed to clear cache %s: %s", cache_dir, e)
    return removed


def clear_profile(service: str) -> bool:
    """Delete the entire profile for *service*.

    Returns:
        True if the profile directory was found and removed.
    """
    path = os.path.join(PROFILES_DIR, service)
    if os.path.isdir(path):
        try:
            shutil.rmtree(path)
            logger.info("Cleared profile: %s", path)
            return True
        except OSError as e:
            logger.warning("Failed to clear profile %s: %s", path, e)
    return False


def clear_all_profiles() -> bool:
    """Delete ALL browser profiles (nuclear option).

    Returns:
        True if profiles directory was found and removed.
    """
    if os.path.isdir(PROFILES_DIR):
        try:
            shutil.rmtree(PROFILES_DIR)
            logger.info("Cleared all browser profiles")
            return True
        except OSError as e:
            logger.warning("Failed to clear all profiles: %s", e)
    return False


def get_profile_size(service: str) -> int:
    """Return total size in bytes of a service's profile directory."""
    path = os.path.join(PROFILES_DIR, service)
    if not os.path.isdir(path):
        return 0
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def list_profiles() -> list[dict]:
    """Return info about all known profiles.

    Returns:
        List of dicts with keys: service, path, size_bytes, exists.
    """
    result = []
    if not os.path.isdir(PROFILES_DIR):
        return result
    for entry in sorted(os.listdir(PROFILES_DIR)):
        full = os.path.join(PROFILES_DIR, entry)
        if os.path.isdir(full):
            result.append({
                "service": entry,
                "path": full,
                "size_bytes": get_profile_size(entry),
                "exists": True,
            })
    return result

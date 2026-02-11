"""
Song Factory - Secure Credential Storage

Stores sensitive credentials in the system keyring when available,
with a fallback to the SQLite config table on systems without a keyring.
"""

import logging

logger = logging.getLogger("songfactory.security")

SERVICE_NAME = "SongFactory"
SENSITIVE_KEYS = {"api_key", "musicgpt_api_key", "lalals_password", "dk_password"}

try:
    import keyring as _keyring
    _HAS_KEYRING = True
except ImportError:
    _keyring = None
    _HAS_KEYRING = False


def has_keyring() -> bool:
    """Return True if system keyring is available."""
    if not _HAS_KEYRING:
        return False
    try:
        _keyring.get_password(SERVICE_NAME, "__test__")
        return True
    except Exception:
        return False


def get_secret(key: str, fallback_db=None) -> str | None:
    """Retrieve a secret, trying keyring first then database.

    Args:
        key: One of the SENSITIVE_KEYS.
        fallback_db: Optional Database instance for fallback lookup.

    Returns:
        The credential value, or None if not found.
    """
    if _HAS_KEYRING:
        try:
            value = _keyring.get_password(SERVICE_NAME, key)
            if value:
                return value
        except Exception as e:
            logger.debug("Keyring read failed for %s: %s", key, e)

    if fallback_db is not None:
        value = fallback_db.get_config(key)
        if value and value != "***":
            return value

    return None


def set_secret(key: str, value: str, fallback_db=None) -> None:
    """Store a secret in the keyring, falling back to the database.

    When keyring is available, the database value is replaced with ``***``
    to indicate that the real value lives in the keyring.

    Args:
        key: One of the SENSITIVE_KEYS.
        value: The credential to store.
        fallback_db: Optional Database instance for fallback storage.
    """
    if _HAS_KEYRING:
        try:
            _keyring.set_password(SERVICE_NAME, key, value)
            # Mark in DB that the credential is in the keyring
            if fallback_db is not None:
                fallback_db.set_config(key, "***")
            logger.info("Stored %s in system keyring", key)
            return
        except Exception as e:
            logger.warning("Keyring write failed for %s: %s, using DB fallback", key, e)

    # Fallback: store in DB (plaintext)
    if fallback_db is not None:
        fallback_db.set_config(key, value)
        logger.info("Stored %s in database (no keyring available)", key)


def delete_secret(key: str, fallback_db=None) -> None:
    """Remove a secret from keyring and database."""
    if _HAS_KEYRING:
        try:
            _keyring.delete_password(SERVICE_NAME, key)
        except Exception:
            pass

    if fallback_db is not None:
        fallback_db.set_config(key, "")


def migrate_to_keyring(db) -> int:
    """Migrate plaintext credentials from the database to the keyring.

    Returns the number of credentials migrated.
    """
    if not _HAS_KEYRING:
        return 0

    migrated = 0
    for key in SENSITIVE_KEYS:
        value = db.get_config(key)
        if value and value != "***":
            try:
                _keyring.set_password(SERVICE_NAME, key, value)
                db.set_config(key, "***")
                migrated += 1
                logger.info("Migrated %s to system keyring", key)
            except Exception as e:
                logger.warning("Failed to migrate %s: %s", key, e)

    return migrated

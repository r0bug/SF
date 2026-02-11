"""Tests for secure credential storage."""

from secure_config import get_secret, set_secret, delete_secret, SENSITIVE_KEYS


def test_sensitive_keys_defined():
    assert "api_key" in SENSITIVE_KEYS
    assert "lalals_password" in SENSITIVE_KEYS
    assert "dk_password" in SENSITIVE_KEYS


def test_fallback_to_db(temp_db):
    """Without keyring, should fall back to database."""
    temp_db.set_config("api_key", "test-key-123")
    value = get_secret("api_key", fallback_db=temp_db)
    assert value == "test-key-123"


def test_set_and_get_without_keyring(temp_db):
    """set_secret + get_secret round-trip via DB fallback."""
    set_secret("api_key", "my-secret", fallback_db=temp_db)
    value = get_secret("api_key", fallback_db=temp_db)
    assert value == "my-secret"


def test_delete_secret(temp_db):
    set_secret("api_key", "to-delete", fallback_db=temp_db)
    delete_secret("api_key", fallback_db=temp_db)
    value = get_secret("api_key", fallback_db=temp_db)
    # Should be empty or None after delete
    assert not value


def test_masked_value_not_returned(temp_db):
    """If DB contains '***' (keyring marker), get_secret should return None."""
    temp_db.set_config("api_key", "***")
    value = get_secret("api_key", fallback_db=temp_db)
    assert value is None

"""
Song Factory - Configuration-Driven Timeouts

Centralized timeout defaults with database override support.
Usage: ``get_timeout(db, "login_wait_s")`` returns the configured or default value.
"""


# Default timeouts — keys describe the operation and unit
TIMEOUTS = {
    "login_wait_s": 300,          # Wait for user to login (lalals)
    "dk_login_wait_s": 600,       # Wait for user to login (DistroKid)
    "generation_poll_s": 600,     # Max time to poll for generation result
    "element_visible_ms": 5000,   # Default element visibility timeout
    "page_load_ms": 15000,        # Page navigation timeout
    "api_request_s": 30,          # HTTP API request timeout
    "ffmpeg_convert_s": 300,      # Audio format conversion
    "download_s": 120,            # File download timeout
    "xvfb_startup_s": 2,          # Xvfb virtual display startup
    "poll_interval_s": 10,        # Default polling interval
    "search_debounce_ms": 300,    # UI search debounce timer
    "api_capture_s": 30,          # Max wait for API task_id after submit
    "post_refresh_delay_s": 5,    # Delay after refresh before downloading
}


def get_timeout(db, key: str) -> int | float:
    """Get a timeout value, checking the config table first.

    Args:
        db: Database instance (or None for defaults only).
        key: Timeout key from TIMEOUTS dict.

    Returns:
        The configured timeout value, or the default from TIMEOUTS.

    Raises:
        KeyError: If key is not in TIMEOUTS.
    """
    if key not in TIMEOUTS:
        raise KeyError(f"Unknown timeout key: {key!r}")
    if db is not None:
        override = db.get_config(f"timeout_{key}")
        if override is not None:
            try:
                return type(TIMEOUTS[key])(override)
            except (ValueError, TypeError):
                pass
    return TIMEOUTS[key]

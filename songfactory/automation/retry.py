"""
Song Factory - Retry & Backoff Utility

Provides a ``with_retry`` decorator for network-facing operations.
Retries with exponential backoff on transient errors.
"""

import time
import logging
import functools

logger = logging.getLogger("songfactory.automation")

# HTTP status codes that should NOT be retried
_NON_RETRYABLE_STATUS = {401, 403, 404, 405, 422}


def with_retry(
    max_attempts: int = 3,
    backoff_base: float = 2,
    retryable_exceptions: tuple = (Exception,),
    stop_check=None,
):
    """Decorator that retries a function on transient failures.

    Args:
        max_attempts: Maximum number of attempts (including the first).
        backoff_base: Base for exponential backoff (seconds).
        retryable_exceptions: Tuple of exception types to retry on.
        stop_check: Optional callable returning True if we should abort
                     (e.g., a worker's _should_stop method).
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retryable_exceptions as e:
                    # Don't retry non-retryable HTTP errors
                    if hasattr(e, "code") and e.code in _NON_RETRYABLE_STATUS:
                        raise

                    if attempt == max_attempts:
                        raise

                    if stop_check and stop_check():
                        raise

                    wait = backoff_base ** attempt
                    logger.warning(
                        "Retry %d/%d for %s: %s (wait %.1fs)",
                        attempt,
                        max_attempts,
                        fn.__name__,
                        e,
                        wait,
                    )
                    time.sleep(wait)

        return wrapper

    return decorator


def retry_call(
    fn,
    args=(),
    kwargs=None,
    max_attempts: int = 3,
    backoff_base: float = 2,
    retryable_exceptions: tuple = (Exception,),
    stop_check=None,
):
    """Functional form of retry — call ``fn(*args, **kwargs)`` with retries.

    Useful when you can't use the decorator (e.g., lambda, method reference).
    """
    if kwargs is None:
        kwargs = {}

    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except retryable_exceptions as e:
            if hasattr(e, "code") and e.code in _NON_RETRYABLE_STATUS:
                raise

            if attempt == max_attempts:
                raise

            if stop_check and stop_check():
                raise

            wait = backoff_base ** attempt
            logger.warning(
                "Retry %d/%d: %s (wait %.1fs)",
                attempt,
                max_attempts,
                e,
                wait,
            )
            time.sleep(wait)

"""Tests for the retry decorator."""

import pytest
from automation.retry import with_retry, retry_call


class TestWithRetry:
    def test_succeeds_first_try(self):
        call_count = 0

        @with_retry(max_attempts=3, backoff_base=0.01)
        def good_fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert good_fn() == "ok"
        assert call_count == 1

    def test_retries_on_failure(self):
        call_count = 0

        @with_retry(max_attempts=3, backoff_base=0.01)
        def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "ok"

        assert flaky_fn() == "ok"
        assert call_count == 3

    def test_raises_after_max_attempts(self):
        @with_retry(max_attempts=2, backoff_base=0.01)
        def always_fails():
            raise ValueError("permanent")

        with pytest.raises(ValueError):
            always_fails()

    def test_stop_check_aborts_retry(self):
        @with_retry(max_attempts=5, backoff_base=0.01, stop_check=lambda: True)
        def fails():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            fails()


class TestRetryCall:
    def test_basic_retry(self):
        count = 0

        def flaky():
            nonlocal count
            count += 1
            if count < 2:
                raise IOError("transient")
            return "done"

        result = retry_call(flaky, max_attempts=3, backoff_base=0.01)
        assert result == "done"
        assert count == 2

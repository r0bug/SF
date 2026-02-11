"""Tests for atomic file operations."""

import os
import pytest
from automation.atomic_io import atomic_write_binary, atomic_write_text, atomic_write_fn


def test_atomic_write_binary(tmp_path):
    target = str(tmp_path / "out.bin")
    data = b"hello world"
    atomic_write_binary(target, data)
    assert os.path.exists(target)
    with open(target, "rb") as f:
        assert f.read() == data


def test_atomic_write_text(tmp_path):
    target = str(tmp_path / "out.txt")
    atomic_write_text(target, "hello")
    with open(target) as f:
        assert f.read() == "hello"


def test_atomic_write_fn(tmp_path):
    target = str(tmp_path / "out.dat")

    def write_callback(tmp):
        with open(tmp, "w") as f:
            f.write("data")

    atomic_write_fn(target, write_callback)
    with open(target) as f:
        assert f.read() == "data"


def test_atomic_write_fn_creates_parent_dirs(tmp_path):
    target = str(tmp_path / "sub" / "dir" / "out.txt")
    atomic_write_text(target, "nested")
    assert os.path.isfile(target)


def test_atomic_write_fn_cleans_up_on_error(tmp_path):
    target = str(tmp_path / "fail.txt")

    def bad_writer(tmp):
        raise RuntimeError("intentional failure")

    with pytest.raises(RuntimeError):
        atomic_write_fn(target, bad_writer)

    assert not os.path.exists(target)
    # Also verify no .tmp files left behind
    assert not any(f.endswith(".tmp") for f in os.listdir(tmp_path))


def test_atomic_write_no_partial_file(tmp_path):
    """If we interrupt mid-write, the target should not exist."""
    target = str(tmp_path / "partial.bin")

    def partial_writer(tmp):
        with open(tmp, "wb") as f:
            f.write(b"partial")
            raise IOError("disk full simulation")

    with pytest.raises(IOError):
        atomic_write_fn(target, partial_writer)

    assert not os.path.exists(target)

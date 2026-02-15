"""
Song Factory - Platform Utilities

Centralized platform detection for cross-platform support.
All platform-conditional code should import from this module.
"""

import os
import sys


def is_linux() -> bool:
    """Check if running on Linux."""
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    """Check if running on macOS."""
    return sys.platform == "darwin"


def is_windows() -> bool:
    """Check if running on Windows."""
    return sys.platform == "win32"


def platform_name() -> str:
    """Return a normalized platform name string."""
    if is_linux():
        return "linux"
    if is_macos():
        return "macos"
    if is_windows():
        return "windows"
    return sys.platform


def is_frozen() -> bool:
    """Check if running as a PyInstaller frozen bundle."""
    return getattr(sys, 'frozen', False)


def get_bundle_dir() -> str:
    """Return the directory containing the executable (frozen) or the source dir."""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_dir() -> str:
    """Return the resource directory (sys._MEIPASS if frozen, else source dir)."""
    if is_frozen():
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_font_search_paths() -> list[str]:
    """Return OS-specific font search paths for CD art generation."""
    if is_linux():
        return [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    if is_macos():
        return [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
    if is_windows():
        windir = os.environ.get("WINDIR", r"C:\Windows")
        return [
            os.path.join(windir, "Fonts", "arial.ttf"),
            os.path.join(windir, "Fonts", "arialbd.ttf"),
            os.path.join(windir, "Fonts", "calibri.ttf"),
            os.path.join(windir, "Fonts", "segoeui.ttf"),
        ]
    return []


def supports_xvfb() -> bool:
    """Check if Xvfb virtual display is supported (Linux only)."""
    return is_linux()

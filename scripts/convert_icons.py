#!/usr/bin/env python3
"""Convert icon.svg to platform-specific icon formats.

Generates:
  - songfactory/icon.ico  (Windows, multi-resolution)
  - songfactory/icon.icns (macOS, via iconutil or Pillow)

Requires: Pillow (and optionally cairosvg for SVG→PNG conversion).
If cairosvg is not available, expects a songfactory/icon.png to exist.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

# Resolve paths relative to this script
REPO_ROOT = Path(__file__).resolve().parent.parent
SONGFACTORY_DIR = REPO_ROOT / "songfactory"
SVG_PATH = SONGFACTORY_DIR / "icon.svg"
ICO_PATH = SONGFACTORY_DIR / "icon.ico"
ICNS_PATH = SONGFACTORY_DIR / "icon.icns"
PNG_PATH = SONGFACTORY_DIR / "icon.png"

# ICO resolutions (Windows)
ICO_SIZES = [16, 32, 48, 64, 128, 256]

# ICNS resolutions (macOS)
ICNS_SIZES = [16, 32, 64, 128, 256, 512, 1024]


def svg_to_png(svg_path: Path, png_path: Path, size: int) -> bool:
    """Render SVG to PNG at the given size. Returns True on success."""
    try:
        import cairosvg
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(png_path),
            output_width=size,
            output_height=size,
        )
        return True
    except ImportError:
        pass

    # Fallback: try rsvg-convert
    try:
        subprocess.run(
            ["rsvg-convert", "-w", str(size), "-h", str(size),
             str(svg_path), "-o", str(png_path)],
            check=True, capture_output=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return False


def load_base_png(size: int) -> "Image.Image":
    """Load or render a PNG at the requested size."""
    from PIL import Image

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    if SVG_PATH.exists() and svg_to_png(SVG_PATH, tmp_path, size):
        img = Image.open(tmp_path).convert("RGBA")
        tmp_path.unlink(missing_ok=True)
        return img.resize((size, size), Image.Resampling.LANCZOS)

    tmp_path.unlink(missing_ok=True)

    # Fallback: resize from existing PNG
    if PNG_PATH.exists():
        img = Image.open(PNG_PATH).convert("RGBA")
        return img.resize((size, size), Image.Resampling.LANCZOS)

    raise FileNotFoundError(
        f"Cannot create icons: neither cairosvg/rsvg-convert nor {PNG_PATH} available.\n"
        f"Install cairosvg (pip install cairosvg) or place a PNG at {PNG_PATH}."
    )


def create_ico():
    """Create a multi-resolution .ico file for Windows."""
    from PIL import Image

    images = [load_base_png(s) for s in ICO_SIZES]
    images[0].save(
        str(ICO_PATH),
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=images[1:],
    )
    print(f"Created {ICO_PATH} ({', '.join(f'{s}x{s}' for s in ICO_SIZES)})")


def create_icns():
    """Create a .icns file for macOS."""
    # Try macOS iconutil first
    if sys.platform == "darwin":
        try:
            _create_icns_iconutil()
            return
        except Exception:
            pass

    # Fallback: use Pillow (limited support for .icns)
    from PIL import Image

    img = load_base_png(1024)
    img.save(str(ICNS_PATH), format="ICNS")
    print(f"Created {ICNS_PATH} (via Pillow)")


def _create_icns_iconutil():
    """Create .icns using macOS iconutil command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        iconset = Path(tmpdir) / "icon.iconset"
        iconset.mkdir()

        for size in ICNS_SIZES:
            if size > 512:
                continue
            img = load_base_png(size)
            img.save(iconset / f"icon_{size}x{size}.png")

            # @2x versions
            img2x = load_base_png(size * 2)
            img2x.save(iconset / f"icon_{size}x{size}@2x.png")

        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(ICNS_PATH)],
            check=True, capture_output=True,
        )
        print(f"Created {ICNS_PATH} (via iconutil)")


def main():
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("Error: Pillow is required. Install with: pip install Pillow")
        sys.exit(1)

    print("Converting icons...")

    try:
        create_ico()
    except Exception as e:
        print(f"Warning: Could not create .ico: {e}")

    try:
        create_icns()
    except Exception as e:
        print(f"Warning: Could not create .icns: {e}")

    print("Done.")


if __name__ == "__main__":
    main()

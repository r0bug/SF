"""Cover art validation and preparation for DistroKid uploads.

DistroKid requires:
- Format: JPG or PNG
- Minimum: 1000x1000 pixels
- Recommended: 3000x3000 pixels
- Must be square (1:1 aspect ratio)
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger("songfactory.automation")

# Target size for DistroKid uploads
TARGET_SIZE = 3000
MIN_SIZE = 1000
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png"}


def validate_cover_art(path: str) -> dict:
    """Validate a cover art image for DistroKid requirements.

    Args:
        path: Path to the image file.

    Returns:
        dict with keys:
            valid (bool): Whether the image meets all requirements.
            width (int): Image width in pixels.
            height (int): Image height in pixels.
            format (str): File extension.
            errors (list[str]): List of validation error messages.
    """
    result = {"valid": False, "width": 0, "height": 0, "format": "", "errors": []}

    p = Path(path)
    if not p.is_file():
        result["errors"].append(f"File not found: {path}")
        return result

    ext = p.suffix.lower()
    result["format"] = ext
    if ext not in SUPPORTED_FORMATS:
        result["errors"].append(
            f"Unsupported format '{ext}'. Use JPG or PNG."
        )
        return result

    try:
        from PIL import Image

        with Image.open(path) as img:
            w, h = img.size
            result["width"] = w
            result["height"] = h

            if w != h:
                result["errors"].append(
                    f"Image is not square ({w}x{h}). Cover art must be 1:1."
                )
            if w < MIN_SIZE or h < MIN_SIZE:
                result["errors"].append(
                    f"Image too small ({w}x{h}). Minimum is {MIN_SIZE}x{MIN_SIZE}."
                )
    except ImportError:
        result["errors"].append(
            "Pillow (PIL) is not installed. Install with: "
            "pip install Pillow --break-system-packages"
        )
        return result
    except Exception as e:
        result["errors"].append(f"Could not read image: {e}")
        return result

    result["valid"] = len(result["errors"]) == 0
    return result


def prepare_cover_art(source_path: str, output_dir: str = None) -> str:
    """Validate and resize cover art for DistroKid upload.

    If the image is already 3000x3000 JPG/PNG, returns the original path.
    Otherwise, resizes to 3000x3000 and saves as PNG in output_dir.

    Args:
        source_path: Path to the source image.
        output_dir: Directory for the prepared image. If None, uses
                    the same directory as the source.

    Returns:
        Path to the prepared (or original) image file.

    Raises:
        ValueError: If the image fails validation (too small, wrong format).
        ImportError: If Pillow is not installed.
    """
    from PIL import Image

    info = validate_cover_art(source_path)
    if info["errors"]:
        raise ValueError("; ".join(info["errors"]))

    w, h = info["width"], info["height"]

    # Already the right size — use as-is
    if w == TARGET_SIZE and h == TARGET_SIZE:
        logger.info(f"Cover art already {TARGET_SIZE}x{TARGET_SIZE}, no resize needed")
        return source_path

    # Resize needed
    src = Path(source_path)
    if output_dir is None:
        output_dir = str(src.parent)

    out_path = Path(output_dir) / f"{src.stem}_3000x3000.png"

    with Image.open(source_path) as img:
        # Use LANCZOS for high-quality upscaling/downscaling
        resized = img.resize((TARGET_SIZE, TARGET_SIZE), Image.LANCZOS)
        resized.save(str(out_path), "PNG")

    logger.info(f"Cover art resized from {w}x{h} to {TARGET_SIZE}x{TARGET_SIZE}: {out_path}")
    return str(out_path)

"""
Song Factory - CD Art Generator

Creates disc art, front cover, and back insert images using Pillow.
All dimensions are at 300 DPI for print-ready output.

  - Disc art:    1417x1417 px  (120mm circular)
  - Cover art:   1417x1417 px  (120mm square front insert)
  - Back insert: 1772x1394 px  (150x118mm back tray card)
"""

import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


# Dimensions at 300 DPI
DISC_SIZE = 1417        # 120mm at 300 DPI
DISC_HOLE = 177         # 15mm center hole
COVER_SIZE = 1417       # 120mm front insert
BACK_W = 1772           # 150mm
BACK_H = 1394           # 118mm

# Default colors
DEFAULT_BG = "#2b2b2b"
DEFAULT_TEXT = "#E8A838"
DEFAULT_SUBTLE = "#888888"

# Font search paths (platform-aware)
from platform_utils import get_font_search_paths
_FONT_PATHS = get_font_search_paths()


def _load_font(size: int, bold: bool = False) -> "ImageFont.FreeTypeFont":
    """Load a system font or fall back to Pillow default."""
    if not _HAS_PIL:
        return None
    prefer = [p for p in _FONT_PATHS if ("Bold" in p) == bold]
    prefer += [p for p in _FONT_PATHS if ("Bold" in p) != bold]
    for path in prefer:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert '#RRGGBB' to (R, G, B)."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _format_duration(seconds: float) -> str:
    """Format seconds as M:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


# ======================================================================
# Disc Art
# ======================================================================

def generate_disc_art(
    project: dict,
    tracks: list[dict],
    output_path: str,
    bg_color: str = DEFAULT_BG,
    text_color: str = DEFAULT_TEXT,
    font_size: int = 36,
    include_tracks: bool = True,
    custom_subtitle: str = "",
) -> str:
    """Generate circular disc art (1417x1417) with center hole masked.

    Returns the output path.
    """
    if not _HAS_PIL:
        raise RuntimeError("Pillow is required for art generation")

    bg_rgb = _hex_to_rgb(bg_color)
    text_rgb = _hex_to_rgb(text_color)
    subtle_rgb = _hex_to_rgb(DEFAULT_SUBTLE)

    img = Image.new("RGBA", (DISC_SIZE, DISC_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw filled circle (disc)
    draw.ellipse([0, 0, DISC_SIZE - 1, DISC_SIZE - 1], fill=bg_rgb)

    # Ring accent near edge
    ring_margin = 30
    draw.ellipse(
        [ring_margin, ring_margin, DISC_SIZE - ring_margin - 1, DISC_SIZE - ring_margin - 1],
        outline=text_rgb, width=3,
    )

    # Inner ring
    inner_ring = 200
    draw.ellipse(
        [inner_ring, inner_ring, DISC_SIZE - inner_ring - 1, DISC_SIZE - inner_ring - 1],
        outline=(*text_rgb, 80), width=1,
    )

    center = DISC_SIZE // 2

    # Album title
    album = project.get("album_title") or project.get("name", "")
    title_font = _load_font(font_size)
    if album:
        bbox = draw.textbbox((0, 0), album, font=title_font)
        tw = bbox[2] - bbox[0]
        draw.text(
            (center - tw // 2, center - 120),
            album, fill=text_rgb, font=title_font,
        )

    # Artist
    artist = project.get("artist", "Yakima Finds")
    artist_font = _load_font(int(font_size * 0.7))
    if artist:
        bbox = draw.textbbox((0, 0), artist, font=artist_font)
        tw = bbox[2] - bbox[0]
        draw.text(
            (center - tw // 2, center - 60),
            artist, fill=subtle_rgb, font=artist_font,
        )

    # Subtitle
    if custom_subtitle:
        sub_font = _load_font(int(font_size * 0.55))
        bbox = draw.textbbox((0, 0), custom_subtitle, font=sub_font)
        tw = bbox[2] - bbox[0]
        draw.text(
            (center - tw // 2, center + 20),
            custom_subtitle, fill=subtle_rgb, font=sub_font,
        )

    # Track listing around the ring (optional)
    if include_tracks and tracks:
        track_font = _load_font(max(14, font_size // 3))
        num_tracks = len(tracks)
        radius = center - 80

        for i, track in enumerate(tracks):
            angle = -90 + (360 / num_tracks) * i
            rad = math.radians(angle)
            x = center + int(radius * math.cos(rad))
            y = center + int(radius * math.sin(rad))
            label = f"{i + 1}"
            bbox = draw.textbbox((0, 0), label, font=track_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text(
                (x - tw // 2, y - th // 2),
                label, fill=(*text_rgb, 150), font=track_font,
            )

    # Cut center hole
    hole_margin = (DISC_SIZE - DISC_HOLE) // 2
    draw.ellipse(
        [hole_margin, hole_margin, hole_margin + DISC_HOLE, hole_margin + DISC_HOLE],
        fill=(0, 0, 0, 0),
    )

    # Save
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return output_path


# ======================================================================
# Cover Art (Front Insert)
# ======================================================================

def generate_cover_art(
    project: dict,
    tracks: list[dict],
    output_path: str,
    bg_color: str = DEFAULT_BG,
    text_color: str = DEFAULT_TEXT,
    font_size: int = 48,
    include_tracks: bool = True,
    custom_subtitle: str = "",
) -> str:
    """Generate square front cover art (1417x1417).

    Returns the output path.
    """
    if not _HAS_PIL:
        raise RuntimeError("Pillow is required for art generation")

    bg_rgb = _hex_to_rgb(bg_color)
    text_rgb = _hex_to_rgb(text_color)
    subtle_rgb = _hex_to_rgb(DEFAULT_SUBTLE)

    img = Image.new("RGB", (COVER_SIZE, COVER_SIZE), bg_rgb)
    draw = ImageDraw.Draw(img)

    # Border
    draw.rectangle([10, 10, COVER_SIZE - 11, COVER_SIZE - 11], outline=text_rgb, width=2)

    # Album title
    album = project.get("album_title") or project.get("name", "")
    title_font = _load_font(font_size, bold=True)
    y = 120

    if album:
        # Word-wrap long titles
        lines = _wrap_text(draw, album, title_font, COVER_SIZE - 160)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            tw = bbox[2] - bbox[0]
            draw.text(
                (COVER_SIZE // 2 - tw // 2, y),
                line, fill=text_rgb, font=title_font,
            )
            y += bbox[3] - bbox[1] + 10

    # Horizontal rule
    y += 20
    draw.line([(80, y), (COVER_SIZE - 80, y)], fill=text_rgb, width=2)
    y += 30

    # Artist
    artist = project.get("artist", "Yakima Finds")
    artist_font = _load_font(int(font_size * 0.7))
    if artist:
        bbox = draw.textbbox((0, 0), artist, font=artist_font)
        tw = bbox[2] - bbox[0]
        draw.text(
            (COVER_SIZE // 2 - tw // 2, y),
            artist, fill=subtle_rgb, font=artist_font,
        )
        y += bbox[3] - bbox[1] + 20

    # Subtitle
    if custom_subtitle:
        sub_font = _load_font(int(font_size * 0.5))
        bbox = draw.textbbox((0, 0), custom_subtitle, font=sub_font)
        tw = bbox[2] - bbox[0]
        draw.text(
            (COVER_SIZE // 2 - tw // 2, y),
            custom_subtitle, fill=subtle_rgb, font=sub_font,
        )
        y += bbox[3] - bbox[1] + 20

    # Track listing
    if include_tracks and tracks:
        y += 40
        track_font = _load_font(int(font_size * 0.45))
        for track in tracks:
            num = track.get("track_number", 0)
            title = track.get("title", "")
            dur = _format_duration(track.get("duration_seconds", 0))
            line = f"{num:2d}. {title}"

            if y > COVER_SIZE - 100:
                draw.text((80, y), "...", fill=subtle_rgb, font=track_font)
                break

            draw.text((80, y), line, fill=text_rgb, font=track_font)
            # Duration right-aligned
            bbox = draw.textbbox((0, 0), dur, font=track_font)
            tw = bbox[2] - bbox[0]
            draw.text(
                (COVER_SIZE - 80 - tw, y),
                dur, fill=subtle_rgb, font=track_font,
            )
            y += bbox[3] - bbox[1] + 8

    # Footer
    footer_font = _load_font(int(font_size * 0.35))
    footer = "Created with Song Factory"
    bbox = draw.textbbox((0, 0), footer, font=footer_font)
    tw = bbox[2] - bbox[0]
    draw.text(
        (COVER_SIZE // 2 - tw // 2, COVER_SIZE - 60),
        footer, fill=subtle_rgb, font=footer_font,
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return output_path


# ======================================================================
# Back Insert
# ======================================================================

def generate_back_insert(
    project: dict,
    tracks: list[dict],
    output_path: str,
    bg_color: str = DEFAULT_BG,
    text_color: str = DEFAULT_TEXT,
    font_size: int = 36,
    **kwargs,
) -> str:
    """Generate back tray card (1772x1394).

    Returns the output path.
    """
    if not _HAS_PIL:
        raise RuntimeError("Pillow is required for art generation")

    bg_rgb = _hex_to_rgb(bg_color)
    text_rgb = _hex_to_rgb(text_color)
    subtle_rgb = _hex_to_rgb(DEFAULT_SUBTLE)

    img = Image.new("RGB", (BACK_W, BACK_H), bg_rgb)
    draw = ImageDraw.Draw(img)

    # Border
    draw.rectangle([8, 8, BACK_W - 9, BACK_H - 9], outline=text_rgb, width=2)

    # Album + Artist header
    album = project.get("album_title") or project.get("name", "")
    artist = project.get("artist", "Yakima Finds")

    title_font = _load_font(font_size, bold=True)
    artist_font = _load_font(int(font_size * 0.7))

    y = 50
    if album:
        bbox = draw.textbbox((0, 0), album, font=title_font)
        tw = bbox[2] - bbox[0]
        draw.text((BACK_W // 2 - tw // 2, y), album, fill=text_rgb, font=title_font)
        y += bbox[3] - bbox[1] + 10

    if artist:
        bbox = draw.textbbox((0, 0), artist, font=artist_font)
        tw = bbox[2] - bbox[0]
        draw.text((BACK_W // 2 - tw // 2, y), artist, fill=subtle_rgb, font=artist_font)
        y += bbox[3] - bbox[1] + 20

    # Divider
    draw.line([(60, y), (BACK_W - 60, y)], fill=text_rgb, width=1)
    y += 30

    # Track listing
    track_font = _load_font(int(font_size * 0.6))
    left_margin = 80
    right_margin = BACK_W - 80

    for track in tracks:
        num = track.get("track_number", 0)
        title = track.get("title", "")
        performer = track.get("performer", "")
        dur = _format_duration(track.get("duration_seconds", 0))

        line = f"{num:2d}.  {title}"
        draw.text((left_margin, y), line, fill=text_rgb, font=track_font)

        # Duration
        bbox = draw.textbbox((0, 0), dur, font=track_font)
        tw = bbox[2] - bbox[0]
        draw.text((right_margin - tw, y), dur, fill=subtle_rgb, font=track_font)

        y += bbox[3] - bbox[1] + 6

        # Performer subtitle if different from album artist
        if performer and performer != artist:
            perf_font = _load_font(int(font_size * 0.45))
            draw.text(
                (left_margin + 40, y),
                performer, fill=subtle_rgb, font=perf_font,
            )
            y += 20

        if y > BACK_H - 120:
            break

    # Total duration footer
    total = sum(t.get("duration_seconds", 0) for t in tracks)
    total_str = f"Total: {_format_duration(total)}"
    footer_font = _load_font(int(font_size * 0.5))
    bbox = draw.textbbox((0, 0), total_str, font=footer_font)
    tw = bbox[2] - bbox[0]
    draw.text(
        (BACK_W // 2 - tw // 2, BACK_H - 80),
        total_str, fill=text_rgb, font=footer_font,
    )

    # Credits
    credits_font = _load_font(int(font_size * 0.35))
    credits = "Created with Song Factory — Yakima Finds"
    bbox = draw.textbbox((0, 0), credits, font=credits_font)
    tw = bbox[2] - bbox[0]
    draw.text(
        (BACK_W // 2 - tw // 2, BACK_H - 40),
        credits, fill=subtle_rgb, font=credits_font,
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return output_path


# ======================================================================
# Helpers
# ======================================================================

def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    """Simple word-wrap for a text string."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines

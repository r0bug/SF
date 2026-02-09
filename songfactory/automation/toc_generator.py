"""
Song Factory - cdrdao TOC File Generator

Generates TOC file content for burning audio CDs with CD-TEXT metadata
using cdrdao.  Pure functions, no QThread.
"""


def _escape_cdtext(text: str) -> str:
    """Escape double quotes in CD-TEXT strings."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _seconds_to_msf(seconds: float) -> str:
    """Convert seconds to MM:SS:FF format (75 frames per second)."""
    total_frames = int(round(seconds * 75))
    minutes = total_frames // (60 * 75)
    remaining = total_frames % (60 * 75)
    secs = remaining // 75
    frames = remaining % 75
    return f"{minutes}:{secs:02d}:{frames:02d}"


def generate_toc(project: dict, tracks: list[dict]) -> str:
    """Generate a cdrdao TOC file string with CD-TEXT.

    Args:
        project: CD project dict with keys: album_title, artist,
                 songwriter, message.
        tracks:  List of track dicts, each with: title, performer,
                 songwriter, wav_path, pregap_seconds.

    Returns:
        Complete TOC file content as a string.
    """
    lines = ["CD_DA", ""]

    # Disc-level CD-TEXT
    album = _escape_cdtext(project.get("album_title") or project.get("name", ""))
    artist = _escape_cdtext(project.get("artist", "Yakima Finds"))
    songwriter = _escape_cdtext(project.get("songwriter", ""))
    message = _escape_cdtext(project.get("message", ""))

    lines.append("CD_TEXT {")
    lines.append("  LANGUAGE_MAP { 0 : EN }")
    lines.append("  LANGUAGE 0 {")
    lines.append(f'    TITLE "{album}"')
    lines.append(f'    PERFORMER "{artist}"')
    if songwriter:
        lines.append(f'    SONGWRITER "{songwriter}"')
    if message:
        lines.append(f'    MESSAGE "{message}"')
    lines.append("  }")
    lines.append("}")
    lines.append("")

    # Tracks
    for i, track in enumerate(tracks):
        title = _escape_cdtext(track.get("title", f"Track {i + 1}"))
        performer = _escape_cdtext(track.get("performer", artist))
        tr_songwriter = _escape_cdtext(track.get("songwriter", ""))
        wav_path = track.get("wav_path") or track.get("source_path", "")
        pregap = track.get("pregap_seconds", 2.0)

        lines.append("TRACK AUDIO")

        # Track CD-TEXT
        lines.append("CD_TEXT {")
        lines.append("  LANGUAGE 0 {")
        lines.append(f'    TITLE "{title}"')
        lines.append(f'    PERFORMER "{performer}"')
        if tr_songwriter:
            lines.append(f'    SONGWRITER "{tr_songwriter}"')
        lines.append("  }")
        lines.append("}")

        # Pre-gap (skip for first track — cdrdao adds it automatically)
        if i > 0 and pregap > 0:
            lines.append(f"PREGAP {_seconds_to_msf(pregap)}")

        # Audio file
        lines.append(f'FILE "{wav_path}" 0')
        lines.append("")

    return "\n".join(lines)

"""
Song Factory - Input Validation Layer

Validation functions for user-facing forms.  Each returns a list of
``ValidationError`` instances (empty list means valid).
"""


class ValidationError:
    """Represents a single validation failure."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message

    def __repr__(self):
        return f"ValidationError({self.field!r}, {self.message!r})"


def validate_song(
    title: str,
    prompt: str,
    lyrics: str,
    max_prompt_length: int = 300,
) -> list[ValidationError]:
    """Validate song creation/edit inputs."""
    errors = []
    if not title or not title.strip():
        errors.append(ValidationError("title", "Title cannot be empty"))
    if not prompt or not prompt.strip():
        errors.append(ValidationError("prompt", "Prompt cannot be empty"))
    if len(prompt) > max_prompt_length:
        errors.append(
            ValidationError(
                "prompt",
                f"Prompt exceeds {max_prompt_length} characters "
                f"({len(prompt)} / {max_prompt_length})",
            )
        )
    if not lyrics or not lyrics.strip():
        errors.append(ValidationError("lyrics", "Lyrics cannot be empty"))
    return errors


def validate_genre(name: str, prompt_template: str) -> list[ValidationError]:
    """Validate genre creation/edit inputs."""
    errors = []
    if not name or not name.strip():
        errors.append(ValidationError("name", "Genre name cannot be empty"))
    if not prompt_template or not prompt_template.strip():
        errors.append(
            ValidationError("prompt_template", "Prompt template cannot be empty")
        )
    return errors


def validate_lore(title: str, content: str) -> list[ValidationError]:
    """Validate lore creation/edit inputs."""
    errors = []
    if not title or not title.strip():
        errors.append(ValidationError("title", "Title cannot be empty"))
    if not content or not content.strip():
        errors.append(ValidationError("content", "Content cannot be empty"))
    return errors


def validate_distribution(
    song_id: int | None,
    songwriter: str,
    cover_art_path: str | None = None,
) -> list[ValidationError]:
    """Validate distribution form inputs."""
    errors = []
    if not song_id:
        errors.append(ValidationError("song_id", "Song is required"))
    if not songwriter or not songwriter.strip():
        errors.append(
            ValidationError("songwriter", "Songwriter legal name is required")
        )
    if cover_art_path:
        import os

        if not os.path.isfile(cover_art_path):
            errors.append(
                ValidationError("cover_art", f"Cover art file not found: {cover_art_path}")
            )
        else:
            try:
                from automation.cover_art_preparer import validate_cover_art

                result = validate_cover_art(cover_art_path)
                if not result.get("valid", False):
                    errors.append(
                        ValidationError("cover_art", result.get("error", "Invalid cover art"))
                    )
            except ImportError:
                pass  # cover_art_preparer not available
    return errors

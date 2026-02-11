"""Tests for input validation."""

from validators import validate_song, validate_genre, validate_lore, validate_distribution, ValidationError


class TestValidateSong:
    def test_valid_song(self):
        assert validate_song("Title", "A prompt", "Lyrics here") == []

    def test_empty_title(self):
        errors = validate_song("", "prompt", "lyrics")
        assert any(e.field == "title" for e in errors)

    def test_empty_prompt(self):
        errors = validate_song("T", "", "lyrics")
        assert any(e.field == "prompt" for e in errors)

    def test_prompt_too_long(self):
        errors = validate_song("T", "x" * 301, "lyrics")
        assert any(e.field == "prompt" and "300" in e.message for e in errors)

    def test_empty_lyrics(self):
        errors = validate_song("T", "prompt", "")
        assert any(e.field == "lyrics" for e in errors)

    def test_whitespace_only(self):
        errors = validate_song("  ", "  ", "  ")
        assert len(errors) == 3


class TestValidateGenre:
    def test_valid_genre(self):
        assert validate_genre("Rock", "heavy guitar") == []

    def test_empty_name(self):
        errors = validate_genre("", "template")
        assert any(e.field == "name" for e in errors)

    def test_empty_template(self):
        errors = validate_genre("Rock", "")
        assert any(e.field == "prompt_template" for e in errors)


class TestValidateLore:
    def test_valid_lore(self):
        assert validate_lore("Title", "Content") == []

    def test_empty_title(self):
        errors = validate_lore("", "Content")
        assert any(e.field == "title" for e in errors)


class TestValidateDistribution:
    def test_valid_distribution(self):
        assert validate_distribution(1, "Writer Name") == []

    def test_no_song(self):
        errors = validate_distribution(None, "Writer")
        assert any(e.field == "song_id" for e in errors)

    def test_no_songwriter(self):
        errors = validate_distribution(1, "")
        assert any(e.field == "songwriter" for e in errors)

    def test_nonexistent_cover_art(self):
        errors = validate_distribution(1, "W", cover_art_path="/nonexistent/art.png")
        assert any(e.field == "cover_art" for e in errors)

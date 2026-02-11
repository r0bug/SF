"""
Song Factory - Anthropic API Client Module

Provides a SongGenerator class that wraps the Anthropic API to generate
songs with lore-aware, genre-sensitive prompts for AI music generation
on lalals.com.
"""

import json
import re
from typing import Optional

from anthropic import Anthropic

from ai_models import DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SongGenerationError(Exception):
    """Raised when song generation fails for any reason."""


# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are a professional songwriter creating songs for AI music generation on lalals.com.

LORE CONTEXT — Use these details about real people, places, and stories to write authentic, specific lyrics:
{lore_block}

RULES:
- Spell "Yakima" as "Yak-eh-Mah" in ALL lyrics for correct AI vocal pronunciation
- The PROMPT field must be ≤ 300 characters. It describes the genre, instruments, tempo, vocal style, and mood. It does NOT contain lyrics.
- LYRICS can be full length with verse/chorus/bridge structure.
- Be creative with which lore details to include — not every song needs every detail.
- If the genre is specified, use the genre's prompt template as a starting point for the prompt field.
- Lyrics should feel natural to the genre — a country song sounds different from a hip-hop track.
- Brews and Cues has multiple bartenders (Casey, Logan, Chris, Mike) — only use ONE per song.
- Yakima Finds has the records, CDs, cassettes, 8-tracks, stereo annex (Marantz, Kenwood, Pioneer, reel-to-reels, turntables).
- Ralph's has the guitars, amps, instruments, and the recording studio with a young band.

Respond in this exact JSON format:
{{
    "title": "Song Title Here",
    "genre_label": "GENRE LABEL (Style Note)",
    "prompt": "The ≤300 character genre/instrument/vocal/mood prompt for lalals.com",
    "lyrics": "Full lyrics with [Verse 1], [Chorus], [Bridge] etc. markers"
}}"""


# ---------------------------------------------------------------------------
# SongGenerator
# ---------------------------------------------------------------------------

class SongGenerator:
    """Generates songs via the Anthropic API with lore context and genre awareness."""

    def __init__(self, api_key: str, model: str | None = None):
        self.client = Anthropic(api_key=api_key)
        self.model = model or DEFAULT_MODEL

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_song(
        self,
        user_input: str,
        active_lore: list[dict],
        genre_name: Optional[str] = None,
        genre_prompt_template: Optional[str] = None,
        style_notes: Optional[str] = None,
    ) -> dict:
        """
        Generate a song using the Anthropic API.

        Args:
            user_input: What the user wants the song about.
            active_lore: List of lore dicts with 'title' and 'content' keys.
            genre_name: Optional genre name if the user selected one.
            genre_prompt_template: Optional genre prompt template.
            style_notes: Optional style reference text.

        Returns:
            dict with keys: title, genre_label, prompt, lyrics.

        Raises:
            SongGenerationError: On any failure during generation or parsing.
        """
        system_prompt = self._build_system_prompt(active_lore)
        user_message = self._build_user_message(
            user_input, genre_name, genre_prompt_template, style_notes,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as exc:
            raise SongGenerationError(f"Anthropic API call failed: {exc}") from exc

        raw_text = response.content[0].text
        return self._parse_response(raw_text)

    def test_connection(self) -> bool:
        """Make a minimal API call to verify the key works.

        Returns:
            True if the API responds successfully, False otherwise.
        """
        try:
            self.client.messages.create(
                model=self.model,
                max_tokens=16,
                messages=[{"role": "user", "content": "Say OK"}],
            )
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_system_prompt(active_lore: list[dict]) -> str:
        """Assemble the system prompt with concatenated lore entries."""
        if active_lore:
            lore_block = "\n\n".join(
                f"### {entry['title']}\n{entry['content']}"
                for entry in active_lore
            )
        else:
            lore_block = "(No lore entries are currently active.)"

        return _SYSTEM_PROMPT_TEMPLATE.format(lore_block=lore_block)

    @staticmethod
    def _build_user_message(
        user_input: str,
        genre_name: Optional[str],
        genre_prompt_template: Optional[str],
        style_notes: Optional[str],
    ) -> str:
        """Construct the user message from the input and optional parameters."""
        message = f"Write a song about: {user_input}"

        if genre_name and genre_name != "Auto (let AI choose)":
            message += f"\n\nGenre: {genre_name}"
            if genre_prompt_template:
                message += (
                    f"\nGenre prompt template to build from: {genre_prompt_template}"
                )

        if style_notes:
            message += f"\n\nStyle reference: {style_notes}"

        return message

    @staticmethod
    def _parse_response(raw_text: str) -> dict:
        """Parse JSON from the model response, handling markdown code fences.

        Raises:
            SongGenerationError: If the response cannot be parsed or is missing
                required keys.
        """
        text = raw_text.strip()

        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        fence_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL,
        )
        if fence_match:
            text = fence_match.group(1).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SongGenerationError(
                f"Failed to parse JSON from model response: {exc}\n"
                f"Raw response:\n{raw_text}"
            ) from exc

        required_keys = {"title", "genre_label", "prompt", "lyrics"}
        missing = required_keys - set(data.keys())
        if missing:
            raise SongGenerationError(
                f"Model response missing required keys: {missing}"
            )

        return {
            "title": data["title"],
            "genre_label": data["genre_label"],
            "prompt": data["prompt"],
            "lyrics": data["lyrics"],
        }

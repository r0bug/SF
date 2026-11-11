"""Deterministic lyric fixes applied before anything is sung.

The AI is told to spell Yakima phonetically, but it keeps proper names
("Yakima Finds", "Yakima River") in normal spelling — and the AI singer
then pronounces the word two different ways in one song.  So every
lyric passes through ``apply_pronunciation`` after generation and again
right before submission.
"""

import re

PHONETIC_YAKIMA = "Yak-eh-Mah"

_YAKIMA_RE = re.compile(r"\byakima", re.IGNORECASE)


def _match_case(word: str) -> str:
    if word.isupper():
        return PHONETIC_YAKIMA.upper()
    if word.islower():
        return PHONETIC_YAKIMA.lower()
    return PHONETIC_YAKIMA


def apply_pronunciation(lyrics: str) -> str:
    """Spell every "Yakima" (any case, incl. "Yakima's", "Yakima Finds")
    as "Yak-eh-Mah" so the AI vocalist pronounces it one way."""
    if not lyrics:
        return lyrics
    return _YAKIMA_RE.sub(lambda m: _match_case(m.group(0)), lyrics)

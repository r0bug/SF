"""
Song Factory - Lore Summarizer Module

Uses the Anthropic API to summarize web content into songwriter-relevant
lore entries focusing on names, places, stories, and cultural details.
"""

from anthropic import Anthropic

from ai_models import DEFAULT_MODEL, create_message, resolve_model, response_text


_SYSTEM_PROMPT = """\
You are a research assistant for a songwriter who writes songs about Yakima, Washington \
and the people, places, and stories connected to it.

Your job is to read web content and extract a concise, songwriter-relevant summary. \
Focus on:
- Names of people, businesses, and landmarks
- Specific stories, anecdotes, and historical events
- Cultural details, traditions, and local color
- Geographic details and descriptions of places
- Interesting facts that could inspire song lyrics

Write in a factual, note-taking style. Use short paragraphs or bullet points. \
Keep the summary between 100-400 words. Do NOT invent details — only include \
information present in the source material.

Respond with ONLY the summary text, no preamble or extra formatting."""


_MERGE_SYSTEM_PROMPT = """\
You are a research assistant for a songwriter who writes songs about Yakima, Washington \
and the people, places, and stories connected to it.

You will receive several research summaries on related topics, each from a different \
source. Merge them into ONE cohesive, songwriter-relevant lore entry:
- Combine overlapping facts once; do not repeat the same detail
- Keep every distinct name, place, date, story, anecdote, and bit of local color
- Organize by theme or chronology rather than by source
- If sources disagree, keep both versions and note the discrepancy briefly
- Do NOT invent details — only use information present in the summaries

Write in a factual, note-taking style with short paragraphs or bullet points, \
roughly 200-700 words depending on how much material there is.

Respond in exactly this format:
TITLE: <a short, specific title for the merged entry>

<the merged summary text>"""


def _strip_source_lines(text: str) -> str:
    """Drop the trailing 'Source: <url>' line added by summarize()."""
    lines = text.rstrip().splitlines()
    while lines and (lines[-1].startswith("Source:") or not lines[-1].strip()):
        lines.pop()
    return "\n".join(lines)


class LoreSummarizer:
    """Summarizes web content into lore entries via the Anthropic API."""

    def __init__(self, api_key: str, model: str | None = None):
        self.client = Anthropic(api_key=api_key)
        self.model = resolve_model(model or DEFAULT_MODEL)

    def summarize(
        self,
        title: str,
        url: str,
        content: str,
        category: str = "general",
        custom_instructions: str = "",
    ) -> dict:
        """Summarize web content into a lore entry.

        Args:
            title: The page/article title.
            url: The source URL.
            content: The plain-text page content to summarize.
            category: Lore category (people, places, events, themes, rules).
            custom_instructions: Optional extra instructions for the summary.

        Returns:
            dict with keys: title, content, category, source_url
        """
        user_message = f"Article title: {title}\nSource URL: {url}\n\n"

        if custom_instructions:
            user_message += f"Additional instructions: {custom_instructions}\n\n"

        user_message += f"Content to summarize:\n\n{content}"

        response = create_message(
            self.client,
            model=self.model,
            max_tokens=8000,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        summary_text = response_text(response).strip()
        summary_text += f"\n\nSource: {url}"

        return {
            "title": title,
            "content": summary_text,
            "category": category,
            "source_url": url,
        }

    def merge(
        self,
        summaries: list[dict],
        category: str = "general",
        title_hint: str = "",
    ) -> dict:
        """Merge several summaries into one deduplicated lore entry.

        Args:
            summaries: Dicts with ``title``, ``content`` and ``source_url``
                (as returned by ``summarize()`` or edited in the UI).
            category: Lore category for the merged entry.
            title_hint: Optional topic (e.g. the search query) to steer
                the merged title.

        Returns:
            dict with keys: title, content, category, source_url (first
            source), source_urls (all sources), merged_count
        """
        if len(summaries) < 2:
            raise ValueError("Need at least two summaries to merge")

        sources = [s.get("source_url", "") for s in summaries]
        sources = list(dict.fromkeys(u for u in sources if u))

        parts = []
        if title_hint:
            parts.append(f"Research topic: {title_hint}\n")
        for i, s in enumerate(summaries, start=1):
            parts.append(
                f"--- Summary {i}: {s.get('title', '')} "
                f"({s.get('source_url', 'unknown source')}) ---\n"
                f"{_strip_source_lines(s.get('content', ''))}\n"
            )

        response = create_message(
            self.client,
            model=self.model,
            max_tokens=16000,
            system=_MERGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": "\n".join(parts)}],
        )
        text = response_text(response).strip()

        title = title_hint or summaries[0].get("title", "Merged lore")
        first, _, rest = text.partition("\n")
        if first.upper().startswith("TITLE:"):
            title = first.split(":", 1)[1].strip() or title
            text = rest.strip()

        if sources:
            text += "\n\nSources:\n" + "\n".join(f"- {u}" for u in sources)

        return {
            "title": title,
            "content": text,
            "category": category,
            "source_url": sources[0] if sources else "",
            "source_urls": sources,
            "merged_count": len(summaries),
        }

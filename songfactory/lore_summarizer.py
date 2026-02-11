"""
Song Factory - Lore Summarizer Module

Uses the Anthropic API to summarize web content into songwriter-relevant
lore entries focusing on names, places, stories, and cultural details.
"""

from anthropic import Anthropic

from ai_models import DEFAULT_MODEL


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


class LoreSummarizer:
    """Summarizes web content into lore entries via the Anthropic API."""

    def __init__(self, api_key: str, model: str | None = None):
        self.client = Anthropic(api_key=api_key)
        self.model = model or DEFAULT_MODEL

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

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        summary_text = response.content[0].text.strip()
        summary_text += f"\n\nSource: {url}"

        return {
            "title": title,
            "content": summary_text,
            "category": category,
            "source_url": url,
        }

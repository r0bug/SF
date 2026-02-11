"""Available AI models for Song Factory.

Centralizes model definitions so that api_client.py, lore_summarizer.py,
and the Settings tab all reference the same list.
"""

# Each entry: (model_id, display_name, description)
AVAILABLE_MODELS = [
    ("claude-sonnet-4-5-20250929", "Claude Sonnet 4.5", "Fast, cost-effective"),
    ("claude-opus-4-6", "Claude Opus 4.6", "Most capable"),
    ("claude-haiku-4-5-20251001", "Claude Haiku 4.5", "Fastest, lowest cost"),
    ("claude-sonnet-4-20250514", "Claude Sonnet 4", "Previous generation"),
]

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def get_model_ids() -> list[str]:
    """Return just the model ID strings."""
    return [m[0] for m in AVAILABLE_MODELS]


def get_model_display_name(model_id: str) -> str:
    """Return the display name for a model ID."""
    for mid, name, _ in AVAILABLE_MODELS:
        if mid == model_id:
            return name
    return model_id


def get_model_choices() -> list[tuple[str, str]]:
    """Return (model_id, display_label) pairs for dropdown menus."""
    return [(mid, f"{name} — {desc}") for mid, name, desc in AVAILABLE_MODELS]

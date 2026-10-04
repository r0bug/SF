"""Available AI models for Song Factory.

Centralizes model definitions so that api_client.py, lore_summarizer.py,
and the Settings tab all reference the same list.
"""

# Each entry: (model_id, display_name, description)
AVAILABLE_MODELS = [
    ("claude-opus-5-5", "Claude Opus 5.5", "Most capable (recommended)"),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5", "Fast, cost-effective"),
    ("claude-haiku-4-5", "Claude Haiku 4.5", "Fastest, lowest cost"),
    ("claude-sonnet-4-5", "Claude Sonnet 4.5", "Previous generation"),
]

DEFAULT_MODEL = "claude-opus-5-5"

# Model ids that were offered here before and are retired or renamed, mapped
# to their current replacement. A saved setting naming one of these keeps
# working instead of failing with not_found_error.
REPLACED_MODELS = {
    "claude-sonnet-4-20250514": "claude-sonnet-5-5",   # retired 2026-06-15
    "claude-sonnet-4-0": "claude-sonnet-5-5",
    "claude-opus-4-6": "claude-opus-5-5",
    "claude-sonnet-4-5-20250929": "claude-sonnet-4-5",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5",
}

# Models that accept the server-side refusal fallback (fallbacks: "default").
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}


def resolve_model(model_id: str | None) -> str:
    """Return a usable model id: replacements for retired ids, else the default."""
    if not model_id:
        return DEFAULT_MODEL
    return REPLACED_MODELS.get(model_id, model_id)


def create_message(client, *, model: str, **kwargs):
    """messages.create with the model resolved and, where supported, the
    server-side refusal fallback enabled (a declined request is re-run on a
    fallback model inside the same call)."""
    model = resolve_model(model)
    if model in _FALLBACK_MODELS:
        return client.beta.messages.create(
            model=model,
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
            **kwargs,
        )
    return client.messages.create(model=model, **kwargs)


def response_text(response) -> str:
    """Concatenate the text blocks of a response.

    Current models can return thinking blocks before the text, so
    ``content[0]`` is not reliably the answer.
    """
    if getattr(response, "stop_reason", None) == "refusal":
        raise RuntimeError("The model declined this request.")
    return "".join(
        getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text"
    )


def get_model_ids() -> list[str]:
    """Return just the model ID strings."""
    return [m[0] for m in AVAILABLE_MODELS]


def get_model_display_name(model_id: str) -> str:
    """Return the display name for a model ID."""
    model_id = resolve_model(model_id)
    for mid, name, _ in AVAILABLE_MODELS:
        if mid == model_id:
            return name
    return model_id


def get_model_choices() -> list[tuple[str, str]]:
    """Return (model_id, display_label) pairs for dropdown menus."""
    return [(mid, f"{name} — {desc}") for mid, name, desc in AVAILABLE_MODELS]

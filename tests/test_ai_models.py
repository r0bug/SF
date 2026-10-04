"""Tests for the AI models registry."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ai_models import (
    AVAILABLE_MODELS, DEFAULT_MODEL, REPLACED_MODELS,
    create_message, get_model_ids, get_model_display_name, get_model_choices,
    resolve_model, response_text,
)


def test_available_models_not_empty():
    assert len(AVAILABLE_MODELS) >= 3


def test_default_model_in_list():
    ids = get_model_ids()
    assert DEFAULT_MODEL in ids


def test_get_model_ids():
    ids = get_model_ids()
    assert all(isinstance(i, str) for i in ids)
    assert len(ids) == len(AVAILABLE_MODELS)


def test_get_model_display_name_known():
    name = get_model_display_name(DEFAULT_MODEL)
    assert name != DEFAULT_MODEL  # Should be a friendly name
    assert len(name) > 0


def test_get_model_display_name_unknown():
    name = get_model_display_name("unknown-model-xyz")
    assert name == "unknown-model-xyz"  # Falls back to model ID


def test_get_model_choices():
    choices = get_model_choices()
    assert len(choices) == len(AVAILABLE_MODELS)
    for model_id, label in choices:
        assert isinstance(model_id, str)
        assert isinstance(label, str)
        assert " — " in label  # format: "Name — Description"


# Retired-model mapping, text extraction and fallback routing

def test_retired_sonnet_4_maps_to_current_sonnet():
    assert resolve_model("claude-sonnet-4-20250514") == "claude-sonnet-5-5"


def test_empty_setting_uses_default():
    assert resolve_model("") == DEFAULT_MODEL
    assert resolve_model(None) == DEFAULT_MODEL


def test_dropdown_never_offers_a_replaced_id():
    assert not set(get_model_ids()) & set(REPLACED_MODELS)
    assert all(resolve_model(m) == m for m in get_model_ids())


def test_response_text_skips_thinking_blocks():
    resp = SimpleNamespace(stop_reason="end_turn", content=[
        SimpleNamespace(type="thinking", thinking=""),
        SimpleNamespace(type="text", text="Hello "),
        SimpleNamespace(type="text", text="Yak-eh-Mah"),
    ])
    assert response_text(resp) == "Hello Yak-eh-Mah"


def test_response_text_raises_on_refusal():
    with pytest.raises(RuntimeError):
        response_text(SimpleNamespace(stop_reason="refusal", content=[]))


def test_create_message_enables_fallback_on_current_models():
    client = MagicMock()
    create_message(client, model="claude-sonnet-4-20250514", max_tokens=10, messages=[])
    kw = client.beta.messages.create.call_args.kwargs
    assert kw["model"] == "claude-sonnet-5-5"
    assert kw["extra_body"] == {"fallbacks": "default"}
    assert kw["betas"] == ["server-side-fallback-2026-07-01"]
    client.messages.create.assert_not_called()


def test_create_message_plain_call_on_older_models():
    client = MagicMock()
    create_message(client, model="claude-haiku-4-5", max_tokens=10, messages=[])
    assert client.messages.create.call_args.kwargs["model"] == "claude-haiku-4-5"
    client.beta.messages.create.assert_not_called()

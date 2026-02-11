"""Tests for the AI models registry."""

from ai_models import (
    AVAILABLE_MODELS, DEFAULT_MODEL,
    get_model_ids, get_model_display_name, get_model_choices,
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

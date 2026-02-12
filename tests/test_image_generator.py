"""Tests for the Segmind image generator API client."""

import sys
import os
from unittest.mock import patch, MagicMock

import pytest

# Ensure the songfactory package is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "songfactory"))

from automation.image_generator import (
    SegmindImageGenerator,
    ImageGenerationError,
    MODELS,
    API_BASE,
)


# ------------------------------------------------------------------
# Model registry
# ------------------------------------------------------------------

class TestModels:
    """Tests for the MODELS dict."""

    def test_models_contains_flux(self):
        assert "Flux 1.1 Pro" in MODELS
        assert MODELS["Flux 1.1 Pro"] == "flux-1.1-pro"

    def test_models_contains_sdxl(self):
        assert "SDXL 1.0" in MODELS
        assert MODELS["SDXL 1.0"] == "sdxl1.0-txt2img"

    def test_models_contains_vega(self):
        assert "Segmind Vega" in MODELS
        assert MODELS["Segmind Vega"] == "segmind-vega"

    def test_models_has_three_entries(self):
        assert len(MODELS) == 3


# ------------------------------------------------------------------
# Constructor
# ------------------------------------------------------------------

class TestConstructor:
    """Tests for SegmindImageGenerator construction."""

    def test_default_model(self):
        gen = SegmindImageGenerator(api_key="test-key")
        assert gen.api_key == "test-key"
        assert gen.model == "flux-1.1-pro"

    def test_custom_model(self):
        gen = SegmindImageGenerator(api_key="k", model="sdxl1.0-txt2img")
        assert gen.model == "sdxl1.0-txt2img"


# ------------------------------------------------------------------
# generate()
# ------------------------------------------------------------------

class TestGenerate:
    """Tests for the generate() method."""

    @patch("automation.image_generator.requests.post")
    def test_generate_returns_image_bytes(self, mock_post):
        fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = fake_image
        mock_post.return_value = mock_resp

        gen = SegmindImageGenerator(api_key="test-key")
        results = gen.generate("a beautiful sunset", width=512, height=512, count=2)

        assert len(results) == 2
        assert results[0] == fake_image
        assert results[1] == fake_image
        assert mock_post.call_count == 2

    @patch("automation.image_generator.requests.post")
    def test_generate_sends_correct_payload(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"img"
        mock_post.return_value = mock_resp

        gen = SegmindImageGenerator(api_key="my-key", model="segmind-vega")
        gen.generate("test prompt", width=1024, height=1024, count=1)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["headers"] == {"x-api-key": "my-key"}
        assert call_kwargs.kwargs["json"]["prompt"] == "test prompt"
        assert call_kwargs.kwargs["json"]["width"] == 1024
        assert call_kwargs.kwargs["json"]["height"] == 1024
        assert f"{API_BASE}/segmind-vega" in call_kwargs.args[0]

    @patch("automation.image_generator.requests.post")
    def test_generate_default_3000x3000(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"img"
        mock_post.return_value = mock_resp

        gen = SegmindImageGenerator(api_key="k")
        gen.generate("prompt", count=1)

        payload = mock_post.call_args.kwargs["json"]
        assert payload["width"] == 3000
        assert payload["height"] == 3000

    @patch("automation.image_generator.requests.post")
    def test_generate_four_images_default(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"img"
        mock_post.return_value = mock_resp

        gen = SegmindImageGenerator(api_key="k")
        results = gen.generate("prompt")

        assert len(results) == 4
        assert mock_post.call_count == 4


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------

class TestErrorHandling:
    """Tests for HTTP error responses."""

    @patch("automation.image_generator.requests.post")
    def test_401_invalid_key(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_post.return_value = mock_resp

        gen = SegmindImageGenerator(api_key="bad-key")
        with pytest.raises(ImageGenerationError, match="Invalid Segmind API key"):
            gen.generate("prompt", count=1)

    @patch("automation.image_generator.requests.post")
    def test_429_rate_limit(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Too Many Requests"
        mock_post.return_value = mock_resp

        gen = SegmindImageGenerator(api_key="k")
        with pytest.raises(ImageGenerationError, match="rate limit"):
            gen.generate("prompt", count=1)

    @patch("automation.image_generator.requests.post")
    def test_500_server_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_post.return_value = mock_resp

        gen = SegmindImageGenerator(api_key="k")
        with pytest.raises(ImageGenerationError, match="HTTP 500"):
            gen.generate("prompt", count=1)

    @patch("automation.image_generator.requests.post")
    def test_network_error(self, mock_post):
        import requests
        mock_post.side_effect = requests.ConnectionError("DNS failure")

        gen = SegmindImageGenerator(api_key="k")
        with pytest.raises(ImageGenerationError, match="Network error"):
            gen.generate("prompt", count=1)

    @patch("automation.image_generator.requests.post")
    def test_error_stops_remaining_generations(self, mock_post):
        """An error on image 2 should stop, not continue to image 3."""
        good_resp = MagicMock()
        good_resp.status_code = 200
        good_resp.content = b"img"

        bad_resp = MagicMock()
        bad_resp.status_code = 500
        bad_resp.text = "Server Error"

        mock_post.side_effect = [good_resp, bad_resp]

        gen = SegmindImageGenerator(api_key="k")
        with pytest.raises(ImageGenerationError):
            gen.generate("prompt", count=4)

        # Should have stopped after the error (2 calls, not 4)
        assert mock_post.call_count == 2


# ------------------------------------------------------------------
# test_connection()
# ------------------------------------------------------------------

class TestConnection:
    """Tests for test_connection()."""

    @patch("automation.image_generator.requests.post")
    def test_connection_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"\x89PNG" + b"\x00" * 50
        mock_post.return_value = mock_resp

        gen = SegmindImageGenerator(api_key="good-key")
        assert gen.test_connection() is True

        # Verify it used small dimensions
        payload = mock_post.call_args.kwargs["json"]
        assert payload["width"] == 256
        assert payload["height"] == 256

    @patch("automation.image_generator.requests.post")
    def test_connection_failure(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_post.return_value = mock_resp

        gen = SegmindImageGenerator(api_key="bad-key")
        assert gen.test_connection() is False

    @patch("automation.image_generator.requests.post")
    def test_connection_empty_response(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b""
        mock_post.return_value = mock_resp

        gen = SegmindImageGenerator(api_key="k")
        assert gen.test_connection() is False

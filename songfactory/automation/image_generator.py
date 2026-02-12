"""Segmind API client for AI cover art generation.

Wraps the Segmind REST API to generate images from text prompts.
Used by the CoverArtDialog to produce album cover art candidates.
"""

import logging

import requests

logger = logging.getLogger("songfactory.automation")

API_BASE = "https://api.segmind.com/v1"


class ImageGenerationError(Exception):
    """Raised when image generation fails."""


# Supported Segmind models
MODELS = {
    "Flux 1.1 Pro": "flux-1.1-pro",
    "SDXL 1.0": "sdxl1.0-txt2img",
    "Segmind Vega": "segmind-vega",
}


class SegmindImageGenerator:
    """Generate images via the Segmind API."""

    def __init__(self, api_key: str, model: str = "flux-1.1-pro"):
        self.api_key = api_key
        self.model = model

    def generate(
        self,
        prompt: str,
        width: int = 3000,
        height: int = 3000,
        count: int = 4,
    ) -> list[bytes]:
        """Generate images from a text prompt.

        Args:
            prompt: The text prompt describing the desired image.
            width: Image width in pixels.
            height: Image height in pixels.
            count: Number of images to generate.

        Returns:
            List of raw image bytes (PNG/JPEG).

        Raises:
            ImageGenerationError: On HTTP errors or API failures.
        """
        url = f"{API_BASE}/{self.model}"
        headers = {"x-api-key": self.api_key}
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
        }

        results = []
        for i in range(count):
            logger.info("Generating image %d/%d via %s", i + 1, count, self.model)
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=120)
                if resp.status_code == 401:
                    raise ImageGenerationError(
                        "Invalid Segmind API key (HTTP 401). "
                        "Check your key in Settings."
                    )
                if resp.status_code == 429:
                    raise ImageGenerationError(
                        "Segmind rate limit exceeded (HTTP 429). "
                        "Please wait and try again."
                    )
                if resp.status_code >= 400:
                    raise ImageGenerationError(
                        f"Segmind API error (HTTP {resp.status_code}): "
                        f"{resp.text[:200]}"
                    )
                results.append(resp.content)
            except requests.RequestException as exc:
                raise ImageGenerationError(
                    f"Network error generating image {i + 1}: {exc}"
                ) from exc

        return results

    def test_connection(self) -> bool:
        """Verify the API key with a small test generation.

        Returns:
            True if the API responds successfully, False otherwise.
        """
        try:
            result = self.generate(
                prompt="test image, simple gradient",
                width=256,
                height=256,
                count=1,
            )
            return len(result) == 1 and len(result[0]) > 0
        except ImageGenerationError:
            return False

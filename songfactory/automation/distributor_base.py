"""Distributor plugin interface for Song Factory.

Defines the abstract base class that all distribution service integrations
must implement.  DistroKid is the first (and currently only) plugin.

To add a new distributor:
1. Create a new module (e.g. ``automation/tunecore_plugin.py``)
2. Subclass ``DistributorPlugin`` and implement all abstract methods
3. Register in ``AVAILABLE_DISTRIBUTORS``

Usage:
    from automation.distributor_base import get_distributor, list_distributors

    distributors = list_distributors()
    dk = get_distributor("distrokid")
    errors = dk.validate_release(dist_dict)
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("songfactory.automation.distributor_base")


class DistributorPlugin(ABC):
    """Abstract base class for distribution service integrations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name (e.g. 'DistroKid')."""
        ...

    @property
    @abstractmethod
    def slug(self) -> str:
        """Internal identifier (e.g. 'distrokid'). Used in DB distributor field."""
        ...

    @property
    @abstractmethod
    def requires_browser(self) -> bool:
        """Whether this distributor needs browser automation."""
        ...

    @property
    @abstractmethod
    def genre_map(self) -> dict[str, str]:
        """Mapping from Song Factory genre names to this service's genre names."""
        ...

    @abstractmethod
    def map_genre(self, sf_genre: str) -> str:
        """Map a Song Factory genre to this service's genre.

        Args:
            sf_genre: Song Factory genre name.

        Returns:
            Service-specific genre name.
        """
        ...

    @abstractmethod
    def validate_release(self, dist: dict) -> list[str]:
        """Validate a distribution record before upload.

        Args:
            dist: Distribution dict from the database.

        Returns:
            List of validation error strings. Empty list = valid.
        """
        ...

    def get_config_keys(self) -> list[str]:
        """Return config keys this distributor needs from Settings.

        Override to declare required configuration (email, password, etc.).
        """
        return []


class DistroKidPlugin(DistributorPlugin):
    """DistroKid distribution plugin."""

    @property
    def name(self) -> str:
        return "DistroKid"

    @property
    def slug(self) -> str:
        return "distrokid"

    @property
    def requires_browser(self) -> bool:
        return True

    @property
    def genre_map(self) -> dict[str, str]:
        # Import the existing mapping
        try:
            from automation.distrokid_driver import GENRE_MAP
            return dict(GENRE_MAP)
        except ImportError:
            return {}

    def map_genre(self, sf_genre: str) -> str:
        return self.genre_map.get(sf_genre, "Pop")

    def validate_release(self, dist: dict) -> list[str]:
        errors = []
        if not dist.get("songwriter"):
            errors.append("Songwriter legal name is required")
        if not dist.get("song_id"):
            errors.append("A song must be selected")
        cover = dist.get("cover_art_path", "")
        if cover and not _file_exists(cover):
            errors.append(f"Cover art file not found: {cover}")
        return errors

    def get_config_keys(self) -> list[str]:
        return ["dk_email", "dk_password", "dk_artist", "dk_songwriter"]


def _file_exists(path: str) -> bool:
    """Check if a file exists (avoids importing os at module level for testing)."""
    import os
    return os.path.isfile(path)


# Registry of available distributors
AVAILABLE_DISTRIBUTORS: dict[str, DistributorPlugin] = {
    "distrokid": DistroKidPlugin(),
}


def get_distributor(slug: str) -> Optional[DistributorPlugin]:
    """Get a distributor plugin by slug.

    Args:
        slug: Distributor identifier (e.g. "distrokid").

    Returns:
        Plugin instance or None if not found.
    """
    return AVAILABLE_DISTRIBUTORS.get(slug)


def list_distributors() -> list[DistributorPlugin]:
    """Return all registered distributor plugins."""
    return list(AVAILABLE_DISTRIBUTORS.values())

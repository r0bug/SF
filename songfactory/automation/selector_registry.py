"""Self-healing CSS selector registry for Song Factory browser automation.

Persists selector priority order to disk so that selectors which work
get tried first next time, and selectors which fail get moved to the back.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("songfactory.automation")

DEFAULT_REGISTRY_PATH = Path.home() / ".songfactory" / "selector_registry.json"


class SelectorRegistry:
    """Manages ordered selector groups with promote/demote learning.

    Each selector group (e.g. "prompt_textarea") stores a list of CSS
    selectors in priority order.  When a selector succeeds, it gets
    promoted to the front.  When it fails, it gets demoted to the back.
    The ordering persists to a JSON file between sessions.
    """

    def __init__(self, path: Path | str | None = None):
        self._path = Path(path) if path else DEFAULT_REGISTRY_PATH
        self._groups: dict[str, list[str]] = {}
        self._load()

    def register_group(self, name: str, selectors: list[str]) -> None:
        """Register a selector group with default ordering.

        If the group already exists on disk, this is a no-op (preserves
        learned ordering).  Only writes defaults for new groups.
        """
        if name in self._groups:
            return
        self._groups[name] = list(selectors)
        self._save()

    def get_selectors(self, name: str) -> list[str]:
        """Return selectors for a group in current priority order."""
        return list(self._groups.get(name, []))

    def promote(self, name: str, selector: str) -> None:
        """Move a selector to the front of its group (it worked)."""
        if name not in self._groups:
            return
        group = self._groups[name]
        if selector in group:
            group.remove(selector)
            group.insert(0, selector)
            self._save()

    def demote(self, name: str, selector: str) -> None:
        """Move a selector to the back of its group (it failed)."""
        if name not in self._groups:
            return
        group = self._groups[name]
        if selector in group:
            group.remove(selector)
            group.append(selector)
            self._save()

    def reset_group(self, name: str, selectors: list[str]) -> None:
        """Force overwrite a group's selector order."""
        self._groups[name] = list(selectors)
        self._save()

    def _load(self) -> None:
        """Load registry from disk."""
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._groups = data
                    logger.debug(f"Selector registry loaded: {len(data)} groups")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load selector registry: {e}")
                self._groups = {}
        else:
            self._groups = {}

    def _save(self) -> None:
        """Save registry to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._groups, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning(f"Failed to save selector registry: {e}")

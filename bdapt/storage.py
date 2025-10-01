"""Storage layer for bdapt."""

import json
import os
from pathlib import Path
from typing import Optional

from .exceptions import StorageError
from .models import BundleStorage


class BundleStore:
    """Manages persistent storage of bundle definitions."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize the bundle store.

        Args:
            data_dir: Directory for data storage. Defaults to /etc/bdapt
        """
        if data_dir is None:
            data_dir = Path("/etc/bdapt")

        self.data_dir = data_dir
        self.bundles_file = data_dir / "bundles.json"

    def _ensure_directory(self) -> None:
        """Ensure the data directory exists."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        except OSError as e:
            raise StorageError(f"Failed to create data directory: {e}")

    def load(self) -> BundleStorage:
        """Load bundle storage from disk."""
        if not self.bundles_file.exists():
            return BundleStorage()

        try:
            with open(self.bundles_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return BundleStorage.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            raise StorageError(f"Failed to load bundles: {e}")

    def save(self, storage: BundleStorage) -> None:
        """Save bundle storage to disk."""
        assert os.getuid() == 0, "Must be run as root"
        self._ensure_directory()

        try:
            with open(self.bundles_file, "w", encoding="utf-8") as f:
                json.dump(
                    storage.model_dump(),
                    f,
                    indent=2,
                    sort_keys=True,
                )
            # Set readable permissions for all users
            self.bundles_file.chmod(0o644)
        except OSError as e:
            raise StorageError(f"Failed to save bundles: {e}")

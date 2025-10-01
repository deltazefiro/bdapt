"""Storage layer for bdapt."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .exceptions import StorageError
from .models import BundleStorage


def escalate_root() -> bool:
    """Escalate to root privileges using sudo.

    Returns:
        True if already root or successfully authenticated with sudo, False otherwise.
    """
    if os.geteuid() == 0:
        return True  # Already root

    msg = "[sudo] password for %u:"
    try:
        subprocess.check_call(["sudo", "-v", "-p", msg])
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        print("sudo command not found.", file=sys.stderr)
        return False


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
        """Ensure the data directory exists with proper permissions."""
        if self.data_dir.exists():
            return

        try:
            subprocess.check_call(["sudo", "mkdir", "-p", str(self.data_dir)])
            subprocess.check_call(["sudo", "chmod", "755", str(self.data_dir)])
        except subprocess.CalledProcessError as e:
            raise StorageError(f"Failed to create data directory: {e}")

    def load(self) -> BundleStorage:
        """Load bundle storage from disk.

        No root privileges required for reading.
        """
        if not self.bundles_file.exists():
            return BundleStorage()

        try:
            with open(self.bundles_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return BundleStorage.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            raise StorageError(f"Failed to load bundles: {e}")

    def save(self, storage: BundleStorage) -> None:
        """Save bundle storage to disk.

        Requires root privileges to write to /etc/bdapt.
        """
        if not escalate_root():
            raise StorageError(
                "Unable to authenticate as sudo user. "
                "Root privileges are required to modify the config."
            )

        self._ensure_directory()

        with open(self.bundles_file, "w", encoding="utf-8") as f:
            json.dump(storage.model_dump(), f, indent=2, sort_keys=True)

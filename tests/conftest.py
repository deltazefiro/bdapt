"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest
from rich.console import Console

from bdapt.storage import BundleStore
from bdapt.bundle import BundleManager


@pytest.fixture
def temp_data_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for data storage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def bundle_store(temp_data_dir: Path) -> BundleStore:
    """Provide a BundleStore instance with temporary storage."""
    return BundleStore(data_dir=temp_data_dir)


@pytest.fixture
def bundle_manager(bundle_store: BundleStore) -> BundleManager:
    """Provide a BundleManager instance with temporary storage."""
    console = Console(file=None, stderr=False)  # Suppress output during tests
    return BundleManager(store=bundle_store, console=console)

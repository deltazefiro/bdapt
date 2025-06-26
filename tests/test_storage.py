"""Tests for storage layer."""

import json
from pathlib import Path

import pytest

from bdapt.models import Bundle, BundleStorage, PackageSpec
from bdapt.storage import BundleStore, StorageError


def test_bundle_store_init(temp_data_dir: Path):
    """Test BundleStore initialization."""
    store = BundleStore(data_dir=temp_data_dir)
    assert store.data_dir == temp_data_dir
    assert store.bundles_file == temp_data_dir / "bundles.json"
    assert store.lock_file == temp_data_dir / ".bdapt.lock"
    assert temp_data_dir.exists()


def test_bundle_store_load_empty(bundle_store: BundleStore):
    """Test loading when no storage file exists."""
    storage = bundle_store.load()
    assert isinstance(storage, BundleStorage)
    assert storage.bundles == {}


def test_bundle_store_save_and_load(bundle_store: BundleStore):
    """Test saving and loading bundle storage."""
    original_storage = BundleStorage()
    original_storage.bundles["test"] = Bundle(
        description="Test bundle", packages={"vim": PackageSpec(version=">= 8.0")}
    )

    # Save
    bundle_store.save(original_storage)
    assert bundle_store.bundles_file.exists()

    # Load and verify
    loaded_storage = bundle_store.load()
    assert "test" in loaded_storage.bundles
    assert loaded_storage.bundles["test"].description == "Test bundle"
    assert "vim" in loaded_storage.bundles["test"].packages
    assert loaded_storage.bundles["test"].packages["vim"].version == ">= 8.0"


def test_bundle_store_corrupted_file(bundle_store: BundleStore):
    """Test handling of corrupted JSON file."""
    # Create corrupted JSON file
    bundle_store.bundles_file.write_text("invalid json{")

    with pytest.raises(StorageError, match="Failed to load bundles"):
        bundle_store.load()


def test_bundle_store_file_locking(bundle_store: BundleStore):
    """Test that file locking works (basic test)."""
    storage = BundleStorage()

    # This should not raise an exception
    bundle_store.save(storage)
    loaded = bundle_store.load()

    assert isinstance(loaded, BundleStorage)

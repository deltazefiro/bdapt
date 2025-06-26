"""Tests for bundle manager (unit tests only)."""

import pytest
from unittest.mock import Mock, patch

from bdapt.bundle import BundleError, BundleManager
from bdapt.models import Bundle, PackageSpec


def test_validate_bundle_name(bundle_manager: BundleManager):
    """Test bundle name validation."""
    # Valid names
    bundle_manager._validate_bundle_name("test")
    bundle_manager._validate_bundle_name("web-stack")
    bundle_manager._validate_bundle_name("app1.dev")
    bundle_manager._validate_bundle_name("a")

    # Invalid names
    with pytest.raises(BundleError, match="Invalid bundle name"):
        bundle_manager._validate_bundle_name("Test")  # uppercase

    with pytest.raises(BundleError, match="Invalid bundle name"):
        bundle_manager._validate_bundle_name("test_bundle")  # underscore

    with pytest.raises(BundleError, match="Invalid bundle name"):
        bundle_manager._validate_bundle_name("test bundle")  # space

    with pytest.raises(BundleError, match="Invalid bundle name"):
        bundle_manager._validate_bundle_name("-test")  # starts with hyphen


def test_get_metapackage_name(bundle_manager: BundleManager):
    """Test metapackage name generation."""
    assert bundle_manager._get_metapackage_name("web-stack") == "bdapt-web-stack"
    assert bundle_manager._get_metapackage_name("dev") == "bdapt-dev"


def test_generate_control_file(bundle_manager: BundleManager):
    """Test control file generation."""
    bundle = Bundle(
        description="Web services",
        packages={
            "nginx": PackageSpec(version=">= 1.18.0"),
            "postgresql": PackageSpec(),
        },
    )

    control_content = bundle_manager._generate_control_file("web-stack", bundle)

    assert "Package: bdapt-web-stack" in control_content
    assert "Description: Web services" in control_content
    assert "Depends: nginx (>= 1.18.0), postgresql" in control_content
    assert "Version: 1.0~" in control_content
    assert "Maintainer: bdapt <bdapt@localhost>" in control_content
    assert "Architecture: all" in control_content


def test_generate_control_file_empty_bundle(bundle_manager: BundleManager):
    """Test control file generation for empty bundle."""
    bundle = Bundle(description="Empty bundle")

    control_content = bundle_manager._generate_control_file("empty", bundle)

    assert "Package: bdapt-empty" in control_content
    assert "Description: Empty bundle" in control_content
    assert "Depends:" not in control_content  # No depends line for empty bundle


def test_get_packages_in_other_bundles(bundle_manager: BundleManager):
    """Test getting packages from other bundles."""
    # Set up test data
    storage = bundle_manager.store.load()
    storage.bundles["web"] = Bundle(
        packages={"nginx": PackageSpec(), "redis": PackageSpec()}
    )
    storage.bundles["dev"] = Bundle(
        packages={"git": PackageSpec(), "vim": PackageSpec()}
    )
    storage.bundles["shared"] = Bundle(
        packages={"curl": PackageSpec(), "nginx": PackageSpec()}
    )
    bundle_manager.store.save(storage)

    # Test excluding different bundles
    packages = bundle_manager._get_packages_in_other_bundles("web")
    assert "git" in packages
    assert "vim" in packages
    assert "curl" in packages
    assert "nginx" in packages  # nginx is in 'shared' bundle
    assert "redis" not in packages  # redis is only in 'web' bundle

    packages = bundle_manager._get_packages_in_other_bundles("nonexistent")
    assert "nginx" in packages
    assert "redis" in packages
    assert "git" in packages
    assert len(packages) == 5  # All packages from all bundles


def test_show_bundle(bundle_manager: BundleManager):
    """Test showing bundle details."""
    # Create test bundle
    storage = bundle_manager.store.load()
    storage.bundles["test"] = Bundle(
        description="Test bundle",
        packages={
            "vim": PackageSpec(),
            "git": PackageSpec(version=">= 2.30"),
        },
    )
    bundle_manager.store.save(storage)

    # This should not raise an exception
    bundle_manager.show_bundle("test")

    # Test non-existent bundle
    with pytest.raises(BundleError, match="Bundle 'nonexistent' does not exist"):
        bundle_manager.show_bundle("nonexistent")


def test_list_bundles_empty(bundle_manager: BundleManager):
    """Test listing bundles when none exist."""
    bundle_manager.list_bundles()  # Should not raise exception


def test_list_bundles(bundle_manager: BundleManager):
    """Test listing bundles."""
    # Create test bundles
    storage = bundle_manager.store.load()
    storage.bundles["web"] = Bundle(
        description="Web services",
        packages={"nginx": PackageSpec(), "postgresql": PackageSpec()},
    )
    storage.bundles["dev"] = Bundle(
        packages={"git": PackageSpec(), "vim": PackageSpec()}
    )
    bundle_manager.store.save(storage)

    # This should not raise an exception
    bundle_manager.list_bundles()

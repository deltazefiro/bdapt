"""Tests for data models."""

from bdapt.models import Bundle, PackageSpec, BundleStorage


def test_package_spec_to_apt_string():
    """Test PackageSpec APT string conversion."""
    # Without version
    spec = PackageSpec()
    assert spec.to_apt_string("nginx") == "nginx"

    # With version
    spec = PackageSpec(version=">= 1.18.0")
    assert spec.to_apt_string("nginx") == "nginx (>= 1.18.0)"


def test_bundle_get_depends_string():
    """Test Bundle depends string generation."""
    bundle = Bundle()
    assert bundle.get_depends_string() == ""

    bundle.packages = {
        "nginx": PackageSpec(),
        "postgresql": PackageSpec(version=">= 12.0"),
        "redis": PackageSpec(),
    }

    depends = bundle.get_depends_string()
    assert "nginx" in depends
    assert "postgresql (>= 12.0)" in depends
    assert "redis" in depends
    assert depends.count(",") == 2  # Two commas for three packages


def test_bundle_storage():
    """Test BundleStorage model."""
    storage = BundleStorage()
    assert storage.bundles == {}

    bundle = Bundle(description="Test bundle", packages={"vim": PackageSpec()})

    storage.bundles["test"] = bundle
    assert "test" in storage.bundles
    assert storage.bundles["test"].description == "Test bundle"

"""Data models for bdapt."""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class PackageSpec(BaseModel):
    """Specification for a package within a bundle."""

    version: Optional[str] = None

    def to_apt_string(self, name: str) -> str:
        """Convert to APT dependency string format."""
        if self.version:
            return f"{name} ({self.version})"
        return name


class Bundle(BaseModel):
    """A bundle of packages."""

    description: str = ""
    packages: Dict[str, PackageSpec] = Field(default_factory=dict)

    def get_depends_string(self) -> str:
        """Get comma-separated APT depends string."""
        return ", ".join(
            spec.to_apt_string(name) for name, spec in self.packages.items()
        )


class BundleStorage(BaseModel):
    """Root storage model for all bundles."""

    bundles: Dict[str, Bundle] = Field(default_factory=dict)

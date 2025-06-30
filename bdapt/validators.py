"""Input validation utilities for bdapt."""

import re
from typing import List

from .exceptions import BundleError


def validate_bundle_name(name: str) -> None:
    """Validate bundle name for use in metapackage names.

    Args:
        name: Bundle name to validate

    Raises:
        BundleError: If name contains invalid characters
    """
    if not name:
        raise BundleError("Bundle name cannot be empty")

    # Single character names must be alphanumeric
    if len(name) == 1:
        if not re.match(r"^[a-z0-9]$", name):
            raise BundleError(
                f"Invalid bundle name '{name}'. Single character names must be lowercase alphanumeric."
            )
        return

    # Multi-character names must follow debian package naming rules
    if not re.match(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$", name):
        raise BundleError(
            f"Invalid bundle name '{name}'. Must contain only lowercase letters, "
            "numbers, dots, and hyphens. Must start and end with alphanumeric."
        )


def validate_package_list(packages: List[str], operation: str = "operation") -> None:
    """Validate that a package list is not empty.

    Args:
        packages: List of package names
        operation: Description of the operation for error messages

    Raises:
        BundleError: If package list is empty
    """
    if not packages:
        raise BundleError(
            f"At least one package must be specified for {operation}")


def validate_package_names(packages: List[str]) -> None:
    """Validate package names follow basic naming conventions.

    Args:
        packages: List of package names to validate

    Raises:
        BundleError: If any package name is invalid
    """
    for pkg in packages:
        if not pkg or not pkg.strip():
            raise BundleError(
                "Package names cannot be empty or whitespace-only")

        # Basic validation - debian package names are quite flexible
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9+.-]*$", pkg.strip()):
            raise BundleError(
                f"Invalid package name '{pkg}'. Package names must start with alphanumeric "
                "and contain only letters, numbers, plus signs, dots, and hyphens."
            )

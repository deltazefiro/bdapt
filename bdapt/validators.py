"""Input validation utilities for bdapt."""

import re
from typing import List

import typer
from .exceptions import ValidationError


def validate_bundle_name(name: str) -> None:
    """Validate bundle name for use in metapackage names.

    Args:
        name: Bundle name to validate

    Exits:
        With code 1 if name contains invalid characters
    """
    if not name:
        raise ValidationError("Bundle name cannot be empty")

    # Single character names must be alphanumeric
    if len(name) == 1:
        if not re.match(r"^[a-z0-9]$", name):
            raise ValidationError(
                f"Invalid bundle name '{name}'. Single character names must be lowercase alphanumeric."
            )
        return

    # Multi-character names must follow debian package naming rules
    if not re.match(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$", name):
        raise ValidationError(
            f"Invalid bundle name '{name}'. Must contain only lowercase letters, numbers, dots, and hyphens, and start/end with alphanumeric characters."
        )


def validate_package_list(packages: List[str], operation: str = "operation") -> None:
    """Validate that a package list is not empty.

    Args:
        packages: List of package names
        operation: Description of the operation for error messages

    Exits:
        With code 1 if package list is empty
    """
    if not packages:
        raise ValidationError(
            f"At least one package must be specified for {operation}"
        )


def validate_package_names(packages: List[str]) -> None:
    """Validate package names follow basic naming conventions.

    Args:
        packages: List of package names to validate

    Exits:
        With code 1 if any package name is invalid
    """
    for pkg in packages:
        if not pkg or not pkg.strip():
            raise ValidationError(
                "Package names cannot be empty or whitespace-only"
            )

        # Basic validation - debian package names are quite flexible
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9+.-]*$", pkg.strip()):
            raise ValidationError(
                f"Invalid package name '{pkg}'. Package names must start with alphanumeric characters and contain only letters, numbers, plus signs, dots, and hyphens."
            )

"""Input validation utilities for bdapt."""

import re
from typing import List

import typer
from rich.console import Console

# Module-level console for error output
_console = Console(stderr=True)


def validate_bundle_name(name: str) -> None:
    """Validate bundle name for use in metapackage names.

    Args:
        name: Bundle name to validate

    Exits:
        With code 1 if name contains invalid characters
    """
    if not name:
        _console.print("[red]Error: Bundle name cannot be empty[/red]")
        raise typer.Exit(1)

    # Single character names must be alphanumeric
    if len(name) == 1:
        if not re.match(r"^[a-z0-9]$", name):
            _console.print(
                f"[red]Error: Invalid bundle name '{name}'. Single character names must be lowercase alphanumeric.[/red]"
            )
            raise typer.Exit(1)
        return

    # Multi-character names must follow debian package naming rules
    if not re.match(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$", name):
        _console.print(
            f"[red]Error: Invalid bundle name '{name}'. Must contain only lowercase letters, "
            "numbers, dots, and hyphens. Must start and end with alphanumeric.[/red]"
        )
        raise typer.Exit(1)


def validate_package_list(packages: List[str], operation: str = "operation") -> None:
    """Validate that a package list is not empty.

    Args:
        packages: List of package names
        operation: Description of the operation for error messages

    Exits:
        With code 1 if package list is empty
    """
    if not packages:
        _console.print(
            f"[red]Error: At least one package must be specified for {operation}[/red]"
        )
        raise typer.Exit(1)


def validate_package_names(packages: List[str]) -> None:
    """Validate package names follow basic naming conventions.

    Args:
        packages: List of package names to validate

    Exits:
        With code 1 if any package name is invalid
    """
    for pkg in packages:
        if not pkg or not pkg.strip():
            _console.print(
                "[red]Error: Package names cannot be empty or whitespace-only[/red]"
            )
            raise typer.Exit(1)

        # Basic validation - debian package names are quite flexible
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9+.-]*$", pkg.strip()):
            _console.print(
                f"[red]Error: Invalid package name '{pkg}'. Package names must start with alphanumeric "
                "and contain only letters, numbers, plus signs, dots, and hyphens.[/red]"
            )
            raise typer.Exit(1)

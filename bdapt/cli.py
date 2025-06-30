"""CLI interface for bdapt."""

import subprocess
import sys
from typing import List, Optional

import typer
from rich.console import Console
from rich.traceback import install

from .bundle_manager import BundleManager
from .storage import BundleStore

# Install rich traceback handler
install(show_locals=True)

# Global state
console = Console()
quiet = False
non_interactive = False

app = typer.Typer(
    name="bdapt",
    help="Bundle APT - Manage groups of APT packages as dependencies",
    add_completion=True,
)


def complete_bundle_name(incomplete: str) -> List[str]:
    """Completion function for bundle names."""
    try:
        store = BundleStore()
        storage = store.load()
        bundle_names = list(storage.bundles.keys())
        return [name for name in bundle_names if name.startswith(incomplete)]
    except Exception:
        # If there's any error, return empty list
        return []


def complete_package_name(incomplete: str) -> List[str]:
    """Completion function for APT package names."""
    try:
        # Use apt-cache to get package names
        # This is a simplified approach - for better performance you might want to cache this
        result = subprocess.run(
            ["apt-cache", "pkgnames", incomplete],
            capture_output=True,
            text=True,
            timeout=3
        )
        if result.returncode == 0:
            packages = result.stdout.strip().split('\n')
            # Filter empty strings and limit results for performance
            packages = [pkg for pkg in packages if pkg][:50]
            return packages
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass
    return []


def complete_bundle_package_name(ctx: typer.Context, incomplete: str) -> List[str]:
    """Completion function for package names within a specific bundle."""
    try:
        # Get the bundle name from the context
        if not ctx.params or 'bundle' not in ctx.params:
            return []

        bundle_name = ctx.params['bundle']
        if not bundle_name:
            return []

        store = BundleStore()
        storage = store.load()

        if bundle_name not in storage.bundles:
            return []

        bundle = storage.bundles[bundle_name]
        package_names = list(bundle.packages.keys())
        return [name for name in package_names if name.startswith(incomplete)]
    except Exception:
        return []


def version_callback(value: bool) -> None:
    """Show version information."""
    if value:
        from . import __version__

        console.print(f"bdapt version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
    quiet_flag: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Minimal output",
    ),
    non_interactive_flag: bool = typer.Option(
        False,
        "-y",
        "--non-interactive",
        help="Skip all confirmation prompts",
    ),
) -> None:
    """bdapt: Bundle APT - Manage groups of APT packages as dependencies."""
    global quiet, non_interactive
    quiet = quiet_flag
    non_interactive = non_interactive_flag

    if quiet:
        console.quiet = True


# Removed handle_errors decorator - using typer.Exit() directly in modules


@app.command()
def new(
    bundle: str = typer.Argument(..., help="Bundle name"),
    packages: List[str] = typer.Argument(
        ..., help="Package names", autocompletion=complete_package_name),
    desc: Optional[str] = typer.Option(
        None,
        "-d",
        "--desc",
        help="Bundle description",
    ),
) -> None:
    """Create and install new bundle."""
    if not packages:
        console.print(
            "[red]Error:[/red] At least one package must be specified")
        raise typer.Exit(1)

    try:
        manager = BundleManager(console=console)
        manager.create_bundle(bundle, packages, desc or "", non_interactive)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled[/yellow]")
        raise typer.Exit(130)


@app.command()
def add(
    bundle: str = typer.Argument(..., help="Bundle name",
                                 autocompletion=complete_bundle_name),
    packages: List[str] = typer.Argument(
        ..., help="Package names to add", autocompletion=complete_package_name),
) -> None:
    """Add packages to a bundle."""
    if not packages:
        console.print(
            "[red]Error:[/red] At least one package must be specified")
        raise typer.Exit(1)

    try:
        manager = BundleManager(console=console)
        manager.add_packages(bundle, packages, non_interactive)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled[/yellow]")
        raise typer.Exit(130)


@app.command()
def rm(
    bundle: str = typer.Argument(..., help="Bundle name",
                                 autocompletion=complete_bundle_name),
    packages: List[str] = typer.Argument(
        ..., help="Package names to remove", autocompletion=complete_bundle_package_name),
    keep_pkg: bool = typer.Option(
        False,
        "--keep-pkg",
        help="Update bundle but keep packages on the system (mark as manual)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force removal of packages from the system, even if manually installed or required by other bundles",
    ),
) -> None:
    """Remove packages from a bundle."""
    if not packages:
        console.print(
            "[red]Error:[/red] At least one package must be specified")
        raise typer.Exit(1)

    try:
        manager = BundleManager(console=console)
        manager.remove_packages(
            bundle, packages, keep_packages=keep_pkg, force=force, non_interactive=non_interactive)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled[/yellow]")
        raise typer.Exit(130)


@app.command(name="del")
def delete(
    bundle: str = typer.Argument(..., help="Bundle name",
                                 autocompletion=complete_bundle_name),
    keep_pkg: bool = typer.Option(
        False,
        "--keep-pkg",
        help="Remove bundle but keep packages (mark as manually installed)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force removal of packages from the system, even if manually installed or required by other bundles",
    ),
) -> None:
    """Delete the bundle."""
    try:
        manager = BundleManager(console=console)
        manager.delete_bundle(bundle, keep_packages=keep_pkg,
                              force=force, non_interactive=non_interactive)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled[/yellow]")
        raise typer.Exit(130)


@app.command()
def ls(
    tree: bool = typer.Option(
        False,
        "--tree",
        help="Show as dependency tree",
    ),
) -> None:
    """List all bundles."""
    try:
        manager = BundleManager(console=console)

        if tree:
            # TODO: Implement tree view
            console.print("[yellow]Tree view not yet implemented[/yellow]")
            return

        manager.list_bundles()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled[/yellow]")
        raise typer.Exit(130)


@app.command()
def show(
    bundle: str = typer.Argument(..., help="Bundle name",
                                 autocompletion=complete_bundle_name),
) -> None:
    """Display bundle contents."""
    try:
        manager = BundleManager(console=console)
        manager.show_bundle(bundle)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled[/yellow]")
        raise typer.Exit(130)


@app.command()
def sync(
    bundle: str = typer.Argument(..., help="Bundle name",
                                 autocompletion=complete_bundle_name),
) -> None:
    """Force reinstall bundle to match definition."""
    try:
        manager = BundleManager(console=console)
        manager.sync_bundle(bundle, non_interactive)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled[/yellow]")
        raise typer.Exit(130)


if __name__ == "__main__":
    app()

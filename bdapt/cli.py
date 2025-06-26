"""CLI interface for bdapt."""

import sys
from typing import List, Optional

import typer
from rich.console import Console
from rich.traceback import install

from .bundle import BundleError, BundleManager
from .storage import StorageError

# Install rich traceback handler
install(show_locals=True)

# Global state
console = Console()
quiet = False
non_interactive = False

app = typer.Typer(
    name="bdapt",
    help="Bundle APT - Manage groups of APT packages as dependencies",
    add_completion=False,
)


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


def handle_errors(func):
    """Decorator to handle common errors."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (BundleError, StorageError) as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled[/yellow]")
            raise typer.Exit(130)
        except Exception as e:
            console.print(f"[red]Unexpected error:[/red] {e}")
            if not quiet:
                console.print_exception()
            raise typer.Exit(1)

    return wrapper


@app.command()
@handle_errors
def new(
    bundle: str = typer.Argument(..., help="Bundle name"),
    packages: List[str] = typer.Argument(..., help="Package names"),
    desc: Optional[str] = typer.Option(
        None,
        "-d",
        "--desc",
        help="Bundle description",
    ),
) -> None:
    """Create and install new bundle."""
    if not packages:
        console.print("[red]Error:[/red] At least one package must be specified")
        raise typer.Exit(1)

    manager = BundleManager(console=console)
    manager.create_bundle(bundle, packages, desc or "")

    # Install dependencies
    if not non_interactive:
        console.print("[yellow]Installing dependencies...[/yellow]")

    try:
        import subprocess

        cmd = ["sudo", "apt", "install", "-f"]
        if non_interactive:
            cmd.append("-y")

        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            console.print(
                "[yellow]Warning:[/yellow] apt install failed. You may need to fix dependencies manually."
            )
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Failed to install dependencies: {e}")


@app.command()
@handle_errors
def add(
    bundle: str = typer.Argument(..., help="Bundle name"),
    packages: List[str] = typer.Argument(..., help="Package names to add"),
) -> None:
    """Add packages to a bundle."""
    if not packages:
        console.print("[red]Error:[/red] At least one package must be specified")
        raise typer.Exit(1)

    manager = BundleManager(console=console)
    manager.add_packages(bundle, packages)

    # Install dependencies
    if not non_interactive:
        console.print("[yellow]Installing dependencies...[/yellow]")

    try:
        import subprocess

        cmd = ["sudo", "apt", "install", "-f"]
        if non_interactive:
            cmd.append("-y")

        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            console.print(
                "[yellow]Warning:[/yellow] apt install failed. You may need to fix dependencies manually."
            )
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Failed to install dependencies: {e}")


@app.command()
@handle_errors
def rm(
    bundle: str = typer.Argument(..., help="Bundle name"),
    packages: List[str] = typer.Argument(..., help="Package names to remove"),
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
        console.print("[red]Error:[/red] At least one package must be specified")
        raise typer.Exit(1)

    manager = BundleManager(console=console)
    manager.remove_packages(bundle, packages, keep_packages=keep_pkg, force=force)


@app.command(name="del")
@handle_errors
def delete(
    bundle: str = typer.Argument(..., help="Bundle name"),
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
    manager = BundleManager(console=console)
    manager.delete_bundle(bundle, keep_packages=keep_pkg, force=force)


@app.command()
@handle_errors
def ls(
    tree: bool = typer.Option(
        False,
        "--tree",
        help="Show as dependency tree",
    ),
) -> None:
    """List all bundles."""
    manager = BundleManager(console=console)

    if tree:
        # TODO: Implement tree view
        console.print("[yellow]Tree view not yet implemented[/yellow]")
        return

    manager.list_bundles()


@app.command()
@handle_errors
def show(
    bundle: str = typer.Argument(..., help="Bundle name"),
) -> None:
    """Display bundle contents."""
    manager = BundleManager(console=console)
    manager.show_bundle(bundle)


@app.command()
@handle_errors
def sync(
    bundle: str = typer.Argument(..., help="Bundle name"),
) -> None:
    """Force reinstall bundle to match definition."""
    manager = BundleManager(console=console)
    manager.sync_bundle(bundle)

    # Install dependencies
    if not non_interactive:
        console.print("[yellow]Installing dependencies...[/yellow]")

    try:
        import subprocess

        cmd = ["sudo", "apt", "install", "-f"]
        if non_interactive:
            cmd.append("-y")

        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            console.print(
                "[yellow]Warning:[/yellow] apt install failed. You may need to fix dependencies manually."
            )
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Failed to install dependencies: {e}")


def main_cli() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main_cli()

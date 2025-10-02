"""CLI interface for bdapt."""

import subprocess
from typing import List, Optional

import typer
from rich.traceback import install

from bdapt.rootlock import aquire_root_and_lock

from . import console as console_module
from .bundle_manager import BundleManager
from .console import console
from .storage import BundleStore

# Install rich traceback handler
install(show_locals=True)

app = typer.Typer(
    name="bdapt",
    help="Bundle APT: Manage multiple Debian APT packages as groups.",
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


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
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
    console_module.quiet = quiet_flag
    console_module.non_interactive = non_interactive_flag

    if quiet_flag:
        console.quiet = True

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


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
    ignore_errors: bool = typer.Option(
        False,
        "-f",
        "--ignore-errors",
        help="Ignore errors",
    ),
) -> None:
    """Create and install new bundle."""
    if not packages:
        console.print(
            "[red]Error:[/red] At least one package must be specified")
        raise typer.Exit(1)

    aquire_root_and_lock()
    manager = BundleManager()
    manager.create_bundle(bundle, packages, desc or "",
                          ignore_errors=ignore_errors)


@app.command()
def add(
    bundle: str = typer.Argument(..., help="Bundle name",
                                 autocompletion=complete_bundle_name),
    packages: List[str] = typer.Argument(
        ..., help="Package names to add", autocompletion=complete_package_name),
    ignore_errors: bool = typer.Option(
        False,
        "-f",
        "--ignore-errors",
        help="Ignore errors",
    ),
) -> None:
    """Add packages to a bundle."""
    if not packages:
        console.print(
            "[red]Error:[/red] At least one package must be specified")
        raise typer.Exit(1)

    aquire_root_and_lock()
    manager = BundleManager()
    manager.add_packages(bundle, packages, ignore_errors=ignore_errors)


@app.command()
def rm(
    bundle: str = typer.Argument(..., help="Bundle name",
                                 autocompletion=complete_bundle_name),
    packages: List[str] = typer.Argument(
        ..., help="Package names to remove", autocompletion=complete_bundle_package_name),
    ignore_errors: bool = typer.Option(
        False,
        "-f",
        "--ignore-errors",
        help="Ignore errors",
    ),
) -> None:
    """Remove packages from a bundle."""
    if not packages:
        console.print(
            "[red]Error:[/red] At least one package must be specified")
        raise typer.Exit(1)

    aquire_root_and_lock()
    manager = BundleManager()
    manager.remove_packages(bundle, packages, ignore_errors=ignore_errors)


@app.command(name="del")
def delete(
    bundle: str = typer.Argument(..., help="Bundle name",
                                 autocompletion=complete_bundle_name),
    ignore_errors: bool = typer.Option(
        False,
        "-f",
        "--ignore-errors",
        help="Ignore errors",
    ),
) -> None:
    """Delete the bundle."""
    aquire_root_and_lock()
    manager = BundleManager()
    manager.delete_bundle(bundle, ignore_errors=ignore_errors)


@app.command()
def ls(
    tree: bool = typer.Option(
        False,
        "-t",
        "--tree",
        help="Show as dependency tree",
    ),
) -> None:
    """List all bundles."""
    manager = BundleManager()
    manager.list_bundles(tree=tree)


@app.command()
def show(
    bundle: str = typer.Argument(..., help="Bundle name",
                                 autocompletion=complete_bundle_name),
) -> None:
    """Display bundle contents."""
    manager = BundleManager()
    manager.show_bundle(bundle)


@app.command()
def sync(
    bundle: str = typer.Argument(..., help="Bundle name",
                                 autocompletion=complete_bundle_name),
    ignore_errors: bool = typer.Option(
        False,
        "-f",
        "--ignore-errors",
        help="Ignore errors",
    ),
) -> None:
    """Force reinstall bundle to match definition."""
    aquire_root_and_lock()
    manager = BundleManager()
    manager.sync_bundle(bundle, ignore_errors=ignore_errors)


if __name__ == "__main__":
    app()

"""CLI interface for bdapt."""

import functools
import subprocess
import sys
from typing import List, Optional

import typer
from rich.console import Console
from rich.traceback import install

from .bundle_manager import BundleManager
from .exceptions import BundleError, StorageError
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


def handle_errors(func):
    """Decorator to handle common errors."""

    @functools.wraps(func)
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

    manager = BundleManager(console=console)
    manager.create_bundle(bundle, packages, desc or "", non_interactive)


@app.command()
@handle_errors
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

    manager = BundleManager(console=console)
    manager.add_packages(bundle, packages, non_interactive)


@app.command()
@handle_errors
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

    manager = BundleManager(console=console)
    manager.remove_packages(
        bundle, packages, keep_packages=keep_pkg, force=force, non_interactive=non_interactive)


@app.command(name="del")
@handle_errors
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
    manager = BundleManager(console=console)
    manager.delete_bundle(bundle, keep_packages=keep_pkg,
                          force=force, non_interactive=non_interactive)


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
    bundle: str = typer.Argument(..., help="Bundle name",
                                 autocompletion=complete_bundle_name),
) -> None:
    """Display bundle contents."""
    manager = BundleManager(console=console)
    manager.show_bundle(bundle)


@app.command()
@handle_errors
def sync(
    bundle: str = typer.Argument(..., help="Bundle name",
                                 autocompletion=complete_bundle_name),
) -> None:
    """Force reinstall bundle to match definition."""
    manager = BundleManager(console=console)
    manager.sync_bundle(bundle, non_interactive)


@app.command(name="completion")
def completion(
    shell: str = typer.Argument(
        ...,
        help="Shell to generate completion for (bash, zsh, fish, powershell)",
    ),
) -> None:
    """Show instructions for enabling shell completion."""
    if shell == "bash":
        console.print("[yellow]To enable bash completion for bdapt:[/yellow]")
        console.print("1. Install bash-completion if not already installed:")
        console.print("   sudo apt install bash-completion  # Ubuntu/Debian")
        console.print("   sudo yum install bash-completion  # CentOS/RHEL")
        console.print("\n2. Add the following to your ~/.bashrc:")
        console.print("   eval \"$(_BDAPT_COMPLETE=bash_source bdapt)\"")
        console.print("\n3. Restart your shell or run: source ~/.bashrc")
    elif shell == "zsh":
        console.print("[yellow]To enable zsh completion for bdapt:[/yellow]")
        console.print("Add the following to your ~/.zshrc:")
        console.print("   eval \"$(_BDAPT_COMPLETE=zsh_source bdapt)\"")
        console.print("\nThen restart your shell or run: source ~/.zshrc")
    elif shell == "fish":
        console.print("[yellow]To enable fish completion for bdapt:[/yellow]")
        console.print("Run the following command:")
        console.print("   eval (env _BDAPT_COMPLETE=fish_source bdapt)")
        console.print("\nOr add it to your ~/.config/fish/config.fish")
    elif shell == "powershell":
        console.print(
            "[yellow]To enable PowerShell completion for bdapt:[/yellow]")
        console.print("Add the following to your PowerShell profile:")
        console.print(
            "   Register-ArgumentCompleter -Native -CommandName bdapt -ScriptBlock {")
        console.print(
            "       param($commandName, $wordToComplete, $cursorPosition)")
        console.print("       $env:_BDAPT_COMPLETE = 'powershell_complete'")
        console.print("       $env:COMP_WORDS = $wordToComplete")
        console.print("       $env:COMP_CWORD = $cursorPosition")
        console.print("       bdapt 2>&1 | ForEach-Object {")
        console.print("           if ($_ -match '^([^\\t]+)\\t(.*)') {")
        console.print(
            "               [System.Management.Automation.CompletionResult]::new($matches[1], $matches[1], 'ParameterValue', $matches[2])")
        console.print("           }")
        console.print("       }")
        console.print("   }")
    else:
        console.print(f"[red]Error:[/red] Unsupported shell: {shell}")
        console.print(
            "[yellow]Supported shells:[/yellow] bash, zsh, fish, powershell")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

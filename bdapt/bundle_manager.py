"""High-level bundle management operations."""

from typing import List, Optional

import typer
from rich.console import Console

from .apt_operations import AptCommandRunner
from .exceptions import CommandError
from .metapackage import MetapackageContext
from .models import Bundle, PackageSpec
from .storage import BundleStore
from .validators import (
    validate_bundle_name,
    validate_package_list,
    validate_package_names,
)


class BundleManager:
    """Manages high-level bundle operations."""

    def __init__(
        self,
        store: Optional[BundleStore] = None,
        console: Optional[Console] = None
    ):
        """Initialize the bundle manager.

        Args:
            store: Bundle storage instance
            console: Rich console for output
        """
        self.store = store or BundleStore()
        self.console = console or Console()
        self.apt_runner = AptCommandRunner(self.console)

    def _dry_run_operation(self, package_spec: str, ignore_errors: bool = False) -> Optional[str]:
        """Run apt dry-run and return summary.
        """
        try:
            return self.apt_runner.run_apt_dry_run([package_spec])
        except KeyboardInterrupt:
            self.console.print("[red]Dry-run interrupted by user.[/red]")
            raise typer.Exit(130)
        except CommandError as e:
            if ignore_errors:
                self.console.print(
                    "[yellow]Dry-run failed, but ignoring errors.[/yellow]")
                return
            self.console.print(f"[red]Dry-run failed: {e}[/red]")
            raise typer.Exit(130)

    def _confirm_operation(self, summary: str) -> None:
        self.console.print("[yellow]Package Changes:[/yellow]\n")
        self.console.print(summary)

        response = input(
            "\nProceed with these changes? [y/N]: ").strip().lower()

        if response not in ('y', 'yes'):
            self.console.print(
                "[red]Operation cancelled by user.[/red]")
            raise typer.Exit(130)

    def _install_metapackage(
        self,
        bundle_name: str,
        bundle: Bundle,
        non_interactive: bool = False,
        ignore_errors: bool = False
    ) -> None:
        """Create and install a metapackage for the given bundle.

        Performs: dry-run → confirmation → installation
        """
        metapackage_ctx = MetapackageContext(
            bundle_name, bundle, self.apt_runner)

        with metapackage_ctx as deb_file:
            # Dry-run to preview changes
            summary = self._dry_run_operation(str(deb_file), ignore_errors)

            # Confirm with user unless non-interactive or no changes
            if summary and not non_interactive:
                self._confirm_operation(summary)

            # Update bundle in store
            storage = self.store.load()
            storage.bundles[bundle_name] = bundle
            self.store.save(storage)

            # Install the metapackage
            try:
                self.apt_runner.run_apt_install([str(deb_file)])
            except KeyboardInterrupt:
                self.console.print("\n[red]Install interrupted by user.[/red]\n"
                                   f"[yellow]The system may be in an inconsistent state. Run [bold]bdapt sync {bundle_name}[/bold] to fix it.[/yellow]")
                raise typer.Exit(130)
            except CommandError as e:
                if ignore_errors:
                    self.console.print(
                        "[yellow]Install failed, but ignoring errors.[/yellow]")
                else:
                    self.console.print(f"[red]Install failed: {e}\n"
                                       f"[yellow]The system may be in an inconsistent state. Run [bold]bdapt sync {bundle_name}[/bold] to fix it.[/yellow]")
                    raise typer.Exit(130)

    def _remove_metapackage(
        self,
        bundle_name: str,
        non_interactive: bool = False,
        ignore_errors: bool = False
    ) -> None:
        """Remove a metapackage from the system.
        """
        metapackage_name = MetapackageContext.get_metapackage_name(bundle_name)
        package_spec = metapackage_name + "-"  # APT syntax to remove package

        # Dry-run to preview changes
        summary = self._dry_run_operation(package_spec, ignore_errors)

        # Confirm with user unless non-interactive or no changes
        if summary and not non_interactive:
            self._confirm_operation(summary)

        # Execute the removal
        try:
            self.apt_runner.run_apt_install([package_spec])
        except KeyboardInterrupt:
            self.console.print("\n[red]Removal interrupted by user.[/red]\n"
                               "[yellow]The system may be in an inconsistent state. "
                               f"Run [bold]bdapt sync {bundle_name}[/bold] to rollback or [bold]bdapt del {bundle_name}[/bold] to try again.[/yellow]")
            raise typer.Exit(130)
        except CommandError as e:
            if ignore_errors:
                self.console.print(
                    "[yellow]Removal failed, but ignoring errors.[/yellow]")
            else:
                self.console.print(f"[red]Removal failed: {e}\n"
                                   "[yellow]The system may be in an inconsistent state. "
                                   f"Run [bold]bdapt sync {bundle_name}[/bold] to rollback or [bold]bdapt del -f {bundle_name}[/bold] to force removal.[/yellow]")
                raise typer.Exit(130)

        # Update bundle in store
        storage = self.store.load()
        del storage.bundles[bundle_name]
        self.store.save(storage)

    def create_bundle(
        self,
        name: str,
        packages: List[str],
        description: str = "",
        ignore_errors: bool = False,
        non_interactive: bool = False
    ) -> None:
        """Create a new bundle.
        """
        validate_bundle_name(name)
        validate_package_list(packages, "bundle creation")
        validate_package_names(packages)

        storage = self.store.load()

        if name in storage.bundles:
            self.console.print(
                f"[red]Error: Bundle '{name}' already exists[/red]")
            raise typer.Exit(1)

        bundle = Bundle(
            description=description,
            packages={pkg: PackageSpec() for pkg in packages}
        )

        self._install_metapackage(name, bundle, non_interactive, ignore_errors)

        # Save bundle after successful installation
        storage.bundles[name] = bundle
        self.store.save(storage)

        self.console.print(f"[green]✓[/green] Created bundle '{name}'")

    def add_packages(
        self,
        bundle_name: str,
        packages: List[str],
        ignore_errors: bool = False,
        non_interactive: bool = False
    ) -> None:
        """Add packages to an existing bundle.
        """
        validate_package_list(packages, "adding packages")
        validate_package_names(packages)

        storage = self.store.load()

        if bundle_name not in storage.bundles:
            self.console.print(
                f"[red]Error: Bundle '{bundle_name}' does not exist[/red]")
            raise typer.Exit(1)

        bundle = storage.bundles[bundle_name]

        # Add new packages (TODO: Parse version spec)
        for pkg in packages:
            bundle.packages[pkg] = PackageSpec()

        self._install_metapackage(
            bundle_name, bundle, non_interactive, ignore_errors)

        # Save bundle after successful installation
        self.store.save(storage)

        self.console.print(
            f"[green]✓[/green] Added {len(packages)} package{len(packages) != 1 and 's' or ''} to bundle '{bundle_name}'")

    def remove_packages(
        self,
        bundle_name: str,
        packages: List[str],
        non_interactive: bool = False,
        ignore_errors: bool = False,
    ) -> None:
        """Remove packages from a bundle.
        """
        validate_package_list(packages, "removing packages")

        storage = self.store.load()

        if bundle_name not in storage.bundles:
            self.console.print(
                f"[red]Error: Bundle '{bundle_name}' does not exist[/red]")
            raise typer.Exit(1)

        bundle = storage.bundles[bundle_name]

        # Verify packages exist in bundle
        for pkg in packages:
            if pkg not in bundle.packages:
                self.console.print(
                    f"[red]Error: Package '{pkg}' not in bundle '{bundle_name}'[/red]")
                raise typer.Exit(1)

        # Remove packages from bundle definition
        for pkg in packages:
            del bundle.packages[pkg]

        self._install_metapackage(
            bundle_name, bundle, non_interactive, ignore_errors)

        # Save bundle after successful installation
        self.store.save(storage)

        self.console.print(
            f"[green]✓[/green] Removed {len(packages)} package{len(packages) != 1 and 's' or ''} from bundle '{bundle_name}'")

    def delete_bundle(
        self,
        bundle_name: str,
        non_interactive: bool = False,
        ignore_errors: bool = False,
    ) -> None:
        """Delete a bundle completely.
        """
        storage = self.store.load()

        if bundle_name not in storage.bundles:
            self.console.print(
                f"[red]Error: Bundle '{bundle_name}' does not exist[/red]")
            raise typer.Exit(1)

        # Remove metapackage
        self._remove_metapackage(bundle_name, non_interactive, ignore_errors)

        # Remove from storage
        del storage.bundles[bundle_name]
        self.store.save(storage)

        self.console.print(f"[green]✓[/green] Deleted bundle '{bundle_name}'")

    def sync_bundle(
        self,
        bundle_name: str,
        non_interactive: bool = False,
        ignore_errors: bool = False
    ) -> None:
        """Force reinstall bundle to match definition.
        """
        storage = self.store.load()

        if bundle_name not in storage.bundles:
            self.console.print(
                f"[red]Error: Bundle '{bundle_name}' does not exist[/red]")
            raise typer.Exit(1)

        bundle = storage.bundles[bundle_name]

        self._install_metapackage(
            bundle_name, bundle, non_interactive, ignore_errors)

        self.console.print(f"[green]✓[/green] Synced bundle '{bundle_name}'")

    def list_bundles(self) -> None:
        """List all bundles."""
        storage = self.store.load()

        if not storage.bundles:
            self.console.print("[yellow]No bundles found[/yellow]")
            return

        for name, bundle in storage.bundles.items():
            pkg_count = len(bundle.packages)
            desc = f" [dim]{bundle.description}[/dim]" if bundle.description else ""
            self.console.print(
                f"[bold]{name}[/bold] ({pkg_count} package{pkg_count != 1 and 's' or ''}){desc}")

    def show_bundle(self, bundle_name: str) -> None:
        """Display detailed information about a bundle.

        Args:
            bundle_name: Name of the bundle to show

        Raises:
            typer.Exit: If bundle doesn't exist
        """
        storage = self.store.load()

        if bundle_name not in storage.bundles:
            self.console.print(
                f"[red]Error: Bundle '{bundle_name}' does not exist[/red]")
            raise typer.Exit(1)

        bundle = storage.bundles[bundle_name]

        self.console.print(f"[bold]Bundle:[/bold] {bundle_name}")
        desc = bundle.description or "[dim]No description[/dim]"
        self.console.print(f"[bold]Description:[/bold] {desc}")

        if bundle.packages:
            self.console.print(
                f"[bold]Packages ({len(bundle.packages)}):[/bold]")
            for pkg_name in sorted(bundle.packages.keys()):
                self.console.print(f"  • {pkg_name}")
        else:
            self.console.print("[yellow]No packages in bundle[/yellow]")

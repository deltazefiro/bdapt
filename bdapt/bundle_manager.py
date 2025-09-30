"""High-level bundle management operations."""

from typing import List, Optional, Set

import typer
from rich.console import Console

from .apt_operations import AptCommandRunner
from .exceptions import BdaptError
from .metapackage import MetapackageManager
from .models import Bundle, PackageSpec
from .storage import BundleStorage, BundleStore
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
        self.metapackage_manager = MetapackageManager(self.console)

    def _sync_bundle(
        self,
        bundle_name: str,
        bundle: Bundle,
        storage: "BundleStorage",
        non_interactive: bool = False,
        ignore_errors: bool = False,
        is_new_bundle: bool = False
    ) -> None:
        """Sync a bundle with the system.

        Follows the order specified in IMPL.md:
        1. Build metapackage and dry-run
        2. Get confirmation
        3. Update bundle in storage
        4. Run apt install
        """
        try:
            # Phase 1: Build, dry-run, and get confirmation
            result = self.metapackage_manager.prepare_metapackage_install(
                bundle_name, bundle, non_interactive, ignore_errors
            )

            # If no changes are needed or errors are being ignored, return early
            if result is None:
                return

            deb_file, temp_dir = result

            # Phase 2: Update bundle in storage (after confirmation, before install)
            if is_new_bundle:
                storage.bundles[bundle_name] = bundle
            self.store.save(storage)

            # Phase 3: Complete the installation
            self.metapackage_manager.complete_metapackage_install(
                deb_file, temp_dir, ignore_errors
            )
        except BdaptError as e:
            if not e.displayed:
                self.console.print(f"[red]Error: {e.message}[/red]")
            raise typer.Exit(e.exit_code)

    def create_bundle(
        self,
        name: str,
        packages: List[str],
        description: str = "",
        ignore_errors: bool = False,
        non_interactive: bool = False
    ) -> None:
        """Create a new bundle.

        Args:
            name: Bundle name
            packages: List of package names
            description: Bundle description
            non_interactive: If True, run apt commands non-interactively

        Exits:
            With code 1 if bundle creation fails
        """
        # Validate inputs
        validate_bundle_name(name)
        validate_package_list(packages, "bundle creation")
        validate_package_names(packages)

        try:
            storage = self.store.load()

            if name in storage.bundles:
                self.console.print(
                    f"[red]Error: Bundle '{name}' already exists[/red]")
                raise typer.Exit(1)

            # Create bundle definition
            bundle = Bundle(
                description=description,
                packages={pkg: PackageSpec() for pkg in packages}
            )

            self._sync_bundle(
                name, bundle, storage, non_interactive, ignore_errors, is_new_bundle=True)
            self.console.print(f"[green]✓[/green] Created bundle '{name}'")
        except BdaptError as e:
            if not e.displayed:
                self.console.print(f"[red]Error: {e.message}[/red]")
            raise typer.Exit(e.exit_code)

    def add_packages(
        self,
        bundle_name: str,
        packages: List[str],
        ignore_errors: bool = False,
        non_interactive: bool = False
    ) -> None:
        """Add packages to an existing bundle.

        Args:
            bundle_name: Name of the bundle
            packages: List of package names to add
            ignore_errors: If True, ignore errors
            non_interactive: If True, run apt commands non-interactively

        Exits:
            With code 1 if operation fails
        """
        try:
            # Validate inputs
            validate_package_list(packages, "adding packages")
            validate_package_names(packages)

            storage = self.store.load()

            if bundle_name not in storage.bundles:
                self.console.print(
                    f"[red]Error: Bundle '{bundle_name}' does not exist[/red]")
                raise typer.Exit(1)

            bundle = storage.bundles[bundle_name]

            # Add new packages
            # TODO: Parse pkg version spec
            for pkg in packages:
                bundle.packages[pkg] = PackageSpec()

            self._sync_bundle(
                bundle_name, bundle, storage, non_interactive, ignore_errors)
            self.console.print(
                f"[green]✓[/green] Added packages to bundle '{bundle_name}'"
            )
        except BdaptError as e:
            if not e.displayed:
                self.console.print(f"[red]Error: {e.message}[/red]")
            raise typer.Exit(e.exit_code)

    def remove_packages(
        self,
        bundle_name: str,
        packages: List[str],
        non_interactive: bool = False,
        ignore_errors: bool = False,
    ) -> None:
        """Remove packages from a bundle.

        Args:
            bundle_name: Name of the bundle
            packages: List of package names to remove
            non_interactive: If True, run apt commands non-interactively
            ignore_errors: If True, ignore errors

        Exits:
            With code 1 if operation fails
        """
        try:
            # Validate inputs
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
                        f"[red]Error: Package '{pkg}' not in bundle '{bundle_name}'[/red]"
                    )
                    raise typer.Exit(1)

            # Remove packages from bundle definition
            for pkg in packages:
                del bundle.packages[pkg]

            # Update metapackage first
            self._sync_bundle(
                bundle_name, bundle, storage, non_interactive, ignore_errors)

            self.console.print(
                f"[green]✓[/green] Removed packages from bundle '{bundle_name}'"
            )
        except BdaptError as e:
            if not e.displayed:
                self.console.print(f"[red]Error: {e.message}[/red]")
            raise typer.Exit(e.exit_code)

    def delete_bundle(
        self,
        bundle_name: str,
        non_interactive: bool = False,
        ignore_errors: bool = False,
    ) -> None:
        """Delete a bundle completely.

        Args:
            bundle_name: Name of the bundle to delete
            non_interactive: If True, run apt commands non-interactively

        Exits:
            With code 1 if operation fails
        """
        try:
            storage = self.store.load()

            if bundle_name not in storage.bundles:
                self.console.print(
                    f"[red]Error: Bundle '{bundle_name}' does not exist[/red]")
                raise typer.Exit(1)

            # Remove metapackage
            self.metapackage_manager.remove_metapackage(
                bundle_name, non_interactive, ignore_errors)

            # Remove from storage
            del storage.bundles[bundle_name]
            self.store.save(storage)

            self.console.print(
                f"[green]✓[/green] Deleted bundle '{bundle_name}'")

        except BdaptError as e:
            if not e.displayed:
                self.console.print(f"[red]Error: {e.message}[/red]")
            raise typer.Exit(e.exit_code)
        except Exception as e:
            self.console.print(
                f"[red]Error: Failed to delete bundle: {e}[/red]")
            raise typer.Exit(1)

    def sync_bundle(self, bundle_name: str, non_interactive: bool = False, ignore_errors: bool = False) -> None:
        """Force reinstall bundle to match definition.

        Args:
            bundle_name: Name of the bundle to sync
            non_interactive: If True, run apt commands non-interactively
            ignore_errors: If True, ignore errors

        Exits:
            With code 1 if operation fails
        """
        try:
            storage = self.store.load()

            if bundle_name not in storage.bundles:
                self.console.print(
                    f"[red]Error: Bundle '{bundle_name}' does not exist[/red]")
                raise typer.Exit(1)

            bundle = storage.bundles[bundle_name]

            self._sync_bundle(
                bundle_name, bundle, storage, non_interactive, ignore_errors)

            self.console.print(
                f"[green]✓[/green] Synced bundle '{bundle_name}'"
            )
        except BdaptError as e:
            if not e.displayed:
                self.console.print(f"[red]Error: {e.message}[/red]")
            raise typer.Exit(e.exit_code)

    def list_bundles(self) -> None:
        """List all bundles."""
        try:
            storage = self.store.load()

            if not storage.bundles:
                self.console.print("[yellow]No bundles found[/yellow]")
                return

            for name, bundle in storage.bundles.items():
                pkg_count = len(bundle.packages)
                self.console.print(
                    f"[bold]{name}[/bold] ({pkg_count} packages) [dim]{bundle.description or ''}[/dim]")
        except BdaptError as e:
            if not e.displayed:
                self.console.print(f"[red]Error: {e.message}[/red]")
            raise typer.Exit(e.exit_code)

    def show_bundle(self, bundle_name: str) -> None:
        """Display detailed information about a bundle.

        Args:
            bundle_name: Name of the bundle to show

        Exits:
            With code 1 if bundle doesn't exist
        """
        try:
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
        except BdaptError as e:
            if not e.displayed:
                self.console.print(f"[red]Error: {e.message}[/red]")
            raise typer.Exit(e.exit_code)

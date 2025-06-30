"""High-level bundle management operations."""

from typing import List, Optional, Set

from rich.console import Console

from .apt_operations import AptCommandRunner
from .exceptions import BundleError, MetapackageError
from .metapackage import MetapackageManager
from .models import Bundle, PackageSpec
from .storage import BundleStorage, BundleStore, StorageError
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
        is_new_bundle: bool = False
    ) -> None:
        """Sync a bundle with the system."""
        try:
            confirmed = self.metapackage_manager.install_metapackage(
                bundle_name, bundle, non_interactive
            )

            if confirmed:
                if is_new_bundle:
                    storage.bundles[bundle_name] = bundle
                self.store.save(storage)
            else:
                # This is raised when the user cancels the operation.
                raise BundleError(
                    f"Operation for bundle '{bundle_name}' cancelled by user.")

        except MetapackageError as e:
            # Metapackage errors are critical and should not result in a saved state change.
            raise BundleError(
                f"Failed to process metapackage for bundle '{bundle_name}': {e}") from e

    def create_bundle(
        self,
        name: str,
        packages: List[str],
        description: str = "",
        non_interactive: bool = False
    ) -> None:
        """Create a new bundle.

        Args:
            name: Bundle name
            packages: List of package names
            description: Bundle description
            non_interactive: If True, run apt commands non-interactively

        Raises:
            BundleError: If bundle creation fails
        """
        # Validate inputs
        validate_bundle_name(name)
        validate_package_list(packages, "bundle creation")
        validate_package_names(packages)

        storage = self.store.load()

        if name in storage.bundles:
            raise BundleError(f"Bundle '{name}' already exists")

        # Create bundle definition
        bundle = Bundle(
            description=description,
            packages={pkg: PackageSpec() for pkg in packages}
        )

        self._sync_bundle(
            name, bundle, storage, non_interactive, is_new_bundle=True)
        self.console.print(f"[green]✓[/green] Created bundle '{name}'")

    def add_packages(
        self,
        bundle_name: str,
        packages: List[str],
        non_interactive: bool = False
    ) -> None:
        """Add packages to an existing bundle.

        Args:
            bundle_name: Name of the bundle
            packages: List of package names to add
            non_interactive: If True, run apt commands non-interactively

        Raises:
            BundleError: If operation fails
        """
        # Validate inputs
        validate_package_list(packages, "adding packages")
        validate_package_names(packages)

        storage = self.store.load()

        if bundle_name not in storage.bundles:
            raise BundleError(f"Bundle '{bundle_name}' does not exist")

        bundle = storage.bundles[bundle_name]

        # Add new packages
        # TODO: Parse pkg version spec
        for pkg in packages:
            bundle.packages[pkg] = PackageSpec()

        self._sync_bundle(
            bundle_name, bundle, storage, non_interactive)
        self.console.print(
            f"[green]✓[/green] Added packages to bundle '{bundle_name}'"
        )

    def remove_packages(
        self,
        bundle_name: str,
        packages: List[str],
        keep_packages: bool = False,
        force: bool = False,
        non_interactive: bool = False,
    ) -> None:
        """Remove packages from a bundle.

        Args:
            bundle_name: Name of the bundle
            packages: List of package names to remove
            keep_packages: If True, keep packages on system (mark as manual)
            force: If True, force removal even if in other bundles or manually installed
            non_interactive: If True, run apt commands non-interactively

        Raises:
            BundleError: If operation fails
        """
        # Validate inputs
        validate_package_list(packages, "removing packages")

        storage = self.store.load()

        if bundle_name not in storage.bundles:
            raise BundleError(f"Bundle '{bundle_name}' does not exist")

        bundle = storage.bundles[bundle_name]

        # Verify packages exist in bundle
        for pkg in packages:
            if pkg not in bundle.packages:
                raise BundleError(
                    f"Package '{pkg}' not in bundle '{bundle_name}'")

        # Remove packages from bundle definition
        for pkg in packages:
            del bundle.packages[pkg]

        # Update metapackage first
        self._sync_bundle(
            bundle_name, bundle, storage, non_interactive)

        self.console.print(
            f"[green]✓[/green] Removed packages from bundle '{bundle_name}'"
        )

    def delete_bundle(
        self,
        bundle_name: str,
        keep_packages: bool = False,
        force: bool = False,
        non_interactive: bool = False
    ) -> None:
        """Delete a bundle completely.

        Args:
            bundle_name: Name of the bundle to delete
            keep_packages: If True, keep packages on system (mark as manual)
            force: If True, force removal even if in other bundles or manually installed
            non_interactive: If True, run apt commands non-interactively

        Raises:
            BundleError: If operation fails
        """
        storage = self.store.load()

        if bundle_name not in storage.bundles:
            raise BundleError(f"Bundle '{bundle_name}' does not exist")

        try:
            # Remove metapackage
            confirmed = self.metapackage_manager.remove_metapackage(
                bundle_name, non_interactive)
            if not confirmed:
                raise BundleError(
                    f"Deletion of bundle '{bundle_name}' cancelled by user.")

            # Remove from storage
            del storage.bundles[bundle_name]
            self.store.save(storage)

            self.console.print(
                f"[green]✓[/green] Deleted bundle '{bundle_name}'")

        except Exception as e:
            raise BundleError(f"Failed to delete bundle: {e}") from e

    def sync_bundle(self, bundle_name: str, non_interactive: bool = False) -> None:
        """Force reinstall bundle to match definition.

        Args:
            bundle_name: Name of the bundle to sync
            non_interactive: If True, run apt commands non-interactively

        Raises:
            BundleError: If operation fails
        """
        storage = self.store.load()

        if bundle_name not in storage.bundles:
            raise BundleError(f"Bundle '{bundle_name}' does not exist")

        bundle = storage.bundles[bundle_name]

        self._sync_bundle(
            bundle_name, bundle, storage, non_interactive)
        self.console.print(
            f"[green]✓[/green] Synced bundle '{bundle_name}'")

    def list_bundles(self) -> None:
        """List all bundles."""
        storage = self.store.load()

        if not storage.bundles:
            self.console.print("[yellow]No bundles found[/yellow]")
            return

        for name, bundle in storage.bundles.items():
            desc = f" - {bundle.description}" if bundle.description else ""
            pkg_count = len(bundle.packages)
            self.console.print(
                f"[blue]{name}[/blue]{desc} ({pkg_count} packages)"
            )

    def show_bundle(self, bundle_name: str) -> None:
        """Show bundle details.

        Args:
            bundle_name: Name of the bundle to show

        Raises:
            BundleError: If bundle doesn't exist
        """
        storage = self.store.load()

        if bundle_name not in storage.bundles:
            raise BundleError(f"Bundle '{bundle_name}' does not exist")

        bundle = storage.bundles[bundle_name]

        self.console.print(f"[blue]Bundle: {bundle_name}[/blue]")
        if bundle.description:
            self.console.print(f"Description: {bundle.description}")

        if bundle.packages:
            self.console.print("Packages:")
            for pkg, spec in bundle.packages.items():
                version_info = f" ({spec.version})" if spec.version else ""
                self.console.print(f"  • {pkg}{version_info}")
        else:
            self.console.print("[yellow]No packages in bundle[/yellow]")

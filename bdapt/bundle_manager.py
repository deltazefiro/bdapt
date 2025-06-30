"""High-level bundle management operations."""

from typing import List, Optional, Set

from rich.console import Console

from .apt_operations import AptCommandRunner
from .exceptions import BundleError
from .metapackage import MetapackageManager
from .models import Bundle, PackageSpec
from .storage import BundleStore, StorageError
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

    def _get_packages_in_other_bundles(self, exclude_bundle: str) -> Set[str]:
        """Get set of packages that are in other bundles.

        Args:
            exclude_bundle: Bundle name to exclude from search

        Returns:
            Set of package names
        """
        storage = self.store.load()
        packages = set()

        for name, bundle in storage.bundles.items():
            if name != exclude_bundle:
                packages.update(bundle.packages.keys())

        return packages

    def _determine_packages_to_remove(
        self,
        packages: List[str],
        exclude_bundle: str,
        force: bool = False
    ) -> List[str]:
        """Determine which packages can be safely removed from the system.

        Args:
            packages: List of package names to consider for removal
            exclude_bundle: Bundle name to exclude from other bundle checks
            force: If True, ignore safety checks

        Returns:
            List of packages that can be removed
        """
        if force:
            return packages

        other_bundle_packages = self._get_packages_in_other_bundles(
            exclude_bundle)
        packages_to_remove = []

        for pkg in packages:
            if pkg in other_bundle_packages:
                self.console.print(
                    f"[yellow]Keeping '{pkg}' (required by other bundles)[/yellow]"
                )
                continue

            if self.apt_runner.is_package_manually_installed(pkg):
                self.console.print(
                    f"[yellow]Keeping '{pkg}' (manually installed)[/yellow]"
                )
                continue

            packages_to_remove.append(pkg)

        return packages_to_remove

    def _handle_package_removal(
        self,
        packages: List[str],
        exclude_bundle: str,
        keep_packages: bool = False,
        force: bool = False,
        non_interactive: bool = False
    ) -> None:
        """Handle removal of packages from the system.

        Args:
            packages: List of package names to remove
            exclude_bundle: Bundle name to exclude from other bundle checks
            keep_packages: If True, don't remove packages from system
            force: If True, force removal even if in other bundles or manually installed
            non_interactive: If True, run apt commands non-interactively
        """
        if keep_packages:
            return

        packages_to_remove = self._determine_packages_to_remove(
            packages, exclude_bundle, force
        )

        if packages_to_remove:
            success = self.apt_runner.remove_packages(
                packages_to_remove, non_interactive)
            if not success:
                self.console.print(
                    "[yellow]Package removal cancelled or failed. "
                    "Bundle definition updated. Run 'sudo apt autoremove' to remove unused packages.[/yellow]"
                )

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

        try:
            # Install metapackage first - only save to storage if successful
            self.metapackage_manager.install_metapackage(
                name, bundle, non_interactive)

            # Add to storage only after successful installation
            storage.bundles[name] = bundle
            self.store.save(storage)
            self.console.print(f"[green]✓[/green] Created bundle '{name}'")

        except Exception as e:
            # Don't save if installation failed
            raise BundleError(f"Failed to create bundle: {e}") from e

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
        for pkg in packages:
            bundle.packages[pkg] = PackageSpec()

        try:
            self.metapackage_manager.install_metapackage(
                bundle_name, bundle, non_interactive)
            self.store.save(storage)
            self.console.print(
                f"[green]✓[/green] Added packages to bundle '{bundle_name}'"
            )
        except Exception as e:
            raise BundleError(f"Failed to add packages: {e}") from e

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

        try:
            # Update metapackage first
            self.metapackage_manager.install_metapackage(
                bundle_name, bundle, non_interactive)
            self.store.save(storage)

            # Handle system package removal
            self._handle_package_removal(
                packages, bundle_name, keep_packages, force, non_interactive
            )

            self.console.print(
                f"[green]✓[/green] Removed packages from bundle '{bundle_name}'"
            )

        except Exception as e:
            raise BundleError(f"Failed to remove packages: {e}") from e

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

        bundle = storage.bundles[bundle_name]

        try:
            # Remove metapackage
            success = self.metapackage_manager.remove_metapackage(
                bundle_name, non_interactive)
            if not success:
                raise BundleError("Failed to remove metapackage")

            # Remove from storage
            del storage.bundles[bundle_name]
            self.store.save(storage)

            # Handle package removal
            if not keep_packages:
                packages_to_remove = self._determine_packages_to_remove(
                    list(bundle.packages.keys()), bundle_name, force
                )
                if packages_to_remove:
                    self.console.print(
                        "[yellow]Run 'sudo apt autoremove' to remove unused packages[/yellow]"
                    )

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

        try:
            self.metapackage_manager.install_metapackage(
                bundle_name, bundle, non_interactive)
            self.console.print(
                f"[green]✓[/green] Synced bundle '{bundle_name}'")
        except Exception as e:
            raise BundleError(f"Failed to sync bundle: {e}") from e

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

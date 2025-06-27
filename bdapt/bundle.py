"""Core bundle management logic."""

import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import List, Optional, Set

from rich.console import Console

from .models import Bundle, PackageSpec
from .storage import BundleStore, StorageError


class BundleError(Exception):
    """Raised when bundle operations fail."""

    pass


class BundleManager:
    """Manages bundle operations including metapackage generation."""

    def __init__(
        self, store: Optional[BundleStore] = None, console: Optional[Console] = None
    ):
        """Initialize the bundle manager.

        Args:
            store: Bundle storage instance
            console: Rich console for output
        """
        self.store = store or BundleStore()
        self.console = console or Console()

    def _validate_bundle_name(self, name: str) -> None:
        """Validate bundle name for use in metapackage names.

        Args:
            name: Bundle name to validate

        Raises:
            BundleError: If name contains invalid characters
        """
        if not re.match(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$", name) and len(name) > 1:
            if not re.match(r"^[a-z0-9]$", name):
                raise BundleError(
                    f"Invalid bundle name '{name}'. Must contain only lowercase letters, "
                    "numbers, dots, and hyphens. Must start and end with alphanumeric."
                )

    def _get_metapackage_name(self, bundle_name: str) -> str:
        """Get metapackage name for a bundle."""
        return f"bdapt-{bundle_name}"

    def _check_command_exists(self, command: str) -> bool:
        """Check if a command exists on the system."""
        try:
            subprocess.run(
                ["which", command], check=True, capture_output=True, text=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def _run_command(
        self, cmd: List[str], check: bool = True, **kwargs
    ) -> subprocess.CompletedProcess:
        """Run a system command with error handling.

        Args:
            cmd: Command and arguments to run
            check: Whether to raise on non-zero exit code
            **kwargs: Additional arguments to subprocess.run

        Returns:
            CompletedProcess instance

        Raises:
            BundleError: If command fails and check=True
        """
        try:
            self.console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
            result = subprocess.run(cmd, check=check, **kwargs)
            return result
        except subprocess.CalledProcessError as e:
            raise BundleError(
                f"Command failed: {' '.join(cmd)}\nError: {e}") from e
        except FileNotFoundError as e:
            raise BundleError(f"Command not found: {cmd[0]}") from e

    def _generate_control_file(self, bundle_name: str, bundle: Bundle) -> str:
        """Generate equivs control file content.

        Args:
            bundle_name: Name of the bundle
            bundle: Bundle definition

        Returns:
            Control file content as string
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        metapackage_name = self._get_metapackage_name(bundle_name)

        control_content = dedent(f"""
        Package: {metapackage_name}
        Version: 1.0~{timestamp}
        Maintainer: bdapt <bdapt@localhost>
        Architecture: all
        Description: {bundle.description or f"Generated metapackage for bdapt bundle '{bundle_name}'"}
        """)

        if bundle.packages:
            depends = bundle.get_depends_string()
            control_content += f"Depends: {depends}\n"

        return control_content

    def _sync_bundle_metapackage(self, bundle_name: str, bundle: Bundle, non_interactive: bool = False) -> None:
        """Sync bundle metapackage with current definition.

        Args:
            bundle_name: Name of the bundle
            bundle: Bundle definition
            non_interactive: If True, run apt commands non-interactively
        """
        self._validate_bundle_name(bundle_name)

        # Check for required tools
        if not self._check_command_exists("equivs-build"):
            raise BundleError(
                "equivs-build not found. Please install equivs package: "
                "sudo apt install equivs"
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            control_file = temp_path / "control"

            # Generate control file
            control_content = self._generate_control_file(bundle_name, bundle)
            control_file.write_text(control_content)

            # Build metapackage
            self._run_command(
                ["equivs-build", str(control_file)],
                cwd=temp_dir,
                capture_output=True,
                text=True,
            )

            # Find generated .deb file
            deb_files = list(temp_path.glob("*.deb"))
            if not deb_files:
                raise BundleError("equivs-build did not generate a .deb file")

            deb_file = deb_files[0]

            # Install metapackage using apt install (not dpkg) to handle dependencies
            cmd = ["sudo", "apt", "install", str(deb_file)]
            if non_interactive:
                cmd.append("-y")

            self._run_command(cmd, check=True)

    def _is_package_manually_installed(self, package: str) -> bool:
        """Check if a package is marked as manually installed.

        Args:
            package: Package name to check

        Returns:
            True if manually installed, False otherwise
        """
        try:
            result = self._run_command(
                ["apt-mark", "showmanual", package],
                capture_output=True,
                text=True,
                check=False,
            )
            return package in result.stdout.strip().split("\n")
        except BundleError:
            return False

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

    def create_bundle(
        self, name: str, packages: List[str], description: str = "", non_interactive: bool = False
    ) -> None:
        """Create a new bundle.

        Args:
            name: Bundle name
            packages: List of package names
            description: Bundle description
            non_interactive: If True, run apt commands non-interactively
        """
        self._validate_bundle_name(name)

        storage = self.store.load()

        if name in storage.bundles:
            raise BundleError(f"Bundle '{name}' already exists")

        # Create bundle definition
        bundle = Bundle(
            description=description, packages={
                pkg: PackageSpec() for pkg in packages}
        )

        try:
            # Sync metapackage first - only save to storage if successful
            self._sync_bundle_metapackage(name, bundle, non_interactive)

            # Add to storage only after successful sync
            storage.bundles[name] = bundle
            self.store.save(storage)
            self.console.print(f"[green]✓[/green] Created bundle '{name}'")
        except Exception as e:
            # Don't save if sync failed
            raise BundleError(f"Failed to create bundle: {e}") from e

    def add_packages(self, bundle_name: str, packages: List[str], non_interactive: bool = False) -> None:
        """Add packages to an existing bundle.

        Args:
            bundle_name: Name of the bundle
            packages: List of package names to add
            non_interactive: If True, run apt commands non-interactively
        """
        storage = self.store.load()

        if bundle_name not in storage.bundles:
            raise BundleError(f"Bundle '{bundle_name}' does not exist")

        bundle = storage.bundles[bundle_name]

        # Add new packages
        for pkg in packages:
            bundle.packages[pkg] = PackageSpec()

        try:
            self._sync_bundle_metapackage(bundle_name, bundle, non_interactive)
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
        """
        storage = self.store.load()

        if bundle_name not in storage.bundles:
            raise BundleError(f"Bundle '{bundle_name}' does not exist")

        bundle = storage.bundles[bundle_name]

        # Remove packages from bundle definition
        for pkg in packages:
            if pkg not in bundle.packages:
                self.console.print(
                    f"[yellow]Warning:[/yellow] Package '{pkg}' not in bundle '{bundle_name}'"
                )
            else:
                del bundle.packages[pkg]

        try:
            # Sync updated bundle first
            self._sync_bundle_metapackage(bundle_name, bundle, non_interactive)
            self.store.save(storage)

            if not keep_packages:
                # Determine which packages to remove from system
                other_bundle_packages = self._get_packages_in_other_bundles(
                    bundle_name)
                packages_to_remove = []

                for pkg in packages:
                    if pkg in other_bundle_packages:
                        if not force:
                            self.console.print(
                                f"[yellow]Keeping '{pkg}' (required by other bundles)[/yellow]"
                            )
                            continue

                    if self._is_package_manually_installed(pkg) and not force:
                        self.console.print(
                            f"[yellow]Keeping '{pkg}' (manually installed)[/yellow]"
                        )
                        continue

                    packages_to_remove.append(pkg)

                if packages_to_remove:
                    self.console.print(
                        f"[yellow]The following packages will be removed: {' '.join(packages_to_remove)}[/yellow]"
                    )
                    # Forward apt's output to user for confirmation as per design
                    cmd = ["sudo", "apt", "remove"] + packages_to_remove
                    if non_interactive:
                        cmd.append("-y")

                    try:
                        self._run_command(cmd, check=False)
                    except BundleError:
                        # On failure: keep the updated bundles.json, prompt user to remove manually
                        self.console.print(
                            "[yellow]Warning:[/yellow] Failed to remove packages. "
                            "Bundle definition updated. Please remove packages manually if needed."
                        )

            self.console.print(
                f"[green]✓[/green] Removed packages from bundle '{bundle_name}'"
            )

        except Exception as e:
            raise BundleError(f"Failed to remove packages: {e}") from e

    def delete_bundle(
        self, bundle_name: str, keep_packages: bool = False, force: bool = False, non_interactive: bool = False
    ) -> None:
        """Delete a bundle completely.

        Args:
            bundle_name: Name of the bundle to delete
            keep_packages: If True, keep packages on system (mark as manual)
            force: If True, force removal even if in other bundles or manually installed
            non_interactive: If True, run apt commands non-interactively
        """
        storage = self.store.load()

        if bundle_name not in storage.bundles:
            raise BundleError(f"Bundle '{bundle_name}' does not exist")

        bundle = storage.bundles[bundle_name]
        metapackage_name = self._get_metapackage_name(bundle_name)

        try:
            # Remove metapackage
            cmd = ["sudo", "apt", "remove", metapackage_name]
            if non_interactive:
                cmd.append("-y")
            self._run_command(cmd)

            # Remove from storage
            del storage.bundles[bundle_name]
            self.store.save(storage)

            if not keep_packages:
                # Handle package removal similar to remove_packages
                other_bundle_packages = self._get_packages_in_other_bundles(
                    bundle_name)
                packages_to_remove = []

                for pkg in bundle.packages:
                    if pkg in other_bundle_packages:
                        if not force:
                            self.console.print(
                                f"[yellow]Keeping '{pkg}' (required by other bundles)[/yellow]"
                            )
                            continue

                    if self._is_package_manually_installed(pkg) and not force:
                        self.console.print(
                            f"[yellow]Keeping '{pkg}' (manually installed)[/yellow]"
                        )
                        continue

                    packages_to_remove.append(pkg)

                if packages_to_remove:
                    self.console.print(
                        f"[yellow]Run 'sudo apt autoremove' to remove unused packages[/yellow]"
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
        """
        storage = self.store.load()

        if bundle_name not in storage.bundles:
            raise BundleError(f"Bundle '{bundle_name}' does not exist")

        bundle = storage.bundles[bundle_name]

        try:
            self._sync_bundle_metapackage(bundle_name, bundle, non_interactive)
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
                f"[blue]{name}[/blue]{desc} ({pkg_count} packages)")

    def show_bundle(self, bundle_name: str) -> None:
        """Show bundle details.

        Args:
            bundle_name: Name of the bundle to show
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

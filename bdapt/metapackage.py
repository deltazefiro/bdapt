"""Metapackage creation and management utilities."""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Optional

from rich.console import Console

from .apt_operations import AptCommandRunner
from .exceptions import CommandError, UserAbortError
from .models import Bundle


class MetapackageManager:
    """Handles creation and management of metapackages."""

    def __init__(self, console: Console):
        """Initialize the metapackage manager.

        Args:
            console: Rich console for output
        """
        self.console = console
        self.apt_runner = AptCommandRunner(console)

    def _get_metapackage_name(self, bundle_name: str) -> str:
        """Get metapackage name for a bundle.

        Args:
            bundle_name: Name of the bundle

        Returns:
            Metapackage name with bdapt prefix
        """
        return f"bdapt-{bundle_name}"

    def _check_prerequisites(self) -> None:
        """Check that required tools are available.

        Exits:
            With code 1 if required tools are missing
        """
        if not self.apt_runner.check_command_exists("equivs-build"):
            raise CommandError(
                "equivs-build not found. Please install equivs package: sudo apt install equivs"
            )

    def _generate_control_file_content(
        self,
        bundle_name: str,
        bundle: Bundle
    ) -> str:
        """Generate equivs control file content.

        Args:
            bundle_name: Name of the bundle
            bundle: Bundle definition

        Returns:
            Control file content as string
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        metapackage_name = self._get_metapackage_name(bundle_name)

        description = (
            bundle.description or
            f"Generated metapackage for bdapt bundle '{bundle_name}'"
        )

        control_content = dedent(f"""
        Package: {metapackage_name}
        Version: 1.0~{timestamp}
        Maintainer: bdapt <bdapt@localhost>
        Architecture: all
        Description: {description}
        """).strip() + "\n"

        if bundle.packages:
            depends = bundle.get_depends_string()
            control_content += f"Depends: {depends}\n"

        return control_content

    def _build_metapackage(
        self,
        bundle_name: str,
        bundle: Bundle
    ) -> Path:
        """Build a metapackage for the given bundle.

        Args:
            bundle_name: Name of the bundle
            bundle: Bundle definition

        Returns:
            Path to the generated .deb file

        Exits:
            With code 1 if metapackage creation fails
        """
        self._check_prerequisites()

        temp_dir = Path(tempfile.mkdtemp())
        try:
            control_file = temp_dir / "control"

            # Generate and write control file
            control_content = self._generate_control_file_content(
                bundle_name, bundle)
            control_file.write_text(control_content)

            # Build metapackage
            self.apt_runner.run_command(
                ["equivs-build", str(control_file)],
                cwd=temp_dir,
                capture_output=True,
                text=True,
            )

            # Find generated .deb file
            deb_files = list(temp_dir.glob("*.deb"))
            if not deb_files:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise CommandError("equivs-build did not generate a .deb file")

            return deb_files[0]

        except CommandError:
            # Clean up temp directory on failure and re-raise
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        except Exception as e:
            # Clean up temp directory on failure
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise CommandError(f"Failed to build metapackage: {e}")

    def _confirm_installation(self, summary: str) -> bool:
        """Ask user to confirm installation based on dry-run summary.

        Args:
            summary: Package change summary from dry-run

        Returns:
            True if user confirms, False otherwise
        """
        self.console.print("[yellow]Package Changes:[/yellow]")
        self.console.print(summary)

        response = input(
            "\nDo you want to proceed with these changes? [y/N]: ").strip().lower()
        return response in ['y', 'yes']

    def prepare_metapackage_install(
        self,
        bundle_name: str,
        bundle: Bundle,
        non_interactive: bool = False,
        ignore_errors: bool = False
    ) -> Optional[tuple[Path, Path]]:
        """Build metapackage, run dry-run, and get confirmation.

        This method performs all pre-installation steps. After this returns,
        the caller should update storage before calling complete_metapackage_install.

        Args:
            bundle_name: Name of the bundle
            bundle: Bundle definition
            non_interactive: If True, skip confirmation prompts
            ignore_errors: If True, ignore errors

        Returns:
            Tuple of (deb_file_path, temp_dir_path) if installation should proceed,
            or None if no changes are needed or errors are being ignored

        Raises:
            CommandError: If metapackage creation or dry-run fails
            UserAbortError: If user cancels the operation
        """
        deb_file = self._build_metapackage(bundle_name, bundle)
        temp_dir = deb_file.parent

        try:
            # Perform dry-run to show what will be installed
            try:
                summary = self.apt_runner.run_apt_dry_run([str(deb_file)])
            except CommandError:
                shutil.rmtree(temp_dir, ignore_errors=True)
                if ignore_errors:
                    self.console.print(
                        "[yellow]Dry-run failed, but ignoring errors.[/yellow]")
                    return None
                raise
            except KeyboardInterrupt:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise UserAbortError(
                    "Dry-run interrupted by user.", exit_code=130)

            if summary is None:
                self.console.print(
                    "[green]No package changes required.[/green]")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

            # Ask for confirmation unless running non-interactively
            if not non_interactive:
                if not self._confirm_installation(summary):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    raise UserAbortError(
                        "Operation cancelled by user.", exit_code=1)

            return deb_file, temp_dir

        except (CommandError, UserAbortError):
            # These are already handled, just re-raise
            raise
        except Exception:
            # Cleanup on unexpected errors
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def complete_metapackage_install(
        self,
        deb_file: Path,
        temp_dir: Path,
        ignore_errors: bool = False
    ) -> None:
        """Complete the metapackage installation.

        This should be called after prepare_metapackage_install and after
        updating the bundle storage.

        Args:
            deb_file: Path to the .deb file
            temp_dir: Temporary directory to clean up
            ignore_errors: If True, ignore errors

        Raises:
            CommandError: If installation fails
            UserAbortError: If user interrupts the operation
        """
        try:
            # Execute the actual installation
            try:
                self.apt_runner.run_apt_install([str(deb_file)])
                self.console.print(
                    "[green]APT operation completed successfully.[/green]")
            except CommandError as e:
                if ignore_errors:
                    self.console.print(
                        "[yellow]Installation failed, but ignoring errors.[/yellow]")
                    return
                # Enhance error message with recovery instructions
                enhanced_msg = (
                    f"{e.message}\n\n"
                    "The bundle definition has been updated, but the system may be in an inconsistent state.\n"
                    "You may need to run 'bdapt sync <bundle>' to reinstall or 'bdapt del -f <bundle>' to clean up."
                )
                raise CommandError(
                    enhanced_msg, stderr=e.stderr, stdout=e.stdout)
            except KeyboardInterrupt:
                raise UserAbortError(
                    "Installation interrupted by user.\n\n"
                    "The system may be in an inconsistent state.\n"
                    "You may need to run 'bdapt sync <bundle>' to reinstall or 'bdapt del -f <bundle>' to clean up.",
                    exit_code=130
                )

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def remove_metapackage(
        self,
        bundle_name: str,
        non_interactive: bool = False,
        ignore_errors: bool = False
    ) -> None:
        """Remove a metapackage from the system.

        Args:
            bundle_name: Name of the bundle
            non_interactive: If True, run apt commands non-interactively
            ignore_errors: If True, ignore errors

        Raises:
            CommandError: If metapackage removal fails
            UserAbortError: If user cancels the operation
        """
        metapackage_name = self._get_metapackage_name(bundle_name)
        # `apt install packagename-` will remove the package
        package_spec = metapackage_name + "-"

        try:
            # Perform dry-run to show what will be removed
            try:
                summary = self.apt_runner.run_apt_dry_run([package_spec])
            except CommandError:
                if ignore_errors:
                    self.console.print(
                        "[yellow]Dry-run failed, but ignoring errors.[/yellow]")
                    return
                raise
            except KeyboardInterrupt:
                raise UserAbortError(
                    "Dry-run interrupted by user.", exit_code=130)

            if summary is None:
                self.console.print(
                    "[green]No package changes required.[/green]")
                return

            # Ask for confirmation unless running non-interactively
            if not non_interactive:
                # Reuse confirmation method
                if not self._confirm_installation(summary):
                    raise UserAbortError(
                        "Operation cancelled by user.", exit_code=1)

            # Execute the actual removal
            try:
                self.apt_runner.run_apt_install([package_spec])
                self.console.print(
                    "[green]Metapackage removal completed successfully.[/green]")
            except CommandError:
                if ignore_errors:
                    self.console.print(
                        "[yellow]Removal failed, but ignoring errors.[/yellow]")
                    return
                raise
            except KeyboardInterrupt:
                raise UserAbortError(
                    "Removal interrupted by user.", exit_code=130)

        except (CommandError, UserAbortError):
            raise
        except Exception as e:
            raise CommandError(f"Failed to remove metapackage: {e}")

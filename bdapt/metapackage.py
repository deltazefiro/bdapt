"""Metapackage creation and management utilities."""

import tempfile
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Optional

from rich.console import Console

from .apt_operations import AptCommandRunner
from .exceptions import MetapackageError
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

    def get_metapackage_name(self, bundle_name: str) -> str:
        """Get metapackage name for a bundle.

        Args:
            bundle_name: Name of the bundle

        Returns:
            Metapackage name with bdapt prefix
        """
        return f"bdapt-{bundle_name}"

    def check_prerequisites(self) -> None:
        """Check that required tools are available.

        Raises:
            MetapackageError: If required tools are missing
        """
        if not self.apt_runner.check_command_exists("equivs-build"):
            raise MetapackageError(
                "equivs-build not found. Please install equivs package: "
                "sudo apt install equivs"
            )

    def generate_control_file_content(
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
        metapackage_name = self.get_metapackage_name(bundle_name)

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

    def build_metapackage(
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

        Raises:
            MetapackageError: If metapackage creation fails
        """
        self.check_prerequisites()

        temp_dir = Path(tempfile.mkdtemp())
        try:
            control_file = temp_dir / "control"

            # Generate and write control file
            control_content = self.generate_control_file_content(
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
                raise MetapackageError(
                    "equivs-build did not generate a .deb file")

            return deb_files[0]

        except Exception as e:
            # Clean up temp directory on failure
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            if isinstance(e, MetapackageError):
                raise
            raise MetapackageError(f"Failed to build metapackage: {e}") from e

    def install_metapackage(
        self,
        bundle_name: str,
        bundle: Bundle,
        non_interactive: bool = False
    ) -> None:
        """Create and install a metapackage for the given bundle.

        Args:
            bundle_name: Name of the bundle
            bundle: Bundle definition
            non_interactive: If True, run apt commands non-interactively

        Raises:
            MetapackageError: If metapackage creation or installation fails
        """
        deb_file = self.build_metapackage(bundle_name, bundle)

        try:
            # Install the metapackage
            self.apt_runner.install_package_file(
                str(deb_file), non_interactive)
        except Exception as e:
            raise MetapackageError(
                f"Failed to install metapackage: {e}") from e
        finally:
            # Clean up temporary files
            import shutil
            shutil.rmtree(deb_file.parent, ignore_errors=True)

    def remove_metapackage(
        self,
        bundle_name: str,
        non_interactive: bool = False
    ) -> bool:
        """Remove a metapackage from the system.

        Args:
            bundle_name: Name of the bundle
            non_interactive: If True, run apt commands non-interactively

        Returns:
            True if successful, False otherwise
        """
        metapackage_name = self.get_metapackage_name(bundle_name)
        return self.apt_runner.remove_package(metapackage_name, non_interactive)

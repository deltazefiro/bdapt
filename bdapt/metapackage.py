import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from textwrap import dedent

from .apt_operations import AptCommandRunner
from .console import console
from .exceptions import CommandError
from .models import Bundle


class MetapackageContext:
    """
    Context manager for metapackage creation with automatic temp directory cleanup.
    """

    def __init__(
        self,
        bundle_name: str,
        bundle: Bundle,
        apt_runner: AptCommandRunner
    ):
        """Initialize the metapackage context.

        Args:
            bundle_name: Name of the bundle
            bundle: Bundle definition
            apt_runner: APT command runner for executing equivs-build
        """
        self.bundle_name = bundle_name
        self.bundle = bundle
        self.apt_runner = apt_runner
        self.temp_dir = None
        self.deb_file = None

    @staticmethod
    def get_metapackage_name(bundle_name: str) -> str:
        """Get metapackage name for a bundle.

        Args:
            bundle_name: Name of the bundle

        Returns:
            Metapackage name with bdapt prefix
        """
        return f"bdapt-{bundle_name}"

    @staticmethod
    def check_prerequisites(apt_runner: AptCommandRunner) -> None:
        """Check that required tools are available.

        Args:
            apt_runner: APT command runner to check for command existence

        Raises:
            CommandError: If required tools are missing
        """
        if not apt_runner.check_command_exists("equivs-build"):
            raise CommandError(
                "equivs-build not found. Please install equivs package: sudo apt install equivs"
            )

    def _generate_control_file_content(self) -> str:
        """Generate equivs control file content.

        Returns:
            Control file content as string
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        metapackage_name = self.get_metapackage_name(self.bundle_name)

        description = (
            self.bundle.description or
            f"Generated metapackage for bdapt bundle '{self.bundle_name}'"
        )

        control_content = dedent(f"""
        Package: {metapackage_name}
        Version: 1.0~{timestamp}
        Maintainer: bdapt <bdapt@localhost>
        Architecture: all
        Description: {description}
        """).strip() + "\n"

        if self.bundle.packages:
            depends = self.bundle.get_depends_string()
            control_content += f"Depends: {depends}\n"

        return control_content

    def _build(self) -> None:
        """Build the metapackage.

        Creates temp directory, generates control file, and builds .deb package.

        Raises:
            CommandError: If metapackage creation fails
        """
        self.check_prerequisites(self.apt_runner)

        self.temp_dir = Path(tempfile.mkdtemp())
        try:
            control_file = self.temp_dir / "control"

            # Generate and write control file
            control_content = self._generate_control_file_content()
            control_file.write_text(control_content)

            # Build metapackage
            self.apt_runner.run_command(
                ["equivs-build", str(control_file)],
                cwd=self.temp_dir,
                capture_output=True,
                text=True,
            )

            # Find generated .deb file
            deb_files = list(self.temp_dir.glob("*.deb"))
            if not deb_files:
                raise CommandError("equivs-build did not generate a .deb file")

            self.deb_file = deb_files[0]

        except Exception as e:
            # Clean up temp directory on failure
            if self.temp_dir:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            if isinstance(e, CommandError):
                raise
            raise CommandError(f"Failed to build metapackage: {e}")

    def __enter__(self) -> Path:
        """Enter the context and return the .deb file path.

        Returns:
            Path to the generated .deb file

        Raises:
            CommandError: If metapackage creation fails
        """
        with console.status(f"Building metapackage for [bold]{self.bundle_name}[/bold]..."):
            self._build()
        if self.deb_file is None:
            raise CommandError("Metapackage build did not produce a .deb file")
        return self.deb_file

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context and clean up the temporary directory.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)

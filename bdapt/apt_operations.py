"""APT command execution and parsing utilities."""

import subprocess
from typing import List, Set, Tuple

from rich.console import Console

from .exceptions import AptError


class AptCommandRunner:
    """Handles execution of APT commands."""

    def __init__(self, console: Console):
        """Initialize the APT command runner.

        Args:
            console: Rich console for output
        """
        self.console = console

    def check_command_exists(self, command: str) -> bool:
        """Check if a command exists on the system.

        Args:
            command: Command name to check

        Returns:
            True if command exists, False otherwise
        """
        try:
            subprocess.run(
                ["which", command],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def run_command(
        self,
        cmd: List[str],
        check: bool = True,
        show_output: bool = True,
        **kwargs
    ) -> subprocess.CompletedProcess:
        """Run a system command with error handling.

        Args:
            cmd: Command and arguments to run
            check: Whether to raise on non-zero exit code
            show_output: Whether to show the command being run
            **kwargs: Additional arguments to subprocess.run

        Returns:
            CompletedProcess instance

        Raises:
            AptError: If command fails and check=True
        """
        try:
            if show_output:
                self.console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")

            result = subprocess.run(cmd, check=check, **kwargs)
            return result
        except subprocess.CalledProcessError as e:
            raise AptError(
                f"Command failed: {' '.join(cmd)}\nError: {e}") from e
        except FileNotFoundError as e:
            raise AptError(f"Command not found: {cmd[0]}") from e

    def parse_apt_dry_run_output(self, output: str) -> Tuple[int, List[str]]:
        """Parse apt dry-run output to extract packages to be installed.

        Args:
            output: stdout from apt install --dry-run

        Returns:
            Tuple of (count of new packages, list of package names)
        """
        new_packages = []
        lines = output.split('\n')

        for line in lines:
            # Look for lines like "Inst package-name (version info)"
            if line.strip().startswith('Inst '):
                parts = line.strip().split()
                if len(parts) >= 2:
                    package_name = parts[1]
                    new_packages.append(package_name)

        return len(new_packages), new_packages

    def install_package_file(
        self,
        deb_file_path: str,
        non_interactive: bool = False
    ) -> Tuple[int, List[str]]:
        """Install a .deb file and return information about what will be installed.

        Args:
            deb_file_path: Path to the .deb file
            non_interactive: If True, run apt commands non-interactively

        Returns:
            Tuple of (package count, package list) that were/will be installed

        Raises:
            AptError: If installation fails
        """
        # First, do a dry run to see what packages will be installed
        dry_run_cmd = ["sudo", "apt", "install", "--dry-run", deb_file_path]
        dry_run_result = self.run_command(
            dry_run_cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Parse dry run output
        package_count, package_list = self.parse_apt_dry_run_output(
            dry_run_result.stdout
        )

        # Ask for confirmation if multiple packages and not non-interactive
        if package_count > 1 and not non_interactive:
            self.console.print(
                f"[yellow]The following {package_count} packages will be installed:[/yellow]"
            )
            for pkg in package_list:
                self.console.print(f"  • {pkg}")

            response = input(
                "\nDo you want to continue? [y/N]: ").strip().lower()
            if response not in ['y', 'yes']:
                raise AptError("Installation cancelled by user")
        elif package_count > 1:
            # In non-interactive mode, just show what will be installed
            self.console.print(
                f"[dim]Installing {package_count} packages: "
                f"{', '.join(package_list[:5])}{'...' if len(package_list) > 5 else ''}[/dim]"
            )

        # Install metapackage using apt install to handle dependencies
        cmd = ["sudo", "apt", "install", deb_file_path, "-y"]
        self.run_command(cmd, check=True)

        return package_count, package_list

    def remove_packages(
        self,
        packages: List[str],
        non_interactive: bool = False
    ) -> bool:
        """Remove packages from the system.

        Args:
            packages: List of package names to remove
            non_interactive: If True, run apt commands non-interactively

        Returns:
            True if successful, False if cancelled or failed
        """
        if not packages:
            return True

        self.console.print(
            f"[yellow]The following packages will be removed: {' '.join(packages)}[/yellow]"
        )

        cmd = ["sudo", "apt", "remove"] + packages
        if non_interactive:
            cmd.append("-y")

        try:
            result = self.run_command(cmd, check=False)
            return result.returncode == 0
        except AptError:
            return False

    def remove_package(
        self,
        package: str,
        non_interactive: bool = False
    ) -> bool:
        """Remove a single package from the system.

        Args:
            package: Package name to remove
            non_interactive: If True, run apt commands non-interactively

        Returns:
            True if successful, False if cancelled or failed
        """
        return self.remove_packages([package], non_interactive)

    def is_package_manually_installed(self, package: str) -> bool:
        """Check if a package is marked as manually installed.

        Args:
            package: Package name to check

        Returns:
            True if manually installed, False otherwise
        """
        try:
            result = self.run_command(
                ["apt-mark", "showmanual", package],
                capture_output=True,
                text=True,
                check=False,
                show_output=False
            )
            return package in result.stdout.strip().split("\n")
        except AptError:
            return False

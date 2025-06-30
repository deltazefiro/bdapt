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

    def run_apt_command(
        self,
        command: List[str],
        non_interactive: bool = False,
        show_dry_run_output: bool = True
    ) -> bool:
        """Run an APT command with dry-run and confirmation.

        Args:
            command: The base APT command to run (e.g., ['sudo', 'apt', 'install', 'pkg'])
            non_interactive: Skip confirmation prompts
            show_dry_run_output: Show the output of the dry run

        Returns:
            True if the user confirmed and the command should proceed, False otherwise.
        """
        # Perform dry run
        dry_run_cmd = command + ["--dry-run"]
        try:
            dry_run_result = self.run_command(
                dry_run_cmd,
                capture_output=True,
                text=True,
                check=True
            )
            if show_dry_run_output:
                self.console.print(
                    "[yellow]APT Dry-Run Output:[/yellow]\n"
                    f"{dry_run_result.stdout.strip()}"
                )

        except AptError as e:
            self.console.print(
                f"[red]Error during dry-run: {e}[/red]")
            return False

        # Ask for confirmation
        if not non_interactive:
            response = input(
                "\nDo you want to proceed with these changes? [y/N]: ").strip().lower()
            if response not in ['y', 'yes']:
                self.console.print(
                    "[yellow]Operation cancelled by user.[/yellow]")
                return False

        # Execute the actual command
        try:
            self.run_command(command + ["-y"], check=True)
            return True
        except AptError as e:
            self.console.print(
                f"[red]Error during APT operation: {e}[/red]\n"
                "[yellow]The bundle definition has been updated, but the system may be in an inconsistent state.\n"
                "You may need to run 'sudo apt --fix-broken install' or 'bdapt sync <bundle>' to resolve.[/yellow]"
            )
            # We return True because the operation was confirmed, even if it failed.
            # The caller is responsible for handling this state.
            return True

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
    ) -> bool:
        """Install a .deb file using the run_apt_command flow.

        Args:
            deb_file_path: Path to the .deb file
            non_interactive: If True, run apt commands non-interactively

        Returns:
            True if the operation was confirmed, False otherwise.
        """
        cmd = ["sudo", "apt", "install", "-f", deb_file_path]
        return self.run_apt_command(cmd, non_interactive)

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

        cmd = ["sudo", "apt", "autoremove"] + packages
        return self.run_apt_command(cmd, non_interactive, show_dry_run_output=False)

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
        # The package name is appended with '-' to indicate removal
        cmd = ["sudo", "apt", "install", f"{package}-"]
        return self.run_apt_command(cmd, non_interactive)

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

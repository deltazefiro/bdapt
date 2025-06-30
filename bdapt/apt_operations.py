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
        packages: List[str],
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
        cmd = ["sudo", "apt", "install", "--autoremove", "-f"] + packages
        try:
            dry_run_result = self.run_command(
                cmd + ["--dry-run"],
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
            self.run_command(cmd + ["-y"], check=True)
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

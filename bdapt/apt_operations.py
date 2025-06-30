"""APT command execution and parsing utilities."""

import subprocess
from typing import Any, List

import typer
from rich.console import Console


class AptError(Exception):
    """Exception raised for APT command errors."""


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
        **kwargs: Any
    ) -> subprocess.CompletedProcess:
        try:
            if show_output:
                self.console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
            result = subprocess.run(cmd, check=check, **kwargs)
            return result
        except subprocess.CalledProcessError as e:
            self.console.print(
                f"[red]Error: Command failed: {' '.join(cmd)}[/red]")
            self.console.print(f"[red]Error: {e}[/red]")
            raise AptError(
                f"Command failed: {' '.join(cmd)}\nError: {e}") from e
        except FileNotFoundError as _:
            self.console.print(
                f"[red]Error: Command not found: {cmd[0]}[/red]")
            raise typer.Exit(1)

    def run_apt_command(
        self,
        packages: List[str],
        non_interactive: bool = False,
        show_dry_run_output: bool = True
    ) -> None:
        """
        Run an APT command with dry-run and confirmation.
        """
        # Perform dry run
        cmd = ["sudo", "apt-get", "install", "--autoremove", "-f"] + packages

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

        # Ask for confirmation
        if not non_interactive:
            response = input(
                "\nDo you want to proceed with these changes? [y/N]: ").strip().lower()
            if response not in ['y', 'yes']:
                self.console.print(
                    "[yellow]Operation cancelled by user.[/yellow]")
                raise typer.Exit(1)

        # Execute the actual command
        try:
            self.run_command(cmd + ["-y"], check=True)
        except AptError:
            self.console.print(
                "[red]Error during APT operation[/red]\n"
                "[yellow]The bundle definition has been updated, but the system may be in an inconsistent state.\n"
                "You may need to run 'bdapt sync <bundle>' to resolve.[/yellow]"
            )
            raise typer.Exit(1)

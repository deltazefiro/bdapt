"""APT command execution and parsing utilities."""

import re
import subprocess
from typing import Any, List, Optional, Tuple

import typer
from rich.console import Console


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

    def parse_apt_output(self, output: str) -> Optional[str]:
        """Parse APT output and extract the package change summary.

        Args:
            output: Raw APT command output

        Returns:
            Formatted summary of package changes, or None if no changes found
        """
        lines = output.strip().split('\n')
        summary_lines = []
        in_summary = False

        for line in lines:
            # Look for the start of package change summary
            if line.startswith('The following'):
                in_summary = True
                summary_lines.append(line)
            elif in_summary:
                # Continue collecting lines until we hit the upgrade/install summary
                if re.match(r'^\d+.*not upgraded\.$', line.strip()):
                    summary_lines.append(line)
                    break
                elif line.strip() and not line.startswith(' '):
                    # If we hit a non-indented line that's not the summary end, we might be done
                    if not re.match(r'^\d+', line.strip()):
                        break
                summary_lines.append(line)

        if summary_lines:
            return '\n'.join(summary_lines)
        return None

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
        except FileNotFoundError as _:
            self.console.print(
                f"[red]Error: Command not found: {cmd[0]}[/red]")
            raise typer.Exit(1)

    def run_apt_command(
        self,
        packages: List[str],
        non_interactive: bool = False,
        ignore_errors: bool = False,
        show_dry_run_output: bool = True
    ) -> None:
        """
        Run an APT command with dry-run and confirmation.
        """
        # Perform dry run
        cmd = ["sudo", "apt-get", "install", "--autoremove", "-f"] + packages

        try:
            dry_run_result = self.run_command(
                cmd + ["--dry-run"],
                capture_output=True,
                text=True,
                check=True,
                show_output=False
            )

            # Parse and display only the package change summary
            if show_dry_run_output:
                summary = self.parse_apt_output(dry_run_result.stdout)
                if summary:
                    self.console.print("[yellow]Package Changes:[/yellow]")
                    self.console.print(summary)
                else:
                    self.console.print(
                        "[green]No package changes required.[/green]")
                    return

        except subprocess.CalledProcessError as e:
            self.console.print(
                f"[red]APT operation failed: {e.stderr or e.stdout}[/red]")
            if ignore_errors:
                self.console.print(
                    "[yellow]APT operation failed, but ignoring errors.[/yellow]")
                return
            raise typer.Exit(1)
        except KeyboardInterrupt as _:
            self.console.print(
                "\n[yellow]Dry-run interrupted by user.[/yellow]")
            raise typer.Exit(130)

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
            self.run_command(cmd + ["-y"], check=True, show_output=False)
            self.console.print(
                "[green]APT operation completed successfully.[/green]")
        except subprocess.CalledProcessError as e:
            self.console.print(
                f"[red]APT operation failed: {e.stderr or e.output}[/red]")
            if ignore_errors:
                self.console.print(
                    "[yellow]APT operation failed, but ignoring errors.[/yellow]")
                return
            self.console.print(
                "[yellow]The bundle definition has been updated, but the system may be in an inconsistent state.\n"
                "You may need to run [bold]bdapt sync <bundle>[/bold] to reinstall or [bold]bdapt del -f <bundle>[/bold] to clean up.[/yellow]"
            )
        except KeyboardInterrupt:
            self.console.print(
                "\n[yellow]APT operation interrupted by user.[/yellow]\n"
                "[yellow]The system may be in an inconsistent state.\n"
                "You may need to run [bold]bdapt sync <bundle>[/bold] to reinstall or [bold]bdapt del -f <bundle>[/bold] to clean up.[/yellow]"
            )

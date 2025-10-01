"""APT command execution and parsing utilities."""

import re
import subprocess
from contextlib import nullcontext
from typing import Any, List, Optional

from .console import console
from .exceptions import CommandError


class AptCommandRunner:
    """Handles execution of APT commands."""

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
            ctx = console.status(
                f"Running: {' '.join(cmd)}") if show_output else nullcontext()
            with ctx:
                result = subprocess.run(cmd, check=check, **kwargs)
            return result
        except FileNotFoundError:
            raise CommandError(f"Command not found: {cmd[0]}")

    def run_apt_dry_run(self, packages: List[str]) -> Optional[str]:
        """Run APT dry-run and return package change summary.

        Args:
            packages: List of package names

        Returns:
            Package change summary or None if no changes

        Raises:
            CommandError: If dry-run fails
        """
        cmd = ["sudo", "apt-get", "install", "--autoremove", "-f"] + \
            packages + ["--dry-run"]

        try:
            result = self.run_command(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return self.parse_apt_output(result.stdout)
        except subprocess.CalledProcessError as e:
            raise CommandError(
                f"APT dry-run failed: {' '.join(cmd)}",
                stderr=e.stderr,
                stdout=e.stdout
            )

    def run_apt_install(self, packages: List[str]) -> None:
        """Execute APT install command.

        Args:
            packages: List of package names

        Raises:
            CommandError: If installation fails
        """
        cmd = ["sudo", "apt-get", "install",
               "--autoremove", "-f", "-y"] + packages

        try:
            self.run_command(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise CommandError(
                f"APT installation failed: {' '.join(cmd)}",
                stderr=e.stderr,
                stdout=e.stdout
            )

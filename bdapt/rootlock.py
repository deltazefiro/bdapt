import fcntl
import os
import sys

import typer

from .console import console

LOCKFILE = "/etc/bdapt/bdapt.lock"


def _elevate():
    """Re-run the current script with sudo if not root."""
    if os.getuid() == 0:
        return
    try:
        args = [sys.executable] + sys.argv
        os.execlp("sudo", "sudo", *args)
    except Exception as e:
        console.print(
            f"[red]Unable to elevate to root: {e}[/red]")
        typer.Exit(1)


def _acquire_lock(lockfile):
    """Acquire an exclusive lock on the specified lockfile."""
    try:
        os.makedirs(os.path.dirname(lockfile), exist_ok=True)
        fd = open(lockfile, "w")
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        console.print(
            f"[red]Unable to acquire lock: {lockfile}. Is another instance already running?[/red]")
        typer.Exit(1)


def aquire_root_and_lock():
    """Acquire root privileges and a lock on the lockfile."""
    _elevate()
    _acquire_lock(LOCKFILE)

import fcntl
import os
import sys

import typer

from .console import console
from .storage import DATA_DIR

LOCKFILE = "bdapt.lock"
LOCKFILE_PATH = DATA_DIR / LOCKFILE

_lock_file = None


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
        raise typer.Exit(1)


def _acquire_lock():
    """Acquire an exclusive lock on the specified lockfile."""
    global _lock_file
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        _lock_file = open(LOCKFILE_PATH, "w")
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        console.print(
            f"[red]Unable to acquire lock: {LOCKFILE_PATH}. Is another instance already running?[/red]")
        raise typer.Exit(1)


def aquire_root_and_lock():
    """Acquire root privileges and a lock on the lockfile."""
    _elevate()
    _acquire_lock()

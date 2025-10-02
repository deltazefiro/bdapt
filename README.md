# bdapt: Bundle APT<br><sub><sup>Manage multiple Debian / Ubuntu APT packages as bundles</sup></sub>

![PyPI - Version](https://img.shields.io/pypi/v/bdapt)
![PyPI - Downloads](https://img.shields.io/pypi/dm/bdapt)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/bdapt)
[![GitHub Repo stars](https://img.shields.io/github/stars/deltazefiro/bdapt)](https://github.com/deltazefiro/bdapt)

**bdapt** (Bundle APT) is a command-line tool for managing collections of [APT packages](https://en.wikipedia.org/wiki/APT_(software)) as "bundles" on Debian-based systems (e.g. Ubuntu, Debian, etc.). It lets you install, remove, and track related packages together with a single command.

When software is installed from source or outside your package manager, dependencies often have to be installed manually using `apt install`. Later, when you remove the software, these dependencies remain because `apt autoremove` only removes packages marked as "automatically installed." Over time, this leads to clutter and orphaned packages. **bdapt** solves this by grouping dependencies into bundles, making cleanup straightforward.

> [!WARNING]  
> This project is in an early development stage and is **not production ready**. Expect breaking changes and data loss. **Backward compatibility is not guaranteed** (i.e. may require manual data migration on updates). Use at your own risk.

## Installation

You can install bdapt using pip:

```bash
pip install bdapt
```

Or if you prefer [uv](https://github.com/astral-sh/uv):

```bash
uv tool install bdapt
```

## Quickstart

Let's say you're setting up a server for a web application. You need Nginx, PostgreSQL, and Redis.

#### Create bundle

```bash
bdapt new web-stack nginx postgresql redis -d "Core web services stack"
```

#### Add packages

Your application now requires PHP. Instead of installing it manually, add it to your bundle.

```bash
bdapt add web-stack php-fpm php-pgsql
```

#### Remove packages

You've decided to move Redis to a different server and no longer need it locally.

```bash
bdapt rm web-stack redis
```

#### Remove bundle

You are decommissioning the server and want to clean up everything.

```bash
bdapt del web-stack
```

Now your system is clean!

## Usage

```plaintext                                                     
 Usage: bdapt [OPTIONS] COMMAND [ARGS]...

 Bundle APT: Group multiple Debian APT packages as bundles.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version                       Show version and exit                                                                                    │
│ --quiet               -q        Minimal output                                                                                           │
│ --non-interactive     -y        Skip all confirmation prompts                                                                            │
│ --install-completion            Install completion for the current shell.                                                                │
│ --show-completion               Show completion for the current shell, to copy it or customize the installation.                         │
│ --help                          Show this message and exit.                                                                              │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ new    Create and install new bundle.                                                                                                    │
│ add    Add packages to a bundle.                                                                                                         │
│ rm     Remove packages from a bundle.                                                                                                    │
│ del    Delete the bundle.                                                                                                                │
│ ls     List all bundles.                                                                                                                 │
│ show   Display bundle contents.                                                                                                          │
│ sync   Force reinstall bundle to match definition.                                                                                       │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

# bdapt: Bundle APT

When building software from source or install applications outside of your system's package manager, you often need to manually install dependencies with `apt install`. Later, when you remove the application, these dependencies remain. `apt autoremove` won't touch them because they were marked as "manually installed." Over time this can lead to a cluttered system with orphaned packages.

bdapt (Bundle APT, pronounced "bee-dapt") is a wrapper for APT that manages groups of package dependencies as cohesive bundles. It uses equivs to create metapackages, allowing dependencies to be installed, tracked, and removed together.

> [!WARNING]  
> This project is in an early development stage and has been extensively developed with AI. Use at your own risk.

## Installation

You can install bdapt using pip:

```bash
pip install bdapt
```

Or if you use uv:

```bash
uv tool install bdapt
```

## Quickstart

Let's say you're setting up a server for a web application. You need Nginx, PostgreSQL, and Redis.

#### Create bundle

```bash
sudo bdapt new web-stack nginx postgresql redis -d "Core web services stack"
```

#### Add packages

Your application now requires PHP. Instead of installing it manually, add it to your bundle.

```bash
sudo bdapt add web-stack php-fpm php-pgsql
```

#### Remove packages

You've decided to move Redis to a different server and no longer need it locally.

```bash
sudo bdapt rm web-stack redis
```

#### Remove bundle

You are decommissioning the server and want to clean up everything.

```bash
sudo bdapt del web-stack
```

Now, `apt` sees that `nginx`, `postgresql`, `php-fpm`, etc., are no longer required by any package. They are now considered orphaned dependencies.

```bash
sudo apt autoremove
```
Your system is now clean, with no leftover packages from your web stack.

## Usage

```plaintext
bdapt [command] [options]

COMMANDS:
  new <bundle> [pkgs...]      Create and install new bundle
    -d, --desc TEXT           Add description

  add <bundle> <pkgs...>      Add packages to a bundle

  rm <bundle> <pkgs...>       Remove packages from a bundle

  del <bundle>                Delete the bundle

  ls                          List all bundles
    --tree                    Show as dependency tree

  show <bundle>               Display bundle contents

  sync <bundle>               Force reinstall bundle to match definition

OPTIONS:
  -y, --non-interactive       Skip all confirmation prompts
  -q, --quiet                 Minimal output
```

# bdapt: Bundle APT

When installing applications on Debian from sources outside of APT, you often need to manually install multiple APT packages as dependencies. Later, when uninstalling the application, these dependencies aren't automatically removed by `apt autoremove` since they were marked as manually installed rather than auto-installed.

bdapt (Bundle APT, pronounced "bee-dapt") is a wrapper for APT that manages groups of package dependencies as cohesive bundles. It uses equivs to create metapackages, allowing dependencies to be installed, tracked, and removed together. You can easily modify bundles by adding or removing packages as needed.

> [!WARNING] Early Development Disclaimer
> 
> This project is in early development stage and has been extensively developed with generative AI assistance.
>
> - **Not production ready** - This tool is experimental and may have bugs or unexpected behavior
> - **Use at your own risk** - Always test in a safe environment before using on important systems
> - **Backup recommended** - Consider backing up your system state before using bdapt
> - **Community feedback welcome** - Please report issues and contribute to help improve the tool


# Installation

You can install bdapt using pip:

```bash
pip install bdapt
```

Or if you use uv:

```bash
uv tool install bdapt
```

# Usage

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

EXAMPLE WORKFLOW:
# Create and install web stack
$ sudo bdapt new web-stack nginx postgresql redis -d "Web services"

# Add PHP components
$ sudo bdapt add web-stack php-fpm php-pgsql

# Remove Redis when no longer needed
$ sudo bdapt rm web-stack redis

# Complete removal
$ sudo bdapt del web-stack
```

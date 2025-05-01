# bpt: Bundle APT

When installing applications on Debian from sources outside of APT, you often need to manually install multiple APT packages as dependencies. Later, when uninstalling the application, these dependencies aren't automatically removed by `apt autoremove` since they were marked as manually installed rather than auto-installed.

bpt (Bundle APT) is a lightweight Python tool that manages groups of package dependencies as cohesive bundles. It uses equivs to create metapackages, allowing dependencies to be installed, tracked, and removed together. You can easily modify bundles by adding or removing packages as needed.

```plaintext
bpt [command] [options]

COMMANDS:
  new <bundle> [pkgs...]    Create and install new bundle (sudo required)
    -d, --desc TEXT      Add description

  add <bundle> <pkgs...>    Add packages and update system immediately (sudo)
    --no-deps            Skip automatic dependency resolution

  rm <bundle> <pkgs...>     Remove packages and update system immediately (sudo)
    --keep-deps          Leave orphaned dependencies installed

  del <bundle>             Permanently delete bundle and uninstall (sudo)
    --keep-pkgs          Remove bundle but keep packages

  ls                      List all bundles

  show <bundle>           Display bundle contents
    --tree               Show as dependency tree

  clean                   Remove temporary files
    --all                Reset all bpt data

OPTIONS:
  -y, --non-interactive  Skip all confirmation prompts
  -q, --quiet           Minimal output
  --config PATH         Alternate config location (~/.local/share/bpt)

DESIGN PRINCIPLES:
1. Immediate system impact - no separate "update" step
2. Sudo required for any system modification
3. No version history - last change overwrites previous state
4. Simple verbs (new/add/rm/del) for fast operation
5. Automatic dependency handling by default

EXAMPLE WORKFLOW:
# Create and install web stack
$ sudo bpt new web-stack nginx postgresql redis -d "Web services"

# Add PHP components
$ sudo bpt add web-stack php-fpm php-pgsql

# Remove Redis when no longer needed
$ sudo bpt rm web-stack redis

# Complete removal
$ sudo bpt del web-stack
```

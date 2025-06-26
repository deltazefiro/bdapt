# bdapt: Bundle APT

When installing applications on Debian from sources outside of APT, you often need to manually install multiple APT packages as dependencies. Later, when uninstalling the application, these dependencies aren't automatically removed by `apt autoremove` since they were marked as manually installed rather than auto-installed.

bdapt (Bundle APT, pronounced "bee-dapt") is a lightweight Python tool that manages groups of package dependencies as cohesive bundles. It uses equivs to create metapackages, allowing dependencies to be installed, tracked, and removed together. You can easily modify bundles by adding or removing packages as needed.

```plaintext
bdapt [command] [options]

COMMANDS:
  new <bundle> [pkgs...]      Create and install new bundle
    -d, --desc TEXT           Add description

  add <bundle> <pkgs...>      Add packages to a bundle

  rm <bundle> <pkgs...>       Remove packages from a bundle
    --keep-pkg                Update bundle but keep packages on the system (mark as manual)
    --force-remove            Force removal of packages from the system, even if manually installed or required by other bundles

  del <bundle>                Permanently delete the bundle
    --keep-pkg                Remove bundle but keep packages (mark as manually installed)
    --force-remove            Force removal of packages from the system, even if manually installed or required by other bundles

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

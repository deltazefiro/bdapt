update (rm, add, sync)
- run "apt-get install --autoremove -f <bundle_file>"
  - dry run first, forward for confirmation
    - cancelled -> Do not update bundle in store
    - otherwise, update bundle in store
  - run again with -y flag
  - if failed during install, update bundle in store but prompt user broken bundle (`sync` for fixing, `del -f` for removing)

del
- run "apt-get install --autoremove -f <bundle_name>-"
  - dry run first, forward for confirmation
    - cancelled -> Do not update bundle in store (update anyway if `-f`)
    - otherwise, update bundle in store
  - run again with -y flag
  - if failed during install, do *not* remove bundle in store but prompt user broken bundle (`sync` for fixing, `del -f` for removing)


cli.py - handles user input and calls bundle_manager, do inputs sanity checks
bundle_manager.py - handles of installing/updating/deleting bundles
metapackage.py - 1. handles metapackage creation 2. install/remove metapackage flow
apt_operations.py - interface to apt
update (rm, add, sync)
- run "apt-get install --autoremove -f <bundle_file>"
  - dry run first, forward for confirmation
    - cancelled -> raise and exit
    - otherwise, continue
  - update bundle in store
  - run apt again with -y flag
    - if failed, prompt user broken bundle (`sync` for fixing, `del -f` for removing)

del
- run "apt-get install --autoremove -f <bundle_name>-"
  - dry run first, forward for confirmation
    - cancelled -> raise and exit
    - Do not update bundle in store for now
  - run apt again with -y flag
    - if failed, prompt user broken bundle (`sync` for fixing, `del -f` for removing)
    - if successful, remove bundle in store


cli.py - handles user input and calls bundle_manager, do inputs sanity checks
bundle_manager.py - handles of installing/updating/deleting bundles
metapackage.py - 1. handles metapackage creation 2. install/remove metapackage flow
apt_operations.py - interface to apt
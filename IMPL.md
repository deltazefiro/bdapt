new
- run "apt-get install --autoremove -f <bundle_file>"
  - dry run first, forward for confirmation
    - cancelled -> Do not add bundle to store
    - otherwise, add bundle to store
  - run again with -y flag
  - if failed during install, keep bundle in store but prompt user broken bundle (`sync` for fixing, `del -f` for removing)

update (rm, add, sync)
- run "apt-get install --autoremove -f <bundle_file>"
  - dry run first, forward for confirmation
    - cancelled -> Do not update bundle in store
    - otherwise, update bundle in store
  - run again with -y flag
  - if failed during install, keep bundle in store but prompt user broken bundle (`sync` for fixing, `del -f` for removing)

del
- run "apt-get install --autoremove -f <bundle_name>-"
  - dry run first, forward for confirmation
    - cancelled -> Do not update bundle in store (update anyway if `-f`)
    - otherwise, update bundle in store
  - run again with -y flag
  - if failed during install, keep bundle in store but prompt user broken bundle (`sync` for fixing, `del -f` for removing)

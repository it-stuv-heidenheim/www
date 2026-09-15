#!/usr/bin/env bash
# Package the plugins for upload via wp-admin -> Plugins -> Add New -> Upload.
# Usage: ./build.sh [plugin ...]   (no argument: build all)
set -euo pipefail

cd "$(dirname "$0")"

# No argument: every plugin directory here, so adding one needs no edit. A
# plugin is a directory holding its own <name>.php entry point, which is what
# keeps tests/ and any other helper directory out of the list.
if [ "$#" -eq 0 ]; then
  set --
  for dir in */; do
    name="${dir%/}"
    [ -f "$name/$name.php" ] && set -- "$@" "$name"
  done
fi

for plugin in "$@"; do
  plugin="${plugin%/}"
  rm -f "$plugin.zip"
  zip -r "$plugin.zip" "$plugin" -x '*.DS_Store'
  echo "built: $(pwd)/$plugin.zip"
done

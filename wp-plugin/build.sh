#!/usr/bin/env bash
# Package the plugins for upload via wp-admin -> Plugins -> Add New -> Upload.
# Usage: ./build.sh [plugin ...]   (no argument: build all)
set -euo pipefail

cd "$(dirname "$0")"

# A plugin is a directory holding its own <name>.php (keeps tests/ out).
if [ "$#" -eq 0 ]; then
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

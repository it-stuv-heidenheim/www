#!/usr/bin/env bash
# Package the plugins for upload via wp-admin -> Plugins -> Add New -> Upload.
# Usage: ./build.sh [plugin ...]   (no argument: build all)
set -euo pipefail

cd "$(dirname "$0")"

if [ "$#" -eq 0 ]; then
  set -- stuv-mensa stuv-theme stuv-dsgvo
fi

for plugin in "$@"; do
  rm -f "$plugin.zip"
  zip -r "$plugin.zip" "$plugin" -x '*.DS_Store'
  echo "built: $(pwd)/$plugin.zip"
done

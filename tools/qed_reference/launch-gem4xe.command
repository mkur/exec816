#!/bin/sh
bundle_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
exec python3 "$bundle_dir/launch.py" "$@"

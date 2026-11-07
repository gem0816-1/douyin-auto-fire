#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$#" -eq 0 ]; then
    set -- run
fi
exec sh "$PROJECT_ROOT/deploy.sh" "$@"

#!/bin/sh
# Finder entry point: run once and keep the result visible in Terminal.
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
sh "$PROJECT_ROOT/start.sh" "$@"
START_EXIT_CODE=$?
if [ "$#" -eq 0 ] && [ -t 0 ]; then
    printf '\nPress Enter to close...'
    read -r REPLY
fi
exit "$START_EXIT_CODE"

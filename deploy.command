#!/bin/sh
# Finder entry point for macOS; deploy.sh also works without executable permissions.
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
sh "$PROJECT_ROOT/deploy.sh" "$@"
DEPLOY_EXIT_CODE=$?
if [ "$#" -eq 0 ] && [ -t 0 ]; then
    printf '\nPress Enter to close...'
    read -r REPLY
fi
exit "$DEPLOY_EXIT_CODE"

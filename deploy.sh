#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_ROOT"
export PYTHONUTF8=1

if [ -x "$PROJECT_ROOT/.tools/uv/uv" ]; then
    UV_BIN="$PROJECT_ROOT/.tools/uv/uv"
elif command -v uv >/dev/null 2>&1; then
    UV_BIN=$(command -v uv)
else
    echo 'Installing uv into .tools/uv (first run only)...'
    if ! command -v curl >/dev/null 2>&1; then
        echo 'curl is required. Please install curl and try again.' >&2
        exit 1
    fi
    INSTALLER=$(mktemp)
    trap 'rm -f "$INSTALLER"' EXIT HUP INT TERM
    curl --fail --location --silent --show-error --retry 2 \
        https://astral.sh/uv/install.sh -o "$INSTALLER"
    UV_INSTALL_DIR="$PROJECT_ROOT/.tools/uv" UV_NO_MODIFY_PATH=1 sh "$INSTALLER"
    rm -f "$INSTALLER"
    trap - EXIT HUP INT TERM
    UV_BIN="$PROJECT_ROOT/.tools/uv/uv"
fi

exec "$UV_BIN" run --no-project --no-config --no-env-file --python '>=3.11' \
    "$PROJECT_ROOT/scripts/deploy.py" --uv "$UV_BIN" "$@"

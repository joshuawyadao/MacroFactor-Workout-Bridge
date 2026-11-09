#!/bin/sh
# Provision only the reviewed interpreter; stdout is the path for PYTHON_BIN.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKTREE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
UV_VERSION=0.13.7
PYTHON_VERSION=3.11.17

if [ "$#" -ne 0 ]; then
    printf 'Usage: %s (prints the local Python path)\n' "$0" >&2
    exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
    printf 'Install uv %s first; see docs/Development.md#reproducible-local-python.\n' "$UV_VERSION" >&2
    exit 1
fi
case "$(uv --version)" in
    "uv $UV_VERSION"|"uv $UV_VERSION ("*) ;;
    *)
        printf 'This setup requires uv %s; see docs/Development.md#reproducible-local-python.\n' "$UV_VERSION" >&2
        exit 1
        ;;
esac

# Keep downloads/cache local and avoid adding executables to a user bin directory.
export UV_PYTHON_INSTALL_DIR="$WORKTREE_ROOT/.venv/python"
export UV_CACHE_DIR="$WORKTREE_ROOT/.venv/uv-cache"
uv --no-config --no-progress python install --no-bin "cpython@$PYTHON_VERSION" >&2
LOCAL_PYTHON=$(uv --no-config python find --managed-python --no-python-downloads \
    --no-project "cpython@$PYTHON_VERSION")
case "$LOCAL_PYTHON" in
    "$UV_PYTHON_INSTALL_DIR"/*) ;;
    *) printf 'uv returned a Python outside the checkout-local installation.\n' >&2; exit 1 ;;
esac
"$LOCAL_PYTHON" -I "$SCRIPT_DIR/check_build_python.py" >&2
"$LOCAL_PYTHON" -I -c "import ensurepip, ssl, sys, venv; assert sys.version_info[:3] == (3, 11, 17)"
printf '%s\n' "$LOCAL_PYTHON"

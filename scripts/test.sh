#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKTREE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
GIT_COMMON_DIR=$(git -C "$WORKTREE_ROOT" rev-parse --git-common-dir)
case "$GIT_COMMON_DIR" in
    /*) ;;
    *) GIT_COMMON_DIR="$WORKTREE_ROOT/$GIT_COMMON_DIR" ;;
esac
GIT_COMMON_DIR=$(CDPATH= cd -- "$GIT_COMMON_DIR" && pwd)
SHARED_ROOT=$(dirname -- "$GIT_COMMON_DIR")
BOOTSTRAP_PYTHON=${PYTHON_BIN:-python3}
TEST_REQUIREMENTS="$WORKTREE_ROOT/requirements/test.lock"
TEST_VENV_ROOT=${MACROFACTOR_TEST_VENV_ROOT:-"$SHARED_ROOT/.venv/worktree-tests"}

python_is_supported() {
    "$1" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1
}

if ! python_is_supported "$BOOTSTRAP_PYTHON"; then
    printf 'Python 3.11 or newer is required to provision the test environment.\n' >&2
    exit 1
fi

REQUIREMENTS_FINGERPRINT=$(
    "$BOOTSTRAP_PYTHON" -c \
        'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' \
        "$TEST_REQUIREMENTS"
)
PYTHON_KEY=$(
    "$BOOTSTRAP_PYTHON" -c \
        'import sys; print(f"py{sys.version_info.major}.{sys.version_info.minor}")'
)
ENVIRONMENT_KEY="$PYTHON_KEY-$REQUIREMENTS_FINGERPRINT"
TEST_VENV="$TEST_VENV_ROOT/$ENVIRONMENT_KEY"
TEST_PYTHON="$TEST_VENV/bin/python"
STAMP_FILE="$TEST_VENV/.macrofactor-test-requirements.sha256"
LOCK_DIR="$TEST_VENV.provision-lock"

if [ "${1:-}" = "--print-venv" ]; then
    printf '%s\n' "$TEST_VENV"
    exit 0
fi

if [ -x "$TEST_PYTHON" ] && ! python_is_supported "$TEST_PYTHON"; then
    printf 'The existing test environment uses an unsupported Python: %s\n' "$TEST_VENV" >&2
    printf 'Remove that fingerprinted environment so it can be provisioned again.\n' >&2
    exit 1
fi

environment_ready() {
    [ -x "$TEST_PYTHON" ] &&
        python_is_supported "$TEST_PYTHON" &&
        [ -f "$STAMP_FILE" ] &&
        [ "$(cat "$STAMP_FILE")" = "$REQUIREMENTS_FINGERPRINT" ] &&
        "$TEST_PYTHON" -c 'from PySide6 import QtWidgets' >/dev/null 2>&1
}

release_lock() {
    rmdir "$LOCK_DIR" 2>/dev/null || true
}

acquire_lock() {
    mkdir -p "$(dirname -- "$LOCK_DIR")"
    attempts=0
    until mkdir "$LOCK_DIR" 2>/dev/null; do
        attempts=$((attempts + 1))
        if [ "$attempts" -ge 300 ]; then
            printf 'Timed out waiting for test environment lock: %s\n' "$LOCK_DIR" >&2
            printf 'Remove it only if no other worktree is provisioning the environment.\n' >&2
            exit 1
        fi
        sleep 0.1
    done
    trap release_lock EXIT HUP INT TERM
}

if ! environment_ready; then
    acquire_lock
    if ! environment_ready; then
        if [ ! -x "$TEST_PYTHON" ]; then
            "$BOOTSTRAP_PYTHON" -m venv "$TEST_VENV"
        fi
        "$TEST_PYTHON" -m pip install \
            --disable-pip-version-check \
            --requirement "$TEST_REQUIREMENTS"
        printf '%s\n' "$REQUIREMENTS_FINGERPRINT" > "$STAMP_FILE"
    fi
    release_lock
    trap - EXIT HUP INT TERM
fi

if ! environment_ready; then
    printf 'The shared test environment could not import PySide6 after provisioning.\n' >&2
    exit 1
fi

export QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-offscreen}
if [ -n "${PYTHONPATH:-}" ]; then
    export PYTHONPATH="$WORKTREE_ROOT/src:$PYTHONPATH"
else
    export PYTHONPATH="$WORKTREE_ROOT/src"
fi

cd "$WORKTREE_ROOT"
exec "$TEST_PYTHON" -m unittest discover -s tests -v

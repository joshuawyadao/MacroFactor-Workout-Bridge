#!/bin/sh
set -eu

check_result() {
  job=$1
  result=$2
  if [ "$result" != success ]; then
    printf '%s check result: %s\n' "$job" "$result" >&2
    exit 1
  fi
}

check_result PORTABLE "${PORTABLE_RESULT:-missing}"
check_result PACKAGED_APP "${PACKAGED_APP_RESULT:-missing}"

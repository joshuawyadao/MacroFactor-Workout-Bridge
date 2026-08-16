#!/bin/zsh
set -euo pipefail

APP_ROOT="${0:A:h:h}"
cd "$APP_ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  print -u2 "This packaging script creates a macOS .app and must run on macOS."
  exit 1
fi

BUILD_PYTHON="${PYTHON_BIN:-python3}"
BUILD_VENV="$APP_ROOT/.app-build-venv"
ICONSET="$APP_ROOT/build/AppIcon.iconset"
ICON_FILE="$APP_ROOT/build/MacroFactor Workout Bridge.icns"
APP_BUNDLE="$APP_ROOT/dist/MacroFactor Workout Bridge.app"

if [[ ! -x "$BUILD_VENV/bin/python" ]]; then
  "$BUILD_PYTHON" -m venv "$BUILD_VENV"
fi

"$BUILD_VENV/bin/python" -m pip install --upgrade pip
"$BUILD_VENV/bin/python" -m pip install -e ".[app-build]"
"$BUILD_VENV/bin/python" packaging/build_icon.py "$ICONSET"
iconutil --convert icns --output "$ICON_FILE" "$ICONSET"

"$BUILD_VENV/bin/python" -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$APP_ROOT/dist" \
  --workpath "$APP_ROOT/build/pyinstaller" \
  "$APP_ROOT/packaging/MacroFactor Workout Bridge.spec"

codesign --force --deep --sign - "$APP_BUNDLE"
codesign --verify --deep --strict "$APP_BUNDLE"

print "Built and verified: $APP_BUNDLE"

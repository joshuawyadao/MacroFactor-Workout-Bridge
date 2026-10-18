"""Check the reviewed Python runtime before recreating the macOS build environment."""

import sys


def main() -> int:
    version = sys.version_info
    if version[:2] != (3, 11) or version.micro < 17 or version.releaselevel != "final":
        print(
            "The macOS build requires final Python 3.11.17 or a later 3.11 patch. "
            f"Selected: {sys.version.split()[0]} ({sys.executable}). "
            "Set PYTHON_BIN=/path/to/patched/python3.11 and retry. "
            "The reviewed build locks target Python 3.11.",
            file=sys.stderr,
        )
        return 1
    print(f"Building with Python {sys.version.split()[0]} ({sys.executable}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

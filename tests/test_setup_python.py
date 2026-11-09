from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PythonSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="python setup ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "scripts").mkdir()
        for name in ("setup_python.sh", "check_build_python.py"):
            shutil.copy2(ROOT / "scripts" / name, self.root / "scripts" / name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=f"{self.bin}:/usr/bin:/bin")
        self.python = self.root / ".venv/python/reviewed/bin/python3.11"

    def fake_uv(self) -> None:
        uv = self.bin / "uv"
        uv.write_text('''#!/bin/sh
set -eu
case "$*" in
  --version) printf '%s\\n' "${TEST_UV_VERSION:-uv 0.13.7}" ;;
  *"python install"*)
    [ "${TEST_DOWNLOAD_FAIL:-0}" = 0 ] || exit 42
    mkdir -p "$UV_PYTHON_INSTALL_DIR/reviewed/bin"
    if [ ! -f "$UV_PYTHON_INSTALL_DIR/reviewed/bin/python3.11" ]; then
      printf '#!/bin/sh\\nexit 0\\n' > "$UV_PYTHON_INSTALL_DIR/reviewed/bin/python3.11"
      chmod +x "$UV_PYTHON_INSTALL_DIR/reviewed/bin/python3.11"
    fi
    ;;
  *"python find"*) printf '%s\\n' "${TEST_FOUND_PYTHON:-$UV_PYTHON_INSTALL_DIR/reviewed/bin/python3.11}" ;;
  *) exit 99 ;;
esac
''')
        uv.chmod(0o755)

    def run_setup(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(self.root / "scripts/setup_python.sh"), *args],
            cwd="/", env=self.env, text=True, capture_output=True, check=False,
        )

    def test_missing_uv_explains_prerequisite_without_creating_environment(self) -> None:
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Install uv 0.13.7", result.stderr)
        self.assertFalse((self.root / ".venv").exists())

    def test_wrong_uv_fails_before_provisioning(self) -> None:
        self.fake_uv()
        self.env["TEST_UV_VERSION"] = "uv 0.1.0"
        result = self.run_setup()
        self.assertIn("requires uv 0.13.7", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / ".venv").exists())

    def test_setup_returns_path_with_spaces_and_preserves_existing_environment(self) -> None:
        self.fake_uv()
        sentinel = self.root / ".venv/audit/keep"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("existing environment")
        for _ in range(2):
            result = self.run_setup()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(self.python))
            self.assertEqual(sentinel.read_text(), "existing environment")

    def test_download_failure_returns_no_interpreter_path(self) -> None:
        self.fake_uv()
        self.env["TEST_DOWNLOAD_FAIL"] = "1"
        result = self.run_setup()
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_python_outside_local_installation_is_rejected(self) -> None:
        self.fake_uv()
        self.env["TEST_FOUND_PYTHON"] = sys.executable
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside the checkout", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_broken_local_runtime_is_rejected_without_returning_path(self) -> None:
        self.fake_uv()
        self.python.parent.mkdir(parents=True)
        self.python.write_text("#!/bin/sh\nexit 23\n")
        self.python.chmod(0o755)
        result = self.run_setup()
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_unknown_arguments_fail_before_provisioning(self) -> None:
        result = self.run_setup("--upgrade")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stderr)
        self.assertFalse((self.root / ".venv").exists())

    def test_version_or_module_check_failure_returns_no_interpreter_path(self) -> None:
        self.fake_uv()
        self.python.parent.mkdir(parents=True)
        # The build preflight succeeds, but the exact-version/module check fails.
        self.python.write_text('#!/bin/sh\n[ "$2" != "-c" ] || exit 24\n')
        self.python.chmod(0o755)
        result = self.run_setup()
        self.assertEqual(result.returncode, 24, result.stderr)
        self.assertEqual(result.stdout, "")

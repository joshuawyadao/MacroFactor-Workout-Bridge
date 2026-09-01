from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FAKE_PYTHON_ADAPTER = """#!/usr/bin/env python3
import os
import pathlib
import shutil
import sys
import time

arguments = sys.argv[1:]

if arguments[:2] == ["-m", "venv"]:
    environment = pathlib.Path(arguments[-1])
    if "--clear" in arguments and environment.exists():
        shutil.rmtree(environment)
    test_python = environment / "bin" / "python"
    test_python.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(__file__, test_python)
    test_python.chmod(0o755)
elif arguments[:2] == ["-m", "pip"]:
    with pathlib.Path(os.environ["FAKE_PYTHON_LOG"]).open("a") as log:
        log.write("provisioned\\n")
    time.sleep(0.5)
elif arguments[:2] == ["-m", "unittest"]:
    pass
elif arguments and arguments[0] == "-c" and "PySide6" in arguments[1]:
    pass
else:
    os.execv(sys.executable, [sys.executable, *arguments])
"""


def wait_for_file(path: Path, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not path.exists():
        if time.monotonic() >= deadline:
            raise AssertionError(f"Timed out waiting for {path}")
        time.sleep(0.01)


class BuildDependencyTests(unittest.TestCase):
    def test_optional_dependencies_match_the_reviewed_app_build_lock(self) -> None:
        project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
        lock_lines = {
            line.strip()
            for line in (PROJECT_ROOT / "requirements" / "app-build.lock").read_text().splitlines()
            if line and not line.startswith("#")
        }

        optional = project["project"]["optional-dependencies"]
        self.assertEqual(optional["desktop"], ["PySide6-Essentials==6.11.2"])
        self.assertEqual(
            optional["app-build"],
            ["PySide6-Essentials==6.11.2", "pyinstaller==6.22.2"],
        )
        self.assertIn("PySide6_Essentials==6.11.2", lock_lines)
        self.assertIn("pyinstaller==6.22.2", lock_lines)
        self.assertIn("shiboken6==6.11.2", lock_lines)

    def test_test_lock_matches_the_desktop_dependency(self) -> None:
        project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
        test_lock = PROJECT_ROOT / "requirements" / "test.lock"
        lock_lines = {
            line.strip()
            for line in test_lock.read_text().splitlines()
            if line and not line.startswith("#")
        }

        self.assertEqual(
            project["project"]["optional-dependencies"]["desktop"],
            ["PySide6-Essentials==6.11.2"],
        )
        self.assertEqual(
            lock_lines,
            {"PySide6_Essentials==6.11.2", "shiboken6==6.11.2"},
        )

    def test_test_runner_uses_a_fingerprinted_shared_virtualenv(self) -> None:
        common_dir = Path(
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(PROJECT_ROOT),
                    "rev-parse",
                    "--git-common-dir",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        if not common_dir.is_absolute():
            common_dir = PROJECT_ROOT / common_dir
        common_dir = common_dir.resolve()
        requirements = PROJECT_ROOT / "requirements" / "test.lock"
        fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
        python_key = f"py{sys.version_info.major}.{sys.version_info.minor}"
        result = subprocess.run(
            [str(PROJECT_ROOT / "scripts" / "test.sh"), "--print-venv"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            Path(result.stdout.strip()),
            common_dir.parent
            / ".venv"
            / "worktree-tests"
            / f"{python_key}-{fingerprint}",
        )

    def test_ci_and_contributor_docs_use_the_canonical_test_runner(self) -> None:
        checked_files = (
            "README.md",
            "CONTRIBUTING.md",
            ".github/workflows/ci-verify.yml",
        )
        for relative_path in checked_files:
            with self.subTest(relative_path=relative_path):
                text = (PROJECT_ROOT / relative_path).read_text()
                self.assertIn("./scripts/test.sh", text)

    def test_test_runner_honors_the_virtualenv_root_override(self) -> None:
        override_root = PROJECT_ROOT / ".test-venv-override"
        environment = os.environ.copy()
        environment["MACROFACTOR_TEST_VENV_ROOT"] = str(override_root)

        result = subprocess.run(
            [str(PROJECT_ROOT / "scripts" / "test.sh"), "--print-venv"],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )

        selected_environment = Path(result.stdout.strip())
        self.assertEqual(selected_environment.parent, override_root)
        self.assertRegex(selected_environment.name, r"^py\d+\.\d+-[0-9a-f]{64}$")

    def test_concurrent_runners_share_one_provisioned_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            fake_python = temporary_root / "fake-python"
            provision_log = temporary_root / "provision.log"
            virtualenv_root = temporary_root / "environments"
            fake_python.write_text(FAKE_PYTHON_ADAPTER)
            fake_python.chmod(0o755)

            environment = os.environ.copy()
            environment["PYTHON_BIN"] = str(fake_python)
            environment["MACROFACTOR_TEST_VENV_ROOT"] = str(virtualenv_root)
            environment["FAKE_PYTHON_LOG"] = str(provision_log)

            selection = subprocess.run(
                [str(PROJECT_ROOT / "scripts" / "test.sh"), "--print-venv"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            selected_environment = Path(selection.stdout.strip())

            first_runner = subprocess.Popen(
                [str(PROJECT_ROOT / "scripts" / "test.sh")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=environment,
            )
            wait_for_file(provision_log)
            provision_lock = Path(f"{selected_environment}.provision-lock")
            self.assertIsNone(first_runner.poll())
            self.assertTrue(provision_lock.is_dir())
            self.assertEqual(
                (provision_lock / "owner-pid").read_text().strip(),
                str(first_runner.pid),
            )
            second_runner = subprocess.Popen(
                [str(PROJECT_ROOT / "scripts" / "test.sh")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=environment,
            )

            for runner in (first_runner, second_runner):
                stdout, stderr = runner.communicate(timeout=10)
                self.assertEqual(runner.returncode, 0, stdout + stderr)

            self.assertEqual(provision_log.read_text().splitlines(), ["provisioned"])
            self.assertTrue(
                (selected_environment / ".macrofactor-test-requirements.sha256").is_file()
            )
            self.assertFalse(provision_lock.exists())

    def test_test_runner_recovers_a_lock_owned_by_a_dead_process(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            fake_python = temporary_root / "fake-python"
            provision_log = temporary_root / "provision.log"
            virtualenv_root = temporary_root / "environments"
            fake_python.write_text(FAKE_PYTHON_ADAPTER)
            fake_python.chmod(0o755)

            environment = os.environ.copy()
            environment["PYTHON_BIN"] = str(fake_python)
            environment["MACROFACTOR_TEST_VENV_ROOT"] = str(virtualenv_root)
            environment["FAKE_PYTHON_LOG"] = str(provision_log)
            selection = subprocess.run(
                [str(PROJECT_ROOT / "scripts" / "test.sh"), "--print-venv"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            provision_lock = Path(f"{selection.stdout.strip()}.provision-lock")
            provision_lock.mkdir(parents=True)
            (provision_lock / "owner-pid").write_text("99999999\n")

            result = subprocess.run(
                [str(PROJECT_ROOT / "scripts" / "test.sh")],
                capture_output=True,
                text=True,
                env=environment,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(provision_log.read_text().splitlines(), ["provisioned"])
            self.assertFalse(provision_lock.exists())

    def test_test_runner_recreates_an_incomplete_virtualenv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            fake_python = temporary_root / "fake-python"
            provision_log = temporary_root / "provision.log"
            virtualenv_root = temporary_root / "environments"
            fake_python.write_text(FAKE_PYTHON_ADAPTER)
            fake_python.chmod(0o755)

            environment = os.environ.copy()
            environment["PYTHON_BIN"] = str(fake_python)
            environment["MACROFACTOR_TEST_VENV_ROOT"] = str(virtualenv_root)
            environment["FAKE_PYTHON_LOG"] = str(provision_log)
            selection = subprocess.run(
                [str(PROJECT_ROOT / "scripts" / "test.sh"), "--print-venv"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            selected_environment = Path(selection.stdout.strip())
            incomplete_python = selected_environment / "bin" / "python"
            incomplete_python.parent.mkdir(parents=True)
            incomplete_python.write_text("#!/bin/sh\nexit 1\n")
            incomplete_python.chmod(0o755)

            result = subprocess.run(
                [str(PROJECT_ROOT / "scripts" / "test.sh")],
                capture_output=True,
                text=True,
                env=environment,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(provision_log.read_text().splitlines(), ["provisioned"])
            self.assertIn("FAKE_PYTHON_LOG", incomplete_python.read_text())

    def test_packaging_script_installs_the_lock_without_reresolving_dependencies(self) -> None:
        script = (PROJECT_ROOT / "scripts" / "build_macos_app.sh").read_text()

        self.assertIn('pip install --requirement "$APP_ROOT/requirements/app-build.lock"', script)
        self.assertIn('pip install --no-build-isolation --no-deps -e "$APP_ROOT"', script)

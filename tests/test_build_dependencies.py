from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HASH_PATTERN = re.compile(r"--hash=sha256:([0-9a-f]{64})(?: \\)?$")


def read_locked_requirements(relative_path: str) -> dict[str, list[str]]:
    requirements: dict[str, list[str]] = {}
    current_requirement: str | None = None

    for raw_line in (PROJECT_ROOT / relative_path).read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("--only-binary") or line == "--require-hashes":
            continue
        if "==" in line:
            if not line.endswith("\\"):
                raise AssertionError(f"Locked requirement has no hashes: {line}")
            name, version = line[:-1].strip().split("==", 1)
            current_requirement = f"{name.lower().replace('_', '-')}=={version}"
            requirements[current_requirement] = []
            continue

        if current_requirement is None:
            raise AssertionError(f"Unexpected lock line: {line}")
        match = HASH_PATTERN.fullmatch(line)
        if match is None:
            raise AssertionError(f"Invalid hash line: {line}")
        requirements[current_requirement].append(match.group(1))
        if not line.endswith("\\"):
            current_requirement = None

    if current_requirement is not None:
        raise AssertionError(f"Unterminated requirement: {current_requirement}")
    return requirements

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
    time.sleep(float(os.environ.get("FAKE_PYTHON_PROVISION_DELAY", "0.5")))
elif arguments[:2] == ["-m", "unittest"]:
    pythonpath_log = os.environ.get("FAKE_PYTHONPATH_LOG")
    if pythonpath_log:
        with pathlib.Path(pythonpath_log).open("a") as log:
            log.write(os.environ.get("PYTHONPATH", "") + "\\n")
elif arguments and arguments[0] == "-c" and "PySide6" in arguments[1]:
    pythonpath_log = os.environ.get("FAKE_PYTHONPATH_LOG")
    if pythonpath_log:
        with pathlib.Path(pythonpath_log).open("a") as log:
            log.write(os.environ.get("PYTHONPATH", "") + "\\n")
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
        locked = read_locked_requirements("requirements/app-build.lock")

        optional = project["project"]["optional-dependencies"]
        self.assertEqual(optional["desktop"], ["PySide6-Essentials==6.11.2"])
        self.assertEqual(
            optional["app-build"],
            ["PySide6-Essentials==6.11.2", "pyinstaller==6.22.2"],
        )
        self.assertIn("pyside6-essentials==6.11.2", locked)
        self.assertIn("pyinstaller==6.22.2", locked)
        self.assertIn("shiboken6==6.11.2", locked)

    def test_test_lock_matches_the_desktop_dependency(self) -> None:
        project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
        locked = read_locked_requirements("requirements/test.lock")

        self.assertEqual(
            project["project"]["optional-dependencies"]["desktop"],
            ["PySide6-Essentials==6.11.2"],
        )
        self.assertEqual(
            set(locked),
            {"pyside6-essentials==6.11.2", "shiboken6==6.11.2"},
        )

    def test_dependency_locks_require_binary_artifacts_and_sha256_hashes(self) -> None:
        for relative_path in (
            "requirements/audit.lock",
            "requirements/app-build.lock",
            "requirements/test.lock",
        ):
            with self.subTest(relative_path=relative_path):
                text = (PROJECT_ROOT / relative_path).read_text()
                self.assertIn("--only-binary=:all:", text)
                self.assertIn("--require-hashes", text)
                locked = read_locked_requirements(relative_path)
                self.assertTrue(locked)
                self.assertTrue(all(hashes for hashes in locked.values()))

    def test_installers_and_ci_enforce_locked_dependency_integrity(self) -> None:
        for relative_path in ("scripts/build_macos_app.sh", "scripts/test.sh"):
            with self.subTest(relative_path=relative_path):
                text = (PROJECT_ROOT / relative_path).read_text()
                self.assertIn("--only-binary=:all:", text)
                self.assertIn("--require-hashes", text)

        workflow = (PROJECT_ROOT / ".github/workflows/ci-verify.yml").read_text()
        audit_locked = read_locked_requirements("requirements/audit.lock")
        audit_requirements = [
            requirement for requirement in audit_locked if requirement.startswith("pip-audit==")
        ]
        self.assertEqual(len(audit_requirements), 1)
        self.assertNotIn('"pip-audit==', workflow)
        self.assertIn("cache-dependency-path: |\n            requirements/audit.lock", workflow)

        install_start = workflow.index("- name: Install reviewed dependency-audit tooling")
        audit_start = workflow.index("- name: Audit locked Python dependencies")
        install_step = workflow[install_start:audit_start]
        self.assertIn("python -m pip install", install_step)
        self.assertIn("--only-binary=:all:", install_step)
        self.assertIn("--require-hashes", install_step)
        self.assertIn("--requirement requirements/audit.lock", install_step)

        audit_step = workflow[audit_start:]
        self.assertIn("python -m pip_audit", audit_step)
        self.assertIn("--disable-pip", audit_step)
        self.assertIn("--require-hashes", audit_step)
        self.assertIn("--requirement requirements/audit.lock", audit_step)
        self.assertIn("--requirement requirements/app-build.lock", audit_step)
        self.assertIn("--requirement requirements/test.lock", audit_step)

    def test_macos_builder_recreates_environment_before_locked_install(self) -> None:
        script = (PROJECT_ROOT / "scripts" / "build_macos_app.sh").read_text()
        preflight = '"$BUILD_PYTHON" "$APP_ROOT/scripts/check_build_python.py"'
        recreation = '"$BUILD_PYTHON" -m venv --clear "$BUILD_VENV"'
        locked_install = '"$BUILD_VENV/bin/python" -m pip install \\\n'

        self.assertEqual(script.count(recreation), 1)
        self.assertLess(script.index(preflight), script.index(recreation))
        self.assertLess(script.index(recreation), script.index(locked_install))

    def test_build_runtime_requires_a_patched_final_python_311(self) -> None:
        preflight = PROJECT_ROOT / "scripts" / "check_build_python.py"
        for version, accepted in (
            ((3, 11, 2, "final", 0), False),
            ((3, 11, 16, "final", 0), False),
            ((3, 11, 17, "candidate", 1), False),
            ((3, 11, 18, "alpha", 1), False),
            ((3, 12, 15, "final", 0), False),
            ((3, 11, 17, "final", 0), True),
            ((3, 11, 18, "final", 0), True),
        ):
            with self.subTest(version=version):
                result = subprocess.run(
                    [
                        sys.executable, "-c",
                        "import collections, runpy, sys; "
                        "Version = collections.namedtuple('Version', "
                        "'major minor micro releaselevel serial'); "
                        f"sys.version_info = Version{version!r}; "
                        "runpy.run_path(sys.argv[1], run_name='__main__')",
                        str(preflight),
                    ],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0 if accepted else 1, result.stderr)
                if not accepted:
                    self.assertIn("PYTHON_BIN=", result.stderr)
                    self.assertIn("3.11.17", result.stderr)

    @unittest.skipUnless(sys.platform == "darwin", "macOS packaging script")
    def test_rejected_build_runtime_preserves_the_existing_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            scripts = root / "scripts"
            scripts.mkdir()
            for name in ("build_macos_app.sh", "check_build_python.py"):
                shutil.copy2(PROJECT_ROOT / "scripts" / name, scripts / name)
            sentinel = root / ".app-build-venv" / "keep-existing-environment"
            sentinel.parent.mkdir()
            sentinel.write_text("existing build")
            fake_python = root / "unsupported-python"
            fake_python.write_text("#!/bin/sh\nexit 1\n")
            fake_python.chmod(0o755)
            result = subprocess.run(
                [str(scripts / "build_macos_app.sh")],
                env={**os.environ, "PYTHON_BIN": str(fake_python)},
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("PYTHON_BIN", result.stderr)
            self.assertEqual(sentinel.read_text(), "existing build")

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
        interpreter = hashlib.sha256(str(Path(sys.executable).resolve()).encode()).hexdigest()[:12]
        python_key = f"py{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}-{interpreter}"
        environment = os.environ.copy()
        environment["PYTHON_BIN"] = sys.executable
        environment.pop("MACROFACTOR_TEST_VENV_ROOT", None)
        result = subprocess.run(
            [str(PROJECT_ROOT / "scripts" / "test.sh"), "--print-venv"],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
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
            "docs/Development.md",
            ".github/workflows/ci-verify.yml",
        )
        for relative_path in checked_files:
            with self.subTest(relative_path=relative_path):
                text = (PROJECT_ROOT / relative_path).read_text()
                self.assertIn("./scripts/test.sh", text)

    def test_documented_audit_environment_uses_the_locked_python_version(self) -> None:
        text = (PROJECT_ROOT / "docs/Development.md").read_text()
        self.assertIn("python3.11 -m venv --clear .venv/audit", text)

    def test_documentation_entry_points_link_to_the_verification_guide(self) -> None:
        for relative_path in ("README.md", "CONTRIBUTING.md"):
            with self.subTest(relative_path=relative_path):
                text = (PROJECT_ROOT / relative_path).read_text()
                self.assertIn(
                    "docs/Development.md",
                    re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", text),
                )

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
        self.assertRegex(selected_environment.name, r"^py\d+\.\d+\.\d+-[0-9a-f]{12}-[0-9a-f]{64}$")

    def test_python_patch_upgrade_selects_a_new_test_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = []
            for patch in (2, 17):
                fake_python = root / f"python-3.11.{patch}"
                fake_python.write_text(
                    "#!/usr/bin/env python3\n"
                    "import collections, sys\n"
                    "Version = collections.namedtuple('Version', "
                    "'major minor micro releaselevel serial')\n"
                    f"sys.version_info = Version(3, 11, {patch}, 'final', 0)\n"
                    "code = sys.argv[2]\n"
                    "sys.argv = sys.argv[2:]\n"
                    "exec(code)\n"
                )
                fake_python.chmod(0o755)
                result = subprocess.run(
                    [str(PROJECT_ROOT / "scripts" / "test.sh"), "--print-venv"],
                    env={**os.environ, "PYTHON_BIN": str(fake_python),
                         "MACROFACTOR_TEST_VENV_ROOT": str(root / "environments")},
                    capture_output=True, text=True, check=True,
                )
                selected.append(Path(result.stdout.strip()))
            self.assertNotEqual(selected[0], selected[1])

    def test_same_version_interpreter_switch_selects_a_new_test_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = []
            for name in ("first-python", "second-python"):
                fake_python = root / name
                fake_python.write_text(
                    "#!/usr/bin/env python3\n"
                    "import sys\n"
                    "sys.executable = __file__\n"
                    "code = sys.argv[2]\n"
                    "sys.argv = sys.argv[2:]\n"
                    "exec(code)\n"
                )
                fake_python.chmod(0o755)
                result = subprocess.run(
                    [str(PROJECT_ROOT / "scripts" / "test.sh"), "--print-venv"],
                    env={**os.environ, "PYTHON_BIN": str(fake_python),
                         "MACROFACTOR_TEST_VENV_ROOT": str(root / "environments")},
                    capture_output=True, text=True, check=True,
                )
                selected.append(Path(result.stdout.strip()))
            self.assertNotEqual(selected[0], selected[1])

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

    def test_test_runner_excludes_the_callers_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            fake_python = temporary_root / "fake-python"
            provision_log = temporary_root / "provision.log"
            pythonpath_log = temporary_root / "pythonpath.log"
            virtualenv_root = temporary_root / "environments"
            caller_pythonpath = temporary_root / "caller-packages"
            fake_python.write_text(FAKE_PYTHON_ADAPTER)
            fake_python.chmod(0o755)
            caller_pythonpath.mkdir()

            environment = os.environ.copy()
            environment["PYTHON_BIN"] = str(fake_python)
            environment["MACROFACTOR_TEST_VENV_ROOT"] = str(virtualenv_root)
            environment["FAKE_PYTHON_LOG"] = str(provision_log)
            environment["FAKE_PYTHONPATH_LOG"] = str(pythonpath_log)
            environment["PYTHONPATH"] = str(caller_pythonpath)

            result = subprocess.run(
                [str(PROJECT_ROOT / "scripts" / "test.sh")],
                capture_output=True,
                text=True,
                env=environment,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            observed_paths = pythonpath_log.read_text().splitlines()
            self.assertGreaterEqual(len(observed_paths), 2)
            self.assertEqual(set(observed_paths), {str(PROJECT_ROOT / "src")})

    def test_test_runner_exits_after_a_provisioning_signal(self) -> None:
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
            environment["FAKE_PYTHON_PROVISION_DELAY"] = "1"
            selection = subprocess.run(
                [str(PROJECT_ROOT / "scripts" / "test.sh"), "--print-venv"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            selected_environment = Path(selection.stdout.strip())
            provision_lock = Path(f"{selected_environment}.provision-lock")

            runner = subprocess.Popen(
                [str(PROJECT_ROOT / "scripts" / "test.sh")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=environment,
            )
            wait_for_file(provision_log)
            self.assertTrue(provision_lock.is_dir())
            runner.terminate()
            stdout, stderr = runner.communicate(timeout=10)

            self.assertEqual(runner.returncode, 143, stdout + stderr)
            self.assertFalse(provision_lock.exists())
            self.assertFalse(
                (selected_environment / ".macrofactor-test-requirements.sha256").exists()
            )

    def test_packaging_script_installs_the_lock_without_reresolving_dependencies(self) -> None:
        script = (PROJECT_ROOT / "scripts" / "build_macos_app.sh").read_text()

        self.assertIn('--requirement "$APP_ROOT/requirements/app-build.lock"', script)
        self.assertIn('pip install --no-build-isolation --no-deps -e "$APP_ROOT"', script)

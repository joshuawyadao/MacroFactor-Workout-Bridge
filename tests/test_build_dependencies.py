from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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

    def test_packaging_script_installs_the_lock_without_reresolving_dependencies(self) -> None:
        script = (PROJECT_ROOT / "scripts" / "build_macos_app.sh").read_text()

        self.assertIn('pip install --requirement "$APP_ROOT/requirements/app-build.lock"', script)
        self.assertIn('pip install --no-build-isolation --no-deps -e "$APP_ROOT"', script)

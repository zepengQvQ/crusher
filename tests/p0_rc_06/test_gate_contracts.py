"""
P0-RC-06：门禁契约——lint 不吞错、H5 有 vitest、旧冒烟命名已纠正。
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Rc06GateTests(unittest.TestCase):
    def test_makefile_lint_uses_venv_and_no_true(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        lint_block = re.search(r"^lint:\n((?:\t.*\n)+)", makefile, re.M)
        self.assertIsNotNone(lint_block)
        body = lint_block.group(1)
        self.assertIn(".venv/bin/ruff", body)
        self.assertIn(".venv/bin/pyright", body)
        self.assertNotIn("|| true", body)

    def test_run_all_tests_requires_project_venv(self) -> None:
        script = (ROOT / "scripts" / "run_all_tests.sh").read_text(encoding="utf-8")
        self.assertIn("make setup", script)
        self.assertIn("exit 1", script)
        self.assertNotIn('PY="python3"', script)
        self.assertIn("npm test", script)

    def test_h5_package_has_vitest_script(self) -> None:
        pkg = (ROOT / "frontend-h5" / "package.json").read_text(encoding="utf-8")
        self.assertIn('"test": "vitest run"', pkg)
        self.assertIn("vitest", pkg)
        self.assertIn("@vue/test-utils", pkg)
        specs = list((ROOT / "frontend-h5" / "src" / "__tests__").glob("*.spec.js"))
        self.assertGreaterEqual(len(specs), 2)

    def test_p0_08_no_longer_named_smoke_or_e2e(self) -> None:
        p008 = ROOT / "tests" / "p0_08"
        names = {p.name for p in p008.iterdir() if p.is_file()}
        self.assertNotIn("test_h5_smoke.py", names)
        self.assertNotIn("test_e2e_api.py", names)
        self.assertIn("test_h5_structure.py", names)
        self.assertIn("test_api_integration.py", names)
        structure = (p008 / "test_h5_structure.py").read_text(encoding="utf-8")
        self.assertNotIn("Smoke", structure)
        self.assertIn("结构契约", structure)
        api = (p008 / "test_api_integration.py").read_text(encoding="utf-8")
        self.assertNotIn("ApiE2ETests", api)
        self.assertIn("ApiIntegrationTests", api)


if __name__ == "__main__":
    unittest.main()

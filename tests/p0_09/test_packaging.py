"""
P0-09：Demo 包装契约（锁文件、启动脚本、VS Code、无业务 sys.path）。
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PackagingContractTests(unittest.TestCase):
    def test_lock_files_exist(self):
        self.assertTrue((ROOT / "backend-python" / "requirements.lock").is_file())
        self.assertTrue((ROOT / "frontend-h5" / "package-lock.json").is_file())

    def test_dev_script_and_makefile_targets(self):
        dev = (ROOT / "scripts" / "dev.sh").read_text(encoding="utf-8")
        self.assertIn("MOCK_MODE", dev)
        self.assertIn("uvicorn", dev)
        self.assertIn("npm run dev", dev)
        self.assertIn("不用 Docker", dev)
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        for target in ("setup", "demo", "test", "export-openapi"):
            self.assertIn(target, makefile)

    def test_vscode_launch_and_http_examples(self):
        launch = ROOT / ".vscode" / "launch.json"
        self.assertTrue(launch.is_file())
        text = launch.read_text(encoding="utf-8")
        self.assertIn("Crusher API", text)
        http = ROOT / "docs" / "http" / "analyze.http"
        self.assertTrue(http.is_file())
        self.assertIn("/api/v1/analyses", http.read_text(encoding="utf-8"))

    def test_readme_has_java_onboarding(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for needle in (
            "20 分钟",
            "MOCK_MODE",
            "make test",
            "scripts/dev.sh",
            "java-python-map",
            "不用 Docker",
        ):
            self.assertIn(needle, readme)

    def test_backend_app_has_no_sys_path_mutation(self):
        app_root = ROOT / "backend-python" / "app"
        offenders = []
        for path in app_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    if node.value.id == "sys" and node.attr == "path":
                        offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_export_openapi_does_not_insert_sys_path(self):
        src = (ROOT / "scripts" / "export_openapi.py").read_text(encoding="utf-8")
        self.assertNotIn("sys.path.insert", src)

    def test_demo_samples_doc_exists(self):
        doc = ROOT / "docs" / "demo-samples.md"
        self.assertTrue(doc.is_file())
        self.assertIn("mock_smoke_pack", doc.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

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
        http = ROOT / "docs" / "http" / "示例-分析接口.http"
        self.assertTrue(http.is_file())
        self.assertIn("/api/v1/analyses", http.read_text(encoding="utf-8"))

    def test_readme_has_java_onboarding(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for needle in (
            "20 分钟",
            "MOCK_MODE",
            "make test",
            "scripts/dev.sh",
            "docs/project.md",
            "project.md",
            "不用 Docker",
        ):
            self.assertIn(needle, readme)

    def test_docs_hub_and_project_md_convention(self):
        hub = (ROOT / "docs" / "project.md").read_text(encoding="utf-8")
        self.assertIn("文档怎么找", hub)
        self.assertIn("开发地图-代码与请求链路.md", hub)
        self.assertIn("demo-支持范围与样例.md", hub)
        self.assertIn("agent-改代码约定.md", hub)
        self.assertIn("archive/", hub)
        self.assertTrue((ROOT / "docs" / "开发地图-代码与请求链路.md").is_file())
        self.assertTrue((ROOT / "docs" / "demo-支持范围与样例.md").is_file())
        self.assertTrue(
            (ROOT / "docs" / "archive" / "整改实施清单-P0.md").is_file()
        )
        self.assertTrue(
            (ROOT / "docs" / "archive" / "P0收口修复-Cursor执行清单.md").is_file()
        )
        self.assertFalse((ROOT / "docs" / "整改实施清单-P0.md").exists())
        self.assertFalse((ROOT / "docs" / "demo-samples.md").exists())
        self.assertFalse((ROOT / "docs" / "java-python-map.md").exists())
        self.assertFalse((ROOT / "docs" / "README.md").exists())
        self.assertFalse((ROOT / "docs" / "cursor.md").exists())
        for rel in (
            "backend-python/project.md",
            "frontend-h5/project.md",
            "tests/project.md",
            "knowledge/project.md",
            "data/demo-样例条款.json",
            "docs/api/示例-创建分析请求.json",
            "docs/http/示例-分析接口.http",
            "docs/archive/project.md",
            "tests/对照-期望输出样例.json",
            "tests/样例-结构性存款.json",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

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

    def test_demo_scope_lists_samples(self):
        doc = (ROOT / "docs" / "demo-支持范围与样例.md").read_text(encoding="utf-8")
        self.assertIn("样例从哪点", doc)
        self.assertIn("mock_smoke_pack", doc)


if __name__ == "__main__":
    unittest.main()

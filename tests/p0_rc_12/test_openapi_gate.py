"""P0-RC-12：OpenAPI / JSDoc / 门禁可信。"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.domain.models import ApiErrorDetail, ApiErrorResponse  # noqa: E402
from app.main import create_app  # noqa: E402
from app.shared.constants import MAX_INPUT_CHARS  # noqa: E402


class ApiErrorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(create_app())

    def _assert_api_error(self, payload: object) -> ApiErrorResponse:
        parsed = ApiErrorResponse.model_validate(payload)
        self.assertIsInstance(parsed.detail, ApiErrorDetail)
        self.assertTrue(parsed.detail.error_code)
        self.assertTrue(parsed.detail.message)
        return parsed

    def test_400_too_long_matches_dto(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={"text": "啊" * (MAX_INPUT_CHARS + 1)},
        )
        self.assertEqual(res.status_code, 400)
        parsed = self._assert_api_error(res.json())
        self.assertEqual(parsed.detail.error_code, "INPUT_TOO_LONG")
        self.assertEqual(parsed.detail.max_input_chars, MAX_INPUT_CHARS)

    def test_404_task_not_found_matches_dto(self) -> None:
        res = self.client.get("/api/v1/analyses/tsk_does_not_exist")
        self.assertEqual(res.status_code, 404)
        parsed = self._assert_api_error(res.json())
        self.assertEqual(parsed.detail.error_code, "TASK_NOT_FOUND")

    def test_422_validation_matches_dto(self) -> None:
        res = self.client.post("/api/v1/analyses", json={"text": "   "})
        self.assertEqual(res.status_code, 422)
        parsed = self._assert_api_error(res.json())
        self.assertEqual(parsed.detail.error_code, "VALIDATION_ERROR")


class OpenApiErrorSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = create_app().openapi()
        self.components = self.schema["components"]["schemas"]

    def test_api_error_schemas_present(self) -> None:
        self.assertIn("ApiErrorDetail", self.components)
        self.assertIn("ApiErrorResponse", self.components)
        detail = self.components["ApiErrorDetail"]["properties"]
        self.assertIn("error_code", detail)
        self.assertIn("message", detail)

    def test_post_declares_400_and_422(self) -> None:
        post = self.schema["paths"]["/api/v1/analyses"]["post"]["responses"]
        self.assertIn("400", post)
        self.assertIn("422", post)
        for code in ("400", "422"):
            ref = post[code]["content"]["application/json"]["schema"]["$ref"]
            self.assertTrue(ref.endswith("/ApiErrorResponse"))

    def test_get_declares_404(self) -> None:
        get = self.schema["paths"]["/api/v1/analyses/{task_id}"]["get"]["responses"]
        self.assertIn("404", get)
        ref = get["404"]["content"]["application/json"]["schema"]["$ref"]
        self.assertTrue(ref.endswith("/ApiErrorResponse"))

    def test_request_text_has_max_length(self) -> None:
        text = self.components["CreateAnalysisRequest"]["properties"]["text"]
        self.assertEqual(text.get("maxLength"), MAX_INPUT_CHARS)


class GeneratedJsdocTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gen = (ROOT / "frontend-h5" / "src" / "api" / "generated-types.js").read_text(
            encoding="utf-8"
        )

    def test_optional_property_syntax(self) -> None:
        self.assertIn("@typedef {Object} CreateAnalysisRequest", self.gen)
        self.assertIn("@property {ProductHintValue} [product_hint]", self.gen)
        self.assertNotIn("[optional]", self.gen)

    def test_enum_value_typedef(self) -> None:
        self.assertIn("@typedef {", self.gen)
        self.assertIn("ProductHintValue", self.gen)
        self.assertRegex(self.gen, r"@typedef \{[^}]+\} ProductHintValue")

    def test_max_input_chars_exported(self) -> None:
        self.assertIn(f"export const MAX_INPUT_CHARS = {MAX_INPUT_CHARS}", self.gen)


class OpenApiDriftGateTests(unittest.TestCase):
    def test_disk_matches_runtime_openapi(self) -> None:
        live = create_app().openapi()
        disk = json.loads((ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8"))
        self.assertEqual(disk, live)

    def test_unexported_change_would_fail_gate(self) -> None:
        """模拟未重新导出：磁盘契约被篡改后与运行时不一致。"""
        path = ROOT / "contracts" / "openapi.json"
        original = path.read_text(encoding="utf-8")
        try:
            mutated = json.loads(original)
            mutated["info"]["title"] = "drift-probe"
            path.write_text(json.dumps(mutated, ensure_ascii=False, indent=2), encoding="utf-8")
            live = create_app().openapi()
            disk = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotEqual(disk, live)
        finally:
            path.write_text(original, encoding="utf-8")


class SetupAndTypecheckTests(unittest.TestCase):
    def test_package_lock_lists_vitest_and_typescript(self) -> None:
        lock = (ROOT / "frontend-h5" / "package-lock.json").read_text(encoding="utf-8")
        self.assertIn('"vitest"', lock)
        self.assertIn('"typescript"', lock)

    def test_dev_sh_always_syncs_npm_ci(self) -> None:
        script = (ROOT / "scripts" / "dev.sh").read_text(encoding="utf-8")
        self.assertIn("npm ci", script)
        self.assertNotIn("if [[ ! -d frontend-h5/node_modules ]]", script)

    def test_typecheck_catches_bad_property(self) -> None:
        if shutil.which("npx") is None:
            self.skipTest("npx unavailable")
        tsc = ROOT / "frontend-h5" / "node_modules" / ".bin" / "tsc"
        if not tsc.exists():
            self.skipTest("typescript not installed; run make setup")
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad-check.js"
            bad.write_text(
                "/** @typedef {{ ok: string }} Sample */\n"
                "/** @type {Sample} */\n"
                "const x = { nope: 1 }\n"
                "export {}\n",
                encoding="utf-8",
            )
            cfg = Path(tmp) / "jsconfig.json"
            cfg.write_text(
                json.dumps(
                    {
                        "compilerOptions": {
                            "checkJs": True,
                            "allowJs": True,
                            "noEmit": True,
                            "strict": False,
                        },
                        "include": ["bad-check.js"],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [str(tsc), "-p", str(cfg), "--noEmit"],
                cwd=tmp,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            self.assertTrue(
                re.search(r"nope|does not exist|unknown", proc.stdout + proc.stderr, re.I)
            )


if __name__ == "__main__":
    unittest.main()

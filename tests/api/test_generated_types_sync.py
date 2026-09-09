"""收口验收：OpenAPI 与前端 generated-types 保持同步。"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class GeneratedTypesSyncTests(unittest.TestCase):
    def test_generated_types_cover_openapi_enums_and_priority_dto(self) -> None:
        openapi = json.loads((ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8"))
        schemas = openapi["components"]["schemas"]
        gen = (ROOT / "frontend-h5" / "src" / "api" / "generated-types.js").read_text(encoding="utf-8")

        # 关键枚举必须从 OpenAPI 生成到前端
        for enum_name in ("TaskStatus", "FindingSeverity", "FactStatus", "ErrorCode", "StageStatus"):
            self.assertIn(enum_name, schemas)
            self.assertIn(f"export const {enum_name}", gen)
            for value in schemas[enum_name].get("enum", []):
                self.assertIn(json.dumps(value, ensure_ascii=False), gen)

        # 关键 DTO 必须有 JSDoc typedef
        for dto in (
            "AnalysisReport",
            "Finding",
            "Evidence",
            "TaskResponse",
            "CreateAnalysisRequest",
        ):
            self.assertIn(f"@typedef {{Object}} {dto}", gen)
            self.assertTrue(re.search(rf"export const SCHEMA_NAMES = .*\"{dto}\"", gen))

        self.assertIn("export const ProductHint", gen)
        self.assertIn("source_text", gen)

if __name__ == "__main__":
    unittest.main()

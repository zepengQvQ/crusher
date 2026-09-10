"""P2-06：LlmAnalysisDraft Schema 与解析契约。"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.domain.llm_errors import LlmInvalidJsonError  # noqa: E402
from app.domain.models.llm import LlmAnalysisDraft, make_simple_draft  # noqa: E402
from app.infrastructure.llm.mock_gateway import MockLlmGateway  # noqa: E402
from app.infrastructure.llm.openai_compatible_gateway import (  # noqa: E402
    parse_llm_explanation_content,
)
from app.domain.models.llm import LlmExplainRequest  # noqa: E402
import asyncio  # noqa: E402


class LlmDraftSchemaTests(unittest.TestCase):
    def test_valid_draft(self) -> None:
        draft = make_simple_draft("白话", fact_ids=["param:term"])
        self.assertEqual(draft.render_plain_language(), "白话")
        parsed = parse_llm_explanation_content(
            json.dumps(draft.model_dump(mode="json"), ensure_ascii=False)
        )
        self.assertEqual(parsed.render_plain_language(), "白话")

    def test_non_json_fails(self) -> None:
        with self.assertRaises(LlmInvalidJsonError):
            parse_llm_explanation_content("不是JSON")

    def test_extra_field_fails(self) -> None:
        raw = make_simple_draft("x", knowledge_ids=["k1"]).model_dump(mode="json")
        raw["risk_level"] = "低"
        with self.assertRaises(LlmInvalidJsonError):
            parse_llm_explanation_content(json.dumps(raw, ensure_ascii=False))

    def test_findings_field_forbidden(self) -> None:
        raw = make_simple_draft("x", knowledge_ids=["k1"]).model_dump(mode="json")
        raw["findings"] = [{"id": "x"}]
        with self.assertRaises(LlmInvalidJsonError) as ctx:
            parse_llm_explanation_content(json.dumps(raw, ensure_ascii=False))
        self.assertIn("forbidden", str(ctx.exception).lower())

    def test_empty_reference_fails(self) -> None:
        with self.assertRaises(Exception):
            LlmAnalysisDraft.model_validate(
                {
                    "overview_items": [
                        {
                            "item_id": "1",
                            "text": "无引用",
                            "fact_ids": [],
                            "finding_ids": [],
                            "knowledge_ids": [],
                        }
                    ]
                }
            )

    def test_legacy_plain_language_rejected(self) -> None:
        with self.assertRaises(LlmInvalidJsonError):
            parse_llm_explanation_content(
                json.dumps({"plain_language": "旧格式"}, ensure_ascii=False)
            )

    def test_mock_uses_same_parse_path(self) -> None:
        gw = MockLlmGateway()

        async def go():
            return await gw.complete(
                LlmExplainRequest(
                    system_prompt="s",
                    user_prompt="u",
                    allowed_knowledge_ids=["knowledge:demo"],
                )
            )

        draft = asyncio.run(go())
        self.assertIsInstance(draft, LlmAnalysisDraft)
        self.assertTrue(draft.render_plain_language())


if __name__ == "__main__":
    unittest.main()

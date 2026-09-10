"""P2-04：文档事实与本地知识参考分通道；Protocol 含 list_terms。"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT_ROOT / "backend-python"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(PROJECT_ROOT))

from app.domain.models.enums import FactStatus  # noqa: E402
from app.domain.ports.protocols import KnowledgeRepository  # noqa: E402
from app.domain.rules.fact_extractor import FactExtractor  # noqa: E402
from app.infrastructure.knowledge.local_files import (  # noqa: E402
    LocalFileKnowledgeRepository,
)


class KnowledgeReferenceChannelTests(unittest.TestCase):
    def test_protocol_declares_list_terms(self) -> None:
        self.assertTrue(hasattr(KnowledgeRepository, "list_terms"))
        members = dict(inspect.getmembers(KnowledgeRepository))
        self.assertIn("list_terms", members)

    def test_list_terms_returns_typed_items(self) -> None:
        repo = LocalFileKnowledgeRepository(knowledge_dir=PROJECT_ROOT / "knowledge")
        terms = repo.list_terms()
        self.assertGreater(len(terms), 0)
        self.assertTrue(all(hasattr(t, "id") and hasattr(t, "term") for t in terms))
        self.assertTrue(all(t.source_note.startswith("knowledge/") for t in terms))

    def test_document_fact_vs_general_reference(self) -> None:
        repo = LocalFileKnowledgeRepository(knowledge_dir=PROJECT_ROOT / "knowledge")
        extractor = FactExtractor(repo)
        text = (
            "本产品为结构性存款，挂钩欧元兑美元汇率。"
            "若汇率突破观察区间，仅获得活期利率。"
            "说明书未写明本金保障安排。"
        )
        result = extractor.extract(text, product_type_id="structured_deposit")
        # 知识库「通常保本」不得进入 document_fact 参数值
        for param in result.key_parameters:
            if param.status == FactStatus.document_fact and param.value:
                self.assertNotIn("通常保本", str(param.value))
        # 本地知识参考独立通道
        self.assertTrue(result.general_references)
        joined = " ".join(r.text for r in result.general_references)
        self.assertTrue("行业参考" in joined or "监管要点" in joined)
        for ref in result.general_references:
            self.assertEqual(ref.status, FactStatus.general_reference)
            self.assertTrue(ref.source)
            if "products.json" in ref.source:
                self.assertIn("verified=", ref.source)
                self.assertIn("本地产品知识", ref.source)


if __name__ == "__main__":
    unittest.main()

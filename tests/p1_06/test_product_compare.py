"""P1-06：两款产品事实对照验收。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from fastapi.testclient import TestClient  # noqa: E402

from app.application.compare_products import CompareProductsUseCase  # noqa: E402
from app.domain.models.p1_enums import DiffStatus  # noqa: E402
from app.domain.models.product_facts import ProductCompareRequest  # noqa: E402
from app.domain.rules.product_fact_builder import normalize_term_months  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402
from app.main import create_app  # noqa: E402

A_DEPOSIT = (
    "本产品为结构性存款，产品期限12个月。"
    "到期年化收益率3.5%。"
    "不支持提前赎回。"
    "本金保障：存款保险保障。"
)
B_DEPOSIT_SAME_TERM = (
    "结构性存款产品，期限1年。"
    "到期年化收益率3.5%。"
    "提前支取：不支持。"
    "本金保障：存款保险保障。"
)
B_RANGE = (
    "结构性存款，期限1年。"
    "到期年化收益率2.0%-4.0%。"
    "不支持提前赎回。"
)


class ProductCompareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.uc = CompareProductsUseCase(LocalFileKnowledgeRepository())

    def test_term_12m_equals_1y(self) -> None:
        self.assertEqual(normalize_term_months("12个月"), normalize_term_months("1年"))
        out = self.uc.execute(
            ProductCompareRequest(text_a=A_DEPOSIT, text_b=B_DEPOSIT_SAME_TERM)
        )
        term = next(d for d in out.dimensions if d.dimension.value == "term")
        self.assertEqual(term.status, DiffStatus.same)
        self.assertTrue(term.side_a.evidence or term.side_b.evidence)

    def test_rate_range_incomparable(self) -> None:
        out = self.uc.execute(ProductCompareRequest(text_a=A_DEPOSIT, text_b=B_RANGE))
        rate = next(d for d in out.dimensions if d.dimension.value == "return_or_rate")
        self.assertEqual(rate.status, DiffStatus.incomparable)

    def test_missing_side(self) -> None:
        thin_b = "结构性存款产品说明。期限6个月。"
        out = self.uc.execute(ProductCompareRequest(text_a=A_DEPOSIT, text_b=thin_b))
        rate = next(d for d in out.dimensions if d.dimension.value == "return_or_rate")
        self.assertIn(rate.status, (DiffStatus.missing_b, DiffStatus.different))
        if rate.status == DiffStatus.missing_b:
            self.assertTrue(rate.side_a.evidence or rate.side_a.display)

    def test_no_recommendation_copy(self) -> None:
        out = self.uc.execute(
            ProductCompareRequest(text_a=A_DEPOSIT, text_b=B_DEPOSIT_SAME_TERM)
        )
        blob = out.disclaimer + "".join(d.note for d in out.dimensions)
        for bad in ("赢家", "推荐购买", "适合你", "综合评分"):
            self.assertNotIn(bad, blob)

    def test_http(self) -> None:
        client = TestClient(create_app())
        res = client.post(
            "/api/v1/product-comparisons",
            json={"text_a": A_DEPOSIT, "text_b": B_DEPOSIT_SAME_TERM},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(len(body["dimensions"]), 9)
        for bad in ("赢家", "推荐购买", "适合你", "综合评分"):
            self.assertNotIn(bad, body["disclaimer"])


if __name__ == "__main__":
    unittest.main()

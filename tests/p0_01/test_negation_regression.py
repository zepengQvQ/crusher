"""
P0-01 否定句回归黑盒测试。

断言正确行为（不得误报）。当前 knowledge_base 关键词规则会误命中，
因此在 P0-05 修复前这些用例预期失败，用于冻结缺陷。

运行：
  python -m unittest tests.p0_01.test_negation_regression -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "legacy"))

from backend.knowledge_base import detect_products, get_grounding_block, match_risks  # noqa: E402

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "regression"


def _load_negation_fixtures():
    fixtures = []
    for path in sorted(FIXTURE_DIR.glob("negation_*.json")):
        with path.open(encoding="utf-8") as f:
            fixtures.append(json.load(f))
    return fixtures


class NegationRegressionTests(unittest.TestCase):
    """四组否定句：正确结果不得出现对应误报。"""

    def test_fixtures_exist(self):
        fixtures = _load_negation_fixtures()
        self.assertEqual(len(fixtures), 4)

    def test_negation_cases_must_not_false_positive(self):
        failures = []
        for fx in _load_negation_fixtures():
            text = fx["input"]["raw_text"]
            expected = fx["expected"]
            risks = match_risks(text)
            risk_ids = {r["id"] for r in risks}
            risk_names = {r["name"] for r in risks}
            products = detect_products(text)
            product_ids = {p["id"] for p in products}
            grounding = get_grounding_block(text)
            grounding_risk_ids = {r["id"] for r in grounding["risk_patterns"]}

            for rid in expected.get("must_not_match_risk_ids", []):
                if rid in risk_ids or rid in grounding_risk_ids:
                    failures.append(
                        f"[{fx['fixture_id']}] 误命中风险 id={rid}；原文={text!r}"
                    )
            for name in expected.get("must_not_match_risk_names", []):
                if name in risk_names:
                    failures.append(
                        f"[{fx['fixture_id']}] 误命中风险名={name}；原文={text!r}"
                    )
            for pid in expected.get("must_not_classify_product_ids", []):
                if pid in product_ids:
                    failures.append(
                        f"[{fx['fixture_id']}] 误识别产品 id={pid}；原文={text!r}"
                    )

        self.assertEqual(
            failures,
            [],
            "否定句回归未通过（P0-05 前预期失败，用于钉住误报）:\n- "
            + "\n- ".join(failures),
        )


if __name__ == "__main__":
    unittest.main()

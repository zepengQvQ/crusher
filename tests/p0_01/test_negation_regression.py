"""
P0-01 否定句回归黑盒测试（P0-05 后应对齐通过）。

运行：
  python -m unittest tests.p0_01.test_negation_regression -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend-python"))
sys.path.insert(0, str(PROJECT_ROOT))

from app.domain.rules.engine import RuleEngine  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "regression"


def _engine() -> RuleEngine:
    return RuleEngine(
        LocalFileKnowledgeRepository(knowledge_dir=PROJECT_ROOT / "knowledge")
    )


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
        engine = _engine()
        failures = []
        for fx in _load_negation_fixtures():
            text = fx["input"]["raw_text"]
            expected = fx["expected"]
            risks = engine.match_risks(text)
            risk_ids = {r.pattern_id for r in risks}
            risk_names = {r.name for r in risks}
            products = engine.detect_products(text)
            product_ids = {p.product_id for p in products}

            for rid in expected.get("must_not_match_risk_ids", []):
                if rid in risk_ids:
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
            "否定句回归未通过:\n- " + "\n- ".join(failures),
        )


if __name__ == "__main__":
    unittest.main()

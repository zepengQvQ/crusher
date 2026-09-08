"""
P0-05：否定句 / 零发现 / 无关句稳定性 / 坏正则。

先钉住正确行为；实现完成前应失败。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT_ROOT / "backend-python"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(PROJECT_ROOT))

from app.domain.rules.engine import RuleEngine  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "regression"
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"


def _engine() -> RuleEngine:
    repo = LocalFileKnowledgeRepository(knowledge_dir=KNOWLEDGE_DIR)
    return RuleEngine(repo)


class NegationAndStabilityTests(unittest.TestCase):
    def test_four_negation_fixtures(self):
        engine = _engine()
        failures: list[str] = []
        for path in sorted(FIXTURE_DIR.glob("negation_*.json")):
            fx = json.loads(path.read_text(encoding="utf-8"))
            text = fx["input"]["raw_text"]
            expected = fx["expected"]
            risks = engine.match_risks(text)
            risk_ids = {r.pattern_id for r in risks}
            risk_names = {r.name for r in risks}
            products = engine.detect_products(text)
            product_ids = {p.product_id for p in products}

            for rid in expected.get("must_not_match_risk_ids", []):
                if rid in risk_ids:
                    failures.append(f"[{fx['fixture_id']}] 误命中风险 id={rid}")
            for name in expected.get("must_not_match_risk_names", []):
                if name in risk_names:
                    failures.append(f"[{fx['fixture_id']}] 误命中风险名={name}")
            for pid in expected.get("must_not_classify_product_ids", []):
                if pid in product_ids:
                    failures.append(f"[{fx['fixture_id']}] 误识别产品 id={pid}")

        self.assertEqual(failures, [], "否定句未通过:\n- " + "\n- ".join(failures))

    def test_safe_text_allows_zero_findings(self):
        engine = _engine()
        text = "本说明书仅介绍营业网点地址与客服电话，不含任何收费或违约条款。"
        risks = engine.match_risks(text)
        self.assertEqual(risks, [], "安全文本不得为了凑数制造风险")

    def test_irrelevant_sentence_does_not_change_conclusions(self):
        engine = _engine()
        base = "本贷款年化利率12%，逾期按罚息日利率计收。"
        noisy = base + "今日天气晴朗，食堂供应番茄炒蛋。"
        self.assertEqual(
            [r.pattern_id for r in engine.match_risks(base)],
            [r.pattern_id for r in engine.match_risks(noisy)],
        )
        self.assertEqual(
            [p.product_id for p in engine.detect_products(base)],
            [p.product_id for p in engine.detect_products(noisy)],
        )

    def test_bad_regex_fails_at_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "products.json").write_text("[]", encoding="utf-8")
            (root / "terms.json").write_text("[]", encoding="utf-8")
            (root / "risk_patterns.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "bad",
                            "name": "坏正则",
                            "keywords": ["x"],
                            "regex": "(",
                            "applicable_product_types": ["loan"],
                            "risk_level": "低",
                            "explanation": "x",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as ctx:
                LocalFileKnowledgeRepository(knowledge_dir=root)
            self.assertIn("bad", str(ctx.exception))


class PromptNoPaddingTests(unittest.TestCase):
    def test_legacy_stage3_prompt_does_not_require_min_findings(self):
        sys.path.insert(0, str(PROJECT_ROOT / "legacy"))
        from backend.prompts import STAGE3_USER_PROMPT  # noqa: WPS433

        self.assertNotIn("至少找出", STAGE3_USER_PROMPT)
        self.assertIn("可以返回空数组", STAGE3_USER_PROMPT)


if __name__ == "__main__":
    unittest.main()

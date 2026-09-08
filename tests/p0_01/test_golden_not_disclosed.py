"""
P0-01 金标审核：原文未披露字段必须使用 not_disclosed，禁止行业常识填空。

运行：
  python -m unittest tests.p0_01.test_golden_not_disclosed -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

GOLDEN_DIR = PROJECT_ROOT / "tests" / "fixtures" / "golden"
LEGACY_SAMPLE = PROJECT_ROOT / "tests" / "expected_output_sample.json"


class GoldenNotDisclosedTests(unittest.TestCase):
    def test_golden_fixtures_exist(self):
        self.assertTrue((GOLDEN_DIR / "structured_deposit_demo.json").exists())
        self.assertTrue((GOLDEN_DIR / "loan_demo.json").exists())

    def test_structured_deposit_undisclosed_fields(self):
        with (GOLDEN_DIR / "structured_deposit_demo.json").open(encoding="utf-8") as f:
            fx = json.load(f)
        params = fx["expected_report"]["key_parameters"]
        for key in ("early_redemption", "fee_structure", "principal_protection"):
            self.assertEqual(params[key]["status"], "not_disclosed")
            self.assertIsNone(params[key]["value"])

    def test_legacy_expected_output_sample_uses_not_disclosed(self):
        """旧样例不得再用「原文未说明」或「通常保本」充当金标。"""
        with LEGACY_SAMPLE.open(encoding="utf-8") as f:
            sample = json.load(f)
        trans = sample["translation"]
        for field in ("early_redemption", "fee_structure", "principal_protection"):
            value = trans.get(field)
            self.assertEqual(
                value,
                "not_disclosed",
                f"{field} 必须为 not_disclosed，当前={value!r}",
            )
            self.assertNotIn("通常保本", str(value))
            self.assertNotIn("原文未说明", str(value))

    def test_case_structured_deposit_does_not_require_invented_principal(self):
        case_path = PROJECT_ROOT / "tests" / "case_structured_deposit.json"
        with case_path.open(encoding="utf-8") as f:
            case = json.load(f)
        expected = case["expected_translation"]
        # 原文未写保本，不得要求输出包含「保本」
        self.assertNotIn("principal_protection_contains", expected)
        self.assertEqual(expected.get("principal_protection"), "not_disclosed")
        self.assertEqual(expected.get("early_redemption"), "not_disclosed")
        self.assertEqual(expected.get("fee_structure"), "not_disclosed")


if __name__ == "__main__":
    unittest.main()

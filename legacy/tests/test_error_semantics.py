"""
P0-01 错误语义黑盒测试。

冻结：模型超时 / 非法 JSON 时，空 findings 不得被解释为「未发现风险」。
当前 risk_analyzer 在异常时直接返回 []，且页面可能显示安全文案 —— 本测试钉住正确契约。

运行：
  cd legacy && PYTHONPATH=.:../backend-python python -m unittest tests.test_error_semantics -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "legacy"))

from backend.llm_client import LLMClient  # noqa: E402
from backend.risk_analyzer import RiskAnalyzer  # noqa: E402

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "regression"


def _load(name: str) -> dict:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


class _FakeClient:
    """最小桩：只实现 RiskAnalyzer 需要的 chat_json。"""

    def __init__(self, side_effect):
        self._side_effect = side_effect

    def chat_json(self, *args, **kwargs):
        if callable(self._side_effect):
            return self._side_effect()
        raise self._side_effect


class ErrorSemanticsTests(unittest.TestCase):
    def test_error_fixtures_exist(self):
        self.assertTrue((FIXTURE_DIR / "error_model_timeout.json").exists())
        self.assertTrue((FIXTURE_DIR / "error_illegal_json.json").exists())

    def test_timeout_must_not_look_like_no_risk(self):
        fx = _load("error_model_timeout.json")
        expected = fx["expected"]

        def boom():
            raise TimeoutError("simulated model timeout")

        analyzer = RiskAnalyzer(_FakeClient(boom))
        result = analyzer.analyze(fx["input"]["raw_text"])

        # 正确契约：失败应显式抛错或返回带失败状态的结构，而不是静默 []
        self.assertNotEqual(
            result,
            [],
            "模型超时时不得返回空列表冒充「无风险」"
            f"（fixture={fx['fixture_id']} error_code={expected['error_code']}）",
        )

    def test_illegal_json_must_not_look_like_no_risk(self):
        fx = _load("error_illegal_json.json")
        expected = fx["expected"]

        def boom():
            raise json.JSONDecodeError("Expecting value", fx["input"]["simulated_model_output"], 0)

        analyzer = RiskAnalyzer(_FakeClient(boom))
        result = analyzer.analyze(fx["input"]["raw_text"])

        self.assertNotEqual(
            result,
            [],
            "非法 JSON 时不得返回空列表冒充「无风险」"
            f"（fixture={fx['fixture_id']} error_code={expected['error_code']}）",
        )

    def test_parse_json_invalid_raises(self):
        """LLM 原始非法 JSON 必须失败，不能被上层吞成空风险。"""
        fx = _load("error_illegal_json.json")
        with self.assertRaises(ValueError):
            LLMClient._parse_json(fx["input"]["simulated_model_output"])


if __name__ == "__main__":
    unittest.main()

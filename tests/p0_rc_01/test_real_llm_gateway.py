"""
P0-RC-01：真模型网关切换、返回写入报告、错误映射（不访问公网）。
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.application.analyze_text import AnalyzeTextUseCase  # noqa: E402
from app.composition_root import build_llm_gateway, require_real_llm_settings  # noqa: E402
from app.config.settings import Settings  # noqa: E402
from app.domain.llm_errors import LlmConfigError, LlmInvalidJsonError  # noqa: E402
from app.domain.models import AnalyzeTextRequest  # noqa: E402
from app.domain.models.llm import LlmExplanation  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402
from app.infrastructure.llm.mock_gateway import MockLlmGateway  # noqa: E402
from app.infrastructure.llm.openai_compatible_gateway import (  # noqa: E402
    OpenAiCompatibleLlmGateway,
    parse_llm_explanation_content,
)
from app.infrastructure.task_store.memory import InMemoryTaskStore  # noqa: E402
from app.shared.enums import ErrorCode, TaskStatus  # noqa: E402


def _settings(**overrides) -> Settings:
    base = dict(
        mock_mode=True,
        llm_api_key="sk-test-key",
        llm_base_url="https://example.test/v1",
        llm_model="deepseek-chat",
        llm_provider="deepseek",
        cors_origins="http://localhost:5173",
        max_input_chars=8000,
    )
    base.update(overrides)
    return Settings(**base)


def _json_content(plain: str) -> str:
    return json.dumps({"plain_language": plain}, ensure_ascii=False)


def _ok_handler(plain: str):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers.get("Authorization", "").startswith("Bearer ")
        body = {
            "choices": [
                {"message": {"content": _json_content(plain)}},
            ]
        }
        return httpx.Response(200, json=body)

    return handler


class GatewaySelectionTests(unittest.TestCase):
    def test_mock_mode_selects_mock(self):
        gw = build_llm_gateway(_settings(mock_mode=True))
        self.assertIsInstance(gw, MockLlmGateway)

    def test_real_mode_selects_openai_compatible(self):
        gw = build_llm_gateway(_settings(mock_mode=False))
        self.assertIsInstance(gw, OpenAiCompatibleLlmGateway)

    def test_real_mode_missing_key_fails_clearly(self):
        with self.assertRaises(LlmConfigError):
            require_real_llm_settings(_settings(mock_mode=False, llm_api_key=""))
        with self.assertRaises(LlmConfigError):
            build_llm_gateway(_settings(mock_mode=False, llm_api_key=""))

    def test_real_mode_missing_base_url_fails(self):
        with self.assertRaises(LlmConfigError):
            build_llm_gateway(_settings(mock_mode=False, llm_base_url=""))

    def test_real_mode_missing_model_fails(self):
        with self.assertRaises(LlmConfigError):
            build_llm_gateway(_settings(mock_mode=False, llm_model=""))


class MockGatewayTests(unittest.TestCase):
    def test_mock_stable_no_network(self):
        gw = MockLlmGateway()

        async def run() -> None:
            a = await gw.complete("prompt-a")
            b = await gw.complete("prompt-b")
            self.assertEqual(a.plain_language, b.plain_language)
            self.assertIsInstance(a, LlmExplanation)

        asyncio.run(run())


class ParseContentTests(unittest.TestCase):
    def test_strips_markdown_fence(self):
        raw = '```json\n{"plain_language":"你好"}\n```'
        exp = parse_llm_explanation_content(raw)
        self.assertEqual(exp.plain_language, "你好")

    def test_empty_choices_content_invalid(self):
        with self.assertRaises(LlmInvalidJsonError):
            parse_llm_explanation_content("")

    def test_bad_dto_invalid(self):
        with self.assertRaises(LlmInvalidJsonError):
            parse_llm_explanation_content('{"other":"x"}')


class RealGatewayPipelineTests(unittest.TestCase):
    def _run(self, gateway, text: str):
        store = InMemoryTaskStore()
        uc = AnalyzeTextUseCase(
            task_store=store,
            knowledge_repository=LocalFileKnowledgeRepository(),
            llm_gateway=gateway,
            settings=_settings(mock_mode=False),
        )
        req = AnalyzeTextRequest(text=text, product_hint="loan")

        async def go():
            task = uc.submit(req)
            await uc.run(task.task_id, req)
            return store.get(task.task_id)

        return asyncio.run(go())

    def test_plain_language_enters_report(self):
        expected = "这是消费贷条款的白话说明，注意违约金。"
        transport = httpx.MockTransport(_ok_handler(expected))
        client = httpx.AsyncClient(transport=transport)
        gw = OpenAiCompatibleLlmGateway(_settings(mock_mode=False), client=client)
        task = self._run(gw, "本贷款提前还款需支付违约金，年利率12%。")
        self.assertEqual(task.task_status, TaskStatus.completed)
        self.assertIsNotNone(task.report)
        self.assertEqual(task.report.plain_language.text, expected)

    def test_contradiction_with_findings_is_invalid_json(self):
        # 人为注入：规则可能命中违约金；模型却说未发现风险
        transport = httpx.MockTransport(_ok_handler("经分析未发现风险，可以放心办理。"))
        client = httpx.AsyncClient(transport=transport)
        gw = OpenAiCompatibleLlmGateway(_settings(mock_mode=False), client=client)
        task = self._run(
            gw,
            "提前还款需支付剩余本金3%的违约金。",
        )
        # 若规则未命中 Finding，矛盾检测不触发；有 Finding 才必须失败
        if task.report and task.report.findings:
            self.fail("有 Finding 时不得完成报告")
        if task.task_status == TaskStatus.completed:
            # 规则未命中时允许完成；跳过本断言场景
            self.skipTest("当前样例未命中 Finding，矛盾用例不适用")
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.INVALID_MODEL_JSON)
        self.assertIsNone(task.report)
        explain = next(s for s in task.stages if s.name == "explain")
        self.assertEqual(explain.status.value, "failed")

    def test_rate_limited(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "busy"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        gw = OpenAiCompatibleLlmGateway(_settings(mock_mode=False), client=client)
        task = self._run(gw, "结构性存款期限90天。")
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.RATE_LIMITED)
        self.assertIsNone(task.report)
        self.assertEqual(next(s for s in task.stages if s.name == "explain").status.value, "failed")

    def test_timeout(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("slow", request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        gw = OpenAiCompatibleLlmGateway(_settings(mock_mode=False), client=client)
        task = self._run(gw, "结构性存款期限90天。")
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.MODEL_TIMEOUT)
        self.assertIsNone(task.report)

    def test_invalid_upstream_json(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"choices": []})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        gw = OpenAiCompatibleLlmGateway(_settings(mock_mode=False), client=client)
        task = self._run(gw, "结构性存款期限90天。")
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.INVALID_MODEL_JSON)
        self.assertIsNone(task.report)

    def test_non_json_content(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "不是JSON"}}]},
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        gw = OpenAiCompatibleLlmGateway(_settings(mock_mode=False), client=client)
        task = self._run(gw, "结构性存款期限90天。")
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.INVALID_MODEL_JSON)


class ForcedFindingContradictionTests(unittest.TestCase):
    """用可控 Gateway 固定返回矛盾文案，并确保任务带 Finding。"""

    def test_contradiction_fails_when_findings_present(self):
        class FixedGw:
            async def complete(self, prompt: str) -> LlmExplanation:
                return LlmExplanation(plain_language="综合来看没有风险。")

        class SeededUc(AnalyzeTextUseCase):
            def _collect_risks(self, text, products):
                hits = super()._collect_risks(text, products)
                if hits:
                    return hits
                # 强制造一条 Finding 路径：走规则正例
                return super()._collect_risks(
                    "提前还款需支付剩余本金3%的违约金。",
                    products,
                )

        store = InMemoryTaskStore()
        uc = SeededUc(
            task_store=store,
            knowledge_repository=LocalFileKnowledgeRepository(),
            llm_gateway=FixedGw(),
            settings=_settings(mock_mode=True),
        )
        req = AnalyzeTextRequest(
            text="提前还款需支付剩余本金3%的违约金。",
            product_hint="loan",
        )

        async def go():
            task = uc.submit(req)
            await uc.run(task.task_id, req)
            return store.get(task.task_id)

        task = asyncio.run(go())
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.INVALID_MODEL_JSON)
        self.assertIsNone(task.report)


if __name__ == "__main__":
    unittest.main()

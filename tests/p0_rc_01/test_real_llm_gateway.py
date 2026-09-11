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
from app.domain.models.llm import (  # noqa: E402
    LlmAnalysisDraft,
    LlmExplainRequest,
    draft_from_request,
    make_simple_draft,
)
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



def _extract_json_list(user: str, label: str) -> list[str]:
    marker = label
    idx = user.find(marker)
    if idx < 0:
        return []
    start = user.find("[", idx)
    end = user.find("]", start)
    if start < 0 or end < 0:
        return []
    try:
        data = json.loads(user[start : end + 1])
    except json.JSONDecodeError:
        return []
    return [str(x) for x in data] if isinstance(data, list) else []


def _json_content_for_http(request: httpx.Request, plain: str) -> str:
    body_in = json.loads(request.content.decode("utf-8"))
    user = body_in["messages"][1]["content"]
    fact_ids = _extract_json_list(user, "允许引用的 fact_ids：")
    finding_ids = _extract_json_list(user, "允许引用的 finding_ids：")
    knowledge_ids = _extract_json_list(user, "允许引用的 knowledge_ids：")
    draft = make_simple_draft(
        plain,
        fact_ids=fact_ids[:1],
        finding_ids=finding_ids,
        knowledge_ids=knowledge_ids[:1] if not fact_ids and not finding_ids else [],
    )
    return json.dumps(draft.model_dump(mode="json"), ensure_ascii=False)


def _ok_handler(plain: str):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers.get("Authorization", "").startswith("Bearer ")
        body_in = json.loads(request.content.decode("utf-8"))
        roles = [m["role"] for m in body_in["messages"]]
        assert roles == ["system", "user"], roles
        body = {
            "choices": [
                {"message": {"content": _json_content_for_http(request, plain)}},
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
        req = LlmExplainRequest(system_prompt="s", user_prompt="u")

        async def run() -> None:
            a = await gw.complete(req)
            b = await gw.complete(req)
            self.assertEqual(a.render_plain_language(), b.render_plain_language())
            self.assertIsInstance(a, LlmAnalysisDraft)

        asyncio.run(run())


class ParseContentTests(unittest.TestCase):
    def test_strips_markdown_fence(self):
        draft = make_simple_draft("你好", knowledge_ids=["knowledge:demo"])
        raw = "```json\n" + json.dumps(draft.model_dump(mode="json"), ensure_ascii=False) + "\n```"
        exp = parse_llm_explanation_content(raw)
        self.assertEqual(exp.render_plain_language(), "你好")

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
        # 完整发布白话由程序模板生成；此处确认模型网关被调用且 explain 成功
        explain = next(s for s in task.stages if s.name == "explain")
        self.assertEqual(explain.status.value, "success")
        self.assertIn("违约金", task.report.plain_language.text)
        self.assertIn("12%", task.report.plain_language.text)

    def test_contradiction_with_findings_is_invalid_json(self):
        # 人为注入：规则可能命中违约金；模型却说未发现风险
        transport = httpx.MockTransport(_ok_handler("经分析未发现风险，可以放心办理。"))
        client = httpx.AsyncClient(transport=transport)
        gw = OpenAiCompatibleLlmGateway(_settings(mock_mode=False), client=client)
        task = self._run(
            gw,
            "提前还款需支付剩余本金3%的违约金。",
        )
        # 若规则未命中 Finding，矛盾检测不触发；有 Finding 则部分发布程序事实
        if task.task_status == TaskStatus.completed and not (
            task.report and task.report.findings
        ):
            self.skipTest("当前样例未命中 Finding，矛盾用例不适用")
        self.assertEqual(task.task_status, TaskStatus.completed)
        self.assertIsNotNone(task.report)
        self.assertTrue(task.report.findings)
        self.assertEqual(task.publication.outcome.value, "publish_partial")
        self.assertEqual(task.publication.reason_code, ErrorCode.MODEL_OUTPUT_INVALID)
        explain = next(s for s in task.stages if s.name == "explain")
        self.assertEqual(explain.status.value, "partial")

    def test_rate_limited(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "busy"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        gw = OpenAiCompatibleLlmGateway(_settings(mock_mode=False), client=client)
        # 与 _run 的 product_hint=loan 一致，避免产品冲突走范围门而跳过 LLM
        task = self._run(gw, "本贷款借款期限90天，年化利率7.2%。")
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.RATE_LIMITED)
        self.assertIsNone(task.report)
        self.assertEqual(next(s for s in task.stages if s.name == "explain").status.value, "failed")

    def test_timeout(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("slow", request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        gw = OpenAiCompatibleLlmGateway(_settings(mock_mode=False), client=client)
        task = self._run(gw, "本贷款借款期限90天，年化利率7.2%。")
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.MODEL_TIMEOUT)
        self.assertIsNone(task.report)

    def test_invalid_upstream_json(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"choices": []})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        gw = OpenAiCompatibleLlmGateway(_settings(mock_mode=False), client=client)
        task = self._run(gw, "本贷款借款期限90天，年化利率7.2%。")
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
        task = self._run(gw, "本贷款借款期限90天，年化利率7.2%。")
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.INVALID_MODEL_JSON)


class ForcedFindingContradictionTests(unittest.TestCase):
    """用可控 Gateway 固定返回矛盾文案，并确保任务带 Finding。"""

    def test_contradiction_fails_when_findings_present(self):
        class FixedGw:
            async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
                return draft_from_request(request, "综合来看没有风险。")

        class SeededUc(AnalyzeTextUseCase):
            def _collect_risks(self, text, product_type_id):
                hits = super()._collect_risks(text, product_type_id)
                if hits:
                    return hits
                return super()._collect_risks(
                    "提前还款需支付剩余本金3%的违约金。",
                    product_type_id,
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
        self.assertEqual(task.task_status, TaskStatus.completed)
        self.assertIsNotNone(task.report)
        self.assertTrue(task.report.findings)
        self.assertEqual(task.publication.outcome.value, "publish_partial")
        self.assertEqual(task.publication.reason_code, ErrorCode.MODEL_OUTPUT_INVALID)


if __name__ == "__main__":
    unittest.main()

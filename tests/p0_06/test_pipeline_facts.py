"""
P0-06：流水线阶段、事实分层、证据校验、常识不填坑、结构化幂等。
"""
from __future__ import annotations

import ast
import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from fastapi.testclient import TestClient  # noqa: E402

from app.composition_root import get_analyze_text_use_case, get_task_store  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.domain.models import Evidence, Finding, FindingSeverity  # noqa: E402
from app.domain.models.enums import EvidenceSource, FactStatus, ParameterKey  # noqa: E402
from app.domain.rules.evidence import validate_and_fix_findings  # noqa: E402
from app.domain.rules.fact_extractor import FactExtractor  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402
from app.main import create_app  # noqa: E402

GOLDEN = ROOT / "tests" / "fixtures" / "golden" / "structured_deposit_demo.json"
EXPECTED_STAGES = [
    "preprocess",
    "classify",
    "extract",
    "rule_review",
    "evidence_validate",
    "explain",
]


def _client() -> TestClient:
    get_settings.cache_clear()
    get_task_store.cache_clear()
    get_analyze_text_use_case.cache_clear()
    return TestClient(create_app())


def _poll_report(client: TestClient, text: str) -> dict:
    res = client.post("/api/v1/analyses", json={"text": text})
    assert res.status_code == 200, res.text
    task_id = res.json()["task_id"]
    for _ in range(50):
        body = client.get(f"/api/v1/analyses/{task_id}").json()
        if body["task_status"] == "completed":
            return body
        if body["task_status"] == "failed":
            raise AssertionError(f"unexpected failed: {body}")
        time.sleep(0.15)
    raise AssertionError("timeout waiting for completed")


class PipelineStageTests(unittest.TestCase):
    def test_stages_include_evidence_validate_in_order(self):
        body = _poll_report(_client(), "本产品为结构性存款，期限90天。")
        names = [s["name"] for s in body["stages"]]
        self.assertEqual(names, EXPECTED_STAGES)
        self.assertTrue(
            all(s["status"] in ("success", "partial") for s in body["stages"])
        )
        self.assertFalse(any(s["status"] == "failed" for s in body["stages"]))


class FactLayeringTests(unittest.TestCase):
    def test_undisclosed_principal_not_filled_by_general_knowledge(self):
        fx = json.loads(GOLDEN.read_text(encoding="utf-8"))
        text = fx["input"]["raw_text"]
        body = _poll_report(_client(), text)
        report = body["report"]
        params = {p["key"]: p for p in report["key_parameters"]}

        expected = fx["expected_report"]["key_parameters"]
        for key, exp in expected.items():
            self.assertIn(key, params, f"缺少参数 {key}")
            self.assertEqual(params[key]["status"], exp["status"], key)
            if exp["status"] == "not_disclosed":
                self.assertIn(params[key]["value"], (None, ""))
            if "value_contains" in exp:
                value = params[key].get("value") or ""
                for needle in exp["value_contains"]:
                    self.assertIn(needle, value, key)

        # 常识可以出现在 general_references，但禁止进入 document_fact 字段值
        joined_doc = " ".join(
            (p.get("value") or "")
            for p in report["key_parameters"]
            if p["status"] == "document_fact"
        )
        for banned in fx["expected_report"]["forbidden_in_document_fields"]:
            self.assertNotIn(banned, joined_doc)

        refs = " ".join(r["text"] for r in report.get("general_references") or [])
        self.assertTrue(report.get("general_references"), "应保留行业常识为 general_reference")
        self.assertTrue(any(r.get("status") == "general_reference" for r in report["general_references"]))
        # 本金保障参数本身必须是未披露
        self.assertEqual(params["principal_protection"]["status"], "not_disclosed")

    def test_extractor_never_copies_principal_hint_into_document_fact(self):
        repo = LocalFileKnowledgeRepository(knowledge_dir=ROOT / "knowledge")
        extractor = FactExtractor(repo)
        text = "本产品为结构性存款，期限90天。"
        result = extractor.extract(text, product_type_id="structured_deposit")
        principal = next(p for p in result.key_parameters if p.key == ParameterKey.principal_protection)
        self.assertEqual(principal.status, FactStatus.not_disclosed)
        self.assertIsNone(principal.value)
        self.assertTrue(result.general_references)
        self.assertTrue(
            any("保本" in r.text or "本金" in r.text for r in result.general_references)
        )


class EvidenceTests(unittest.TestCase):
    def test_finding_evidence_must_match_source_text(self):
        text = "本贷款提前还款需支付违约金3%。"
        body = _poll_report(_client(), text)
        findings = body["report"]["findings"]
        self.assertGreaterEqual(len(findings), 1)
        for f in findings:
            self.assertTrue(f["evidence"], f)
            for ev in f["evidence"]:
                self.assertEqual(text[ev["start"] : ev["end"]], ev["quote"])
                self.assertIn(ev["quote"], text)
            self.assertIn("rule_or_knowledge_id", f)
            self.assertIn("confidence", f)
            self.assertIn("needs_review", f)

    def test_invalid_evidence_is_dropped_not_kept_silently(self):
        text = "abcdef"
        bad = Finding(
            id="x",
            title="坏证据",
            finding_severity=FindingSeverity.mid,
            explanation="无",
            evidence=[
                Evidence(
                    quote="不存在的片段",
                    start=0,
                    end=2,
                    source=EvidenceSource.input_text,
                )
            ],
            rule_or_knowledge_id="x",
            confidence=0.9,
        )
        kept, dropped = validate_and_fix_findings(text, [bad])
        self.assertEqual(kept, [])
        self.assertTrue(dropped)


class IdempotencyTests(unittest.TestCase):
    def test_structured_facts_stable_across_runs(self):
        client = _client()
        text = "本产品为结构性存款，期限90天，年化收益率4.80%。提前还款需支付违约金。"
        a = _poll_report(client, text)["report"]
        b = _poll_report(client, text)["report"]
        self.assertEqual(
            [(p["key"], p["status"], p.get("value")) for p in a["key_parameters"]],
            [(p["key"], p["status"], p.get("value")) for p in b["key_parameters"]],
        )
        self.assertEqual(
            sorted(f["id"] for f in a["findings"]),
            sorted(f["id"] for f in b["findings"]),
        )


class NoMcpInApplicationTests(unittest.TestCase):
    def test_application_and_rules_do_not_import_mcp(self):
        app_root = ROOT / "backend-python" / "app"
        offenders = []
        for path in app_root.rglob("*.py"):
            # P2-10：仅允许 interfaces/mcp 可选适配层依赖 mcp 包
            if "interfaces/mcp" in path.as_posix():
                continue
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "mcp" or alias.name.startswith("mcp."):
                            offenders.append(str(path.relative_to(ROOT)))
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module == "mcp" or node.module.startswith("mcp."):
                        offenders.append(str(path.relative_to(ROOT)))
            if "asyncio.run(" in src and "application" in str(path):
                offenders.append(f"{path.relative_to(ROOT)}:asyncio.run")
            if "```mermaid" in src or "flowchart TD" in src:
                offenders.append(f"{path.relative_to(ROOT)}:mermaid")
        self.assertEqual(offenders, [], f"主链路禁止 MCP/嵌套 asyncio.run/模型 Mermaid: {offenders}")


if __name__ == "__main__":
    unittest.main()

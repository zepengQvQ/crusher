"""
P0-08：首批产品金标（正常 / 风险 / 缺失披露 / 否定句）。
强制断言 not_disclosed，禁止跳过比较。
"""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "fixtures" / "golden"
sys.path.insert(0, str(ROOT / "backend-python"))

from fastapi.testclient import TestClient  # noqa: E402

from app.composition_root import get_analyze_text_use_case, get_task_store  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


def _client() -> TestClient:
    get_settings.cache_clear()
    get_task_store.cache_clear()
    get_analyze_text_use_case.cache_clear()
    return TestClient(create_app())


def _analyze(client: TestClient, text: str, product_hint: str = "auto") -> dict:
    res = client.post(
        "/api/v1/analyses",
        json={"text": text, "product_hint": product_hint},
    )
    assert res.status_code == 200, res.text
    task_id = res.json()["task_id"]
    for _ in range(50):
        body = client.get(f"/api/v1/analyses/{task_id}").json()
        if body["task_status"] == "completed":
            return body
        if body["task_status"] == "failed":
            raise AssertionError(body)
        time.sleep(0.12)
    raise AssertionError("timeout")


def _assert_golden(body: dict, expected: dict) -> None:
    report = body["report"]
    assert report is not None
    top = report["product_candidates"][0]["product_type_id"]
    if "product_type_id" in expected:
        assert top == expected["product_type_id"], f"product got {top}"

    params = {p["key"]: p for p in report["key_parameters"]}
    for key, exp in (expected.get("key_parameters") or {}).items():
        assert key in params, f"missing param {key}"
        assert params[key]["status"] == exp["status"], (
            f"{key} status want {exp['status']} got {params[key]['status']}"
        )
        if exp["status"] == "not_disclosed":
            # 严格：不得跳过，不得带值
            assert params[key].get("value") in (None, "")
            assert params[key].get("amount") in (None, "")
        for needle in exp.get("value_contains") or []:
            assert needle in (params[key].get("value") or ""), key

    finding_ids = {f["id"] for f in report.get("findings") or []}
    for rid in expected.get("must_match_risk_ids") or []:
        assert rid in finding_ids, f"missing risk {rid}, got {finding_ids}"
    for rid in expected.get("must_not_match_risk_ids") or []:
        assert rid not in finding_ids, f"false positive risk {rid}"

    for banned in expected.get("forbidden_in_document_fields") or []:
        joined = " ".join(
            (p.get("value") or "")
            for p in report["key_parameters"]
            if p["status"] == "document_fact"
        )
        assert banned not in joined, banned

    for label in expected.get("forbidden_labels") or []:
        labels = [p.get("label") or "" for p in report["key_parameters"]]
        assert label not in labels, f"forbidden label {label} in {labels}"

    for key in expected.get("forbidden_keys") or []:
        assert key not in params, f"forbidden key {key}"


class GoldenProductTests(unittest.TestCase):
    def test_structured_deposit_normal_and_missing(self):
        fx = json.loads((GOLDEN / "structured_deposit_demo.json").read_text(encoding="utf-8"))
        body = _analyze(_client(), fx["input"]["raw_text"], "structured_deposit")
        _assert_golden(body, fx["expected_report"])

    def test_structured_deposit_risk(self):
        fx = json.loads((GOLDEN / "structured_deposit_risk.json").read_text(encoding="utf-8"))
        body = _analyze(_client(), fx["input"]["raw_text"], "structured_deposit")
        _assert_golden(body, fx["expected_report"])

    def test_loan_risk(self):
        fx = json.loads((GOLDEN / "loan_demo.json").read_text(encoding="utf-8"))
        body = _analyze(_client(), fx["input"]["raw_text"], "loan")
        _assert_golden(body, fx["expected_report"])

    def test_loan_negation(self):
        fx = json.loads((GOLDEN / "loan_negation.json").read_text(encoding="utf-8"))
        body = _analyze(_client(), fx["input"]["raw_text"], "loan")
        _assert_golden(body, fx["expected_report"])

    def test_loan_missing_disclosure(self):
        fx = json.loads((GOLDEN / "loan_missing_disclosure.json").read_text(encoding="utf-8"))
        body = _analyze(_client(), fx["input"]["raw_text"], "loan")
        _assert_golden(body, fx["expected_report"])


if __name__ == "__main__":
    unittest.main()

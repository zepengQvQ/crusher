"""P2-04：知识 Schema / 缺字段 / 坏正则 / 重复 ID。"""
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

from app.infrastructure.knowledge.schemas import (  # noqa: E402
    KnowledgeValidationError,
    validate_knowledge_dir,
)

VERIFIED = "2026-09-10"


def _write_manifest(root: Path) -> None:
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "content_version": "test",
                "last_verified_at": VERIFIED,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _loan_product() -> dict:
    return {
        "id": "loan",
        "name": "借贷",
        "aliases": ["贷款"],
        "strong_aliases": ["贷款"],
        "weak_aliases": [],
        "category": "信贷",
        "definition": "借贷产品。",
        "typical_terms": [],
        "source_name": "测试",
        "source_note": "knowledge/products.json",
        "verified_at": VERIFIED,
    }


def _pattern(**overrides: object) -> dict:
    base = {
        "id": "p1",
        "name": "模式",
        "keywords": ["罚息"],
        "regex": "罚息",
        "match_mode": "regex_or_keywords",
        "applicable_product_types": ["loan"],
        "risk_level": "中",
        "explanation": "说明",
        "source_name": "测试",
        "source_note": "knowledge/risk_patterns.json",
        "verified_at": VERIFIED,
    }
    base.update(overrides)
    return base


def _term(**overrides: object) -> dict:
    base = {
        "id": "term_x",
        "term": "罚息",
        "aliases": [],
        "category": "信贷",
        "definition": "逾期加收的利息。",
        "plain_explanation": "欠钱多付的利息。",
        "risk_hint": "",
        "source_name": "测试",
        "source_note": "knowledge/terms.json",
        "verified_at": VERIFIED,
    }
    base.update(overrides)
    return base


class KnowledgeSchemaTests(unittest.TestCase):
    def test_repo_knowledge_validates(self) -> None:
        bundle = validate_knowledge_dir(PROJECT_ROOT / "knowledge")
        self.assertEqual(bundle.manifest.schema_version, "1.0")
        self.assertGreaterEqual(len(bundle.products), 1)
        self.assertGreaterEqual(len(bundle.terms), 1)
        self.assertTrue(all(t.id for t in bundle.terms))

    def test_missing_required_field_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root)
            (root / "products.json").write_text(
                json.dumps([{"id": "loan", "name": "借贷"}], ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "risk_patterns.json").write_text("[]", encoding="utf-8")
            (root / "terms.json").write_text("[]", encoding="utf-8")
            with self.assertRaises(KnowledgeValidationError) as ctx:
                validate_knowledge_dir(root)
            self.assertIn("products.json", str(ctx.exception))

    def test_duplicate_product_id_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root)
            (root / "products.json").write_text(
                json.dumps([_loan_product(), _loan_product()], ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "risk_patterns.json").write_text("[]", encoding="utf-8")
            (root / "terms.json").write_text("[]", encoding="utf-8")
            with self.assertRaises(KnowledgeValidationError) as ctx:
                validate_knowledge_dir(root)
            self.assertIn("重复 ID", str(ctx.exception))

    def test_bad_regex_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root)
            (root / "products.json").write_text(
                json.dumps([_loan_product()], ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "risk_patterns.json").write_text(
                json.dumps([_pattern(id="bad", regex="(")], ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "terms.json").write_text("[]", encoding="utf-8")
            with self.assertRaises(KnowledgeValidationError) as ctx:
                validate_knowledge_dir(root)
            self.assertIn("bad", str(ctx.exception))

    def test_unknown_product_ref_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root)
            (root / "products.json").write_text(
                json.dumps([_loan_product()], ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "risk_patterns.json").write_text(
                json.dumps(
                    [_pattern(applicable_product_types=["not_a_product"])],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "terms.json").write_text(
                json.dumps([_term()], ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaises(KnowledgeValidationError) as ctx:
                validate_knowledge_dir(root)
            self.assertIn("未知产品", str(ctx.exception))

    def test_duplicate_term_id_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root)
            (root / "products.json").write_text(
                json.dumps([_loan_product()], ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "risk_patterns.json").write_text("[]", encoding="utf-8")
            (root / "terms.json").write_text(
                json.dumps([_term(), _term()], ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaises(KnowledgeValidationError) as ctx:
                validate_knowledge_dir(root)
            self.assertIn("重复 ID", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

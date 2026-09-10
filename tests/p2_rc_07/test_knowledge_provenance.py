"""P2-RC-07：知识来源不得自证；缺来源标 UNVERIFIED；日期与 Manifest 一致。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT_ROOT / "backend-python"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(PROJECT_ROOT))

from app.domain.models.knowledge import KnowledgeVerificationStatus  # noqa: E402
from app.infrastructure.knowledge.schemas import (  # noqa: E402
    KnowledgeValidationError,
    validate_knowledge_dir,
)

TODAY = date.today().isoformat()


def _write_manifest(root: Path, *, last_verified_at: str | None = None) -> None:
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "content_version": "test.1",
                "last_verified_at": last_verified_at or TODAY,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _loan_product(**overrides: object) -> dict:
    base = {
        "id": "loan",
        "name": "借贷",
        "aliases": ["贷款"],
        "strong_aliases": ["贷款"],
        "weak_aliases": [],
        "category": "信贷",
        "definition": "借贷产品。",
        "typical_terms": [],
        "risk_level_hint": "视资质而定",
        "regulatory_notes": "金融机构贷款需明示年化利率。",
        "source_name": "未核验本地草稿",
        "source_url": None,
        "source_note": "本地 Demo 草稿，未经外部权威来源核验",
        "verified_at": TODAY,
        "verification_status": "UNVERIFIED",
    }
    base.update(overrides)
    return base


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
        "source_name": "未核验本地草稿",
        "source_url": None,
        "source_note": "本地 Demo 草稿，未经外部权威来源核验",
        "verified_at": TODAY,
        "verification_status": "UNVERIFIED",
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
        "source_name": "未核验本地草稿",
        "source_url": None,
        "source_note": "本地 Demo 草稿，未经外部权威来源核验",
        "verified_at": TODAY,
        "verification_status": "UNVERIFIED",
    }
    base.update(overrides)
    return base


class KnowledgeProvenanceTests(unittest.TestCase):
    def test_repo_knowledge_has_no_self_proving_verified_sources(self) -> None:
        bundle = validate_knowledge_dir(PROJECT_ROOT / "knowledge")
        for product in bundle.products:
            self.assertIn(
                product.verification_status,
                (
                    KnowledgeVerificationStatus.verified,
                    KnowledgeVerificationStatus.unverified,
                ),
            )
            if product.verification_status == KnowledgeVerificationStatus.verified:
                note = (product.source_note or "").strip()
                self.assertFalse(
                    note.startswith("knowledge/") and note.endswith(".json"),
                    msg=f"产品 {product.id} 不得用 JSON 自身证明 VERIFIED",
                )
                self.assertTrue(
                    (product.source_url or "").startswith(("http://", "https://"))
                    or (
                        note
                        and "knowledge/" not in note
                        and "未经" not in note
                    ),
                    msg=f"产品 {product.id} VERIFIED 需要可核查外部来源",
                )
            else:
                self.assertEqual(
                    product.verification_status,
                    KnowledgeVerificationStatus.unverified,
                )
        # 监管/金额/风险/定义类条目若无外部来源，必须是 UNVERIFIED
        for product in bundle.products:
            sensitive = bool(
                (product.regulatory_notes or "").strip()
                or (product.risk_level_hint or "").strip()
                or (product.definition or "").strip()
            )
            if sensitive and not (product.source_url or "").startswith(
                ("http://", "https://")
            ):
                self.assertEqual(
                    product.verification_status,
                    KnowledgeVerificationStatus.unverified,
                    msg=f"产品 {product.id} 敏感知识缺外部来源必须 UNVERIFIED",
                )

    def test_self_referential_verified_product_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root)
            (root / "products.json").write_text(
                json.dumps(
                    [
                        _loan_product(
                            verification_status="VERIFIED",
                            source_note="knowledge/products.json",
                            source_url=None,
                        )
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "risk_patterns.json").write_text("[]", encoding="utf-8")
            (root / "terms.json").write_text("[]", encoding="utf-8")
            with self.assertRaises(KnowledgeValidationError) as ctx:
                validate_knowledge_dir(root)
            self.assertIn("自证", str(ctx.exception))

    def test_future_verified_at_rejected(self) -> None:
        future = (date.today() + timedelta(days=3)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root)
            (root / "products.json").write_text(
                json.dumps(
                    [_loan_product(verified_at=future)],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "risk_patterns.json").write_text("[]", encoding="utf-8")
            (root / "terms.json").write_text("[]", encoding="utf-8")
            with self.assertRaises(KnowledgeValidationError) as ctx:
                validate_knowledge_dir(root)
            self.assertIn("未来", str(ctx.exception))

    def test_entry_verified_after_manifest_rejected(self) -> None:
        earlier = (date.today() - timedelta(days=10)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, last_verified_at=earlier)
            (root / "products.json").write_text(
                json.dumps([_loan_product(verified_at=TODAY)], ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "risk_patterns.json").write_text(
                json.dumps([_pattern(verified_at=TODAY)], ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "terms.json").write_text(
                json.dumps([_term(verified_at=TODAY)], ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaises(KnowledgeValidationError) as ctx:
                validate_knowledge_dir(root)
            self.assertIn("Manifest", str(ctx.exception))

    def test_sensitive_unverified_without_external_url_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root)
            (root / "products.json").write_text(
                json.dumps([_loan_product()], ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "risk_patterns.json").write_text(
                json.dumps([_pattern()], ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "terms.json").write_text(
                json.dumps([_term()], ensure_ascii=False),
                encoding="utf-8",
            )
            bundle = validate_knowledge_dir(root)
            self.assertEqual(
                bundle.products[0].verification_status,
                KnowledgeVerificationStatus.unverified,
            )


if __name__ == "__main__":
    unittest.main()

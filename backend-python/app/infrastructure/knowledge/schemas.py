"""知识库 JSON Schema 校验与加载（P2-04 / P2-RC-07）。

启动或 CLI 均可调用；缺字段、重复 ID、坏正则、未知产品引用一律失败。
来源不得自证；敏感知识缺外部来源须 UNVERIFIED；日期不得晚于今天且须与 Manifest 一致。
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from app.domain.models.knowledge import (
    KnowledgeBundle,
    KnowledgeManifest,
    KnowledgeVerificationStatus,
    ProductKnowledge,
    RiskPatternKnowledge,
    TermKnowledge,
)

_SELF_PROOF_NOTE = re.compile(
    r"^(knowledge/[\w./-]+\.json)(#.*)?$",
    re.IGNORECASE,
)


class KnowledgeValidationError(ValueError):
    """知识库契约校验失败。"""


def _load_json(path: Path) -> object:
    if not path.is_file():
        raise KnowledgeValidationError(f"知识库文件不存在: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _parse_list(path: Path, model_cls: type, label: str) -> list:
    raw = _load_json(path)
    if not isinstance(raw, list):
        raise KnowledgeValidationError(f"{label} 必须是 JSON 数组: {path}")
    items = []
    for index, row in enumerate(raw):
        try:
            items.append(model_cls.model_validate(row))
        except ValidationError as exc:
            raise KnowledgeValidationError(
                f"{label} 第 {index} 条校验失败 ({path.name}): {exc}"
            ) from exc
    return items


def _unique_ids(items: list, label: str, attr: str = "id") -> None:
    seen: set[str] = set()
    for item in items:
        item_id = getattr(item, attr)
        if item_id in seen:
            raise KnowledgeValidationError(f"{label} 存在重复 ID: {item_id}")
        seen.add(item_id)


def _compile_regexes(patterns: list[RiskPatternKnowledge]) -> dict[str, re.Pattern[str]]:
    compiled: dict[str, re.Pattern[str]] = {}
    for pattern in patterns:
        if pattern.regex:
            try:
                compiled[pattern.regex] = re.compile(pattern.regex)
            except re.error as exc:
                raise KnowledgeValidationError(
                    f"风险模式 {pattern.id} 的 regex 非法，拒绝启动: "
                    f"{pattern.regex!r} ({exc})"
                ) from exc
        if pattern.numeric_rule is not None:
            extract = pattern.numeric_rule.extract_regex
            try:
                compiled[extract] = re.compile(extract)
            except re.error as exc:
                raise KnowledgeValidationError(
                    f"风险模式 {pattern.id} 的 numeric_rule.extract_regex 非法: "
                    f"{extract!r} ({exc})"
                ) from exc
    return compiled


def _check_product_refs(
    products: list[ProductKnowledge],
    patterns: list[RiskPatternKnowledge],
) -> None:
    product_ids = {p.id for p in products}
    for pattern in patterns:
        for pid in pattern.applicable_product_types:
            if pid not in product_ids:
                raise KnowledgeValidationError(
                    f"风险模式 {pattern.id} 引用了未知产品: {pid}"
                )


def _has_external_source(*, source_url: str | None, source_note: str) -> bool:
    url = (source_url or "").strip()
    if url.startswith(("http://", "https://")):
        return True
    note = (source_note or "").strip()
    if not note:
        return False
    if _SELF_PROOF_NOTE.match(note):
        return False
    if note.startswith("knowledge/") and note.endswith(".json"):
        return False
    return True


def _is_self_proving(*, source_url: str | None, source_note: str) -> bool:
    """来源仅回指 knowledge/*.json 自身时视为自证。"""
    url = (source_url or "").strip()
    if url.startswith(("http://", "https://")):
        return False
    note = (source_note or "").strip()
    if _SELF_PROOF_NOTE.match(note):
        return True
    if note.startswith("knowledge/") and ".json" in note:
        return True
    return False


def _check_entry_provenance(
    *,
    label: str,
    entry_id: str,
    verification_status: KnowledgeVerificationStatus,
    source_url: str | None,
    source_note: str,
    verified_at: date,
    manifest: KnowledgeManifest,
    sensitive: bool,
) -> None:
    today = date.today()
    if verified_at > today:
        raise KnowledgeValidationError(
            f"{label} {entry_id} 的 verified_at 不能是未来日期: {verified_at.isoformat()}"
        )
    if verified_at > manifest.last_verified_at:
        raise KnowledgeValidationError(
            f"{label} {entry_id} 的 verified_at 晚于 Manifest.last_verified_at"
        )
    if verification_status == KnowledgeVerificationStatus.verified:
        if _is_self_proving(source_url=source_url, source_note=source_note):
            raise KnowledgeValidationError(
                f"{label} {entry_id} 不得用知识 JSON 自身自证为 VERIFIED"
            )
        if not _has_external_source(source_url=source_url, source_note=source_note):
            raise KnowledgeValidationError(
                f"{label} {entry_id} 标记 VERIFIED 但缺少可核查外部来源"
            )
    elif sensitive and not _has_external_source(
        source_url=source_url, source_note=source_note
    ):
        if verification_status != KnowledgeVerificationStatus.unverified:
            raise KnowledgeValidationError(
                f"{label} {entry_id} 监管/风险/定义类知识缺外部来源必须为 UNVERIFIED"
            )


def _check_provenance_bundle(
    manifest: KnowledgeManifest,
    products: list[ProductKnowledge],
    patterns: list[RiskPatternKnowledge],
    terms: list[TermKnowledge],
) -> None:
    if manifest.last_verified_at > date.today():
        raise KnowledgeValidationError(
            f"Manifest.last_verified_at 不能是未来日期: "
            f"{manifest.last_verified_at.isoformat()}"
        )
    for product in products:
        sensitive = bool(
            (product.definition or "").strip()
            or (product.regulatory_notes or "").strip()
            or (product.risk_level_hint or "").strip()
        )
        _check_entry_provenance(
            label="产品",
            entry_id=product.id,
            verification_status=product.verification_status,
            source_url=product.source_url,
            source_note=product.source_note,
            verified_at=product.verified_at,
            manifest=manifest,
            sensitive=sensitive,
        )
    for pattern in patterns:
        _check_entry_provenance(
            label="风险模式",
            entry_id=pattern.id,
            verification_status=pattern.verification_status,
            source_url=pattern.source_url,
            source_note=pattern.source_note,
            verified_at=pattern.verified_at,
            manifest=manifest,
            sensitive=True,
        )
    for term in terms:
        _check_entry_provenance(
            label="术语",
            entry_id=term.id,
            verification_status=term.verification_status,
            source_url=term.source_url,
            source_note=term.source_note,
            verified_at=term.verified_at,
            manifest=manifest,
            sensitive=bool((term.definition or "").strip()),
        )


def load_knowledge_bundle(
    knowledge_dir: Path,
) -> tuple[KnowledgeBundle, dict[str, re.Pattern[str]]]:
    """加载并强校验本地知识目录。"""
    root = Path(knowledge_dir)
    if not root.is_dir():
        raise KnowledgeValidationError(f"知识库目录不存在: {root}")

    try:
        manifest = KnowledgeManifest.model_validate(_load_json(root / "manifest.json"))
    except ValidationError as exc:
        raise KnowledgeValidationError(f"manifest.json 校验失败: {exc}") from exc

    products = _parse_list(root / "products.json", ProductKnowledge, "products.json")
    risk_patterns = _parse_list(
        root / "risk_patterns.json", RiskPatternKnowledge, "risk_patterns.json"
    )
    terms = _parse_list(root / "terms.json", TermKnowledge, "terms.json")

    _unique_ids(products, "products.json")
    _unique_ids(risk_patterns, "risk_patterns.json")
    _unique_ids(terms, "terms.json")
    _check_product_refs(products, risk_patterns)
    _check_provenance_bundle(manifest, products, risk_patterns, terms)
    compiled = _compile_regexes(risk_patterns)

    bundle = KnowledgeBundle(
        manifest=manifest,
        products=products,
        risk_patterns=risk_patterns,
        terms=terms,
    )
    return bundle, compiled


def validate_knowledge_dir(knowledge_dir: Path) -> KnowledgeBundle:
    """供 CLI / 测试调用：成功返回 bundle，失败抛 KnowledgeValidationError。"""
    bundle, _ = load_knowledge_bundle(knowledge_dir)
    return bundle

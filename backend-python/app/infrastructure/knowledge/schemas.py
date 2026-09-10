"""知识库 JSON Schema 校验与加载（P2-04）。

启动或 CLI 均可调用；缺字段、重复 ID、坏正则、未知产品引用一律失败。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.domain.models.knowledge import (
    KnowledgeBundle,
    KnowledgeManifest,
    ProductKnowledge,
    RiskPatternKnowledge,
    TermKnowledge,
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

"""
金融知识库加载与查询（legacy 适配层）。

P0-09：不再修改 sys.path。请使用已安装的 crusher-backend
（`pip install -e backend-python/.`）或设置 PYTHONPATH=backend-python。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.domain.rules.engine import RuleEngine
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository

_REPO = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def _engine() -> RuleEngine:
    return RuleEngine(LocalFileKnowledgeRepository(knowledge_dir=_REPO / "knowledge"))


def get_terms() -> list[dict]:
    return [t.model_dump(mode="json") for t in _engine()._knowledge.list_terms()]  # noqa: SLF001


def get_products() -> list[dict]:
    return [p.model_dump(mode="json") for p in _engine()._knowledge.list_products()]  # noqa: SLF001


def get_risk_patterns() -> list[dict]:
    return [r.model_dump(mode="json") for r in _engine()._knowledge.list_risk_patterns()]  # noqa: SLF001


def search_terms(query: str, limit: int = 10) -> list[dict]:
    q = (query or "").strip().lower()
    if not q:
        return []
    results = []
    for t in get_terms():
        haystack = " ".join(
            [
                t.get("term", ""),
                " ".join(t.get("aliases", [])),
                t.get("category", ""),
            ]
        ).lower()
        if q in haystack:
            results.append(t)
            if len(results) >= limit:
                break
    return results


def detect_terms_in_text(text: str) -> list[dict]:
    text_l = (text or "").lower()
    matched = []
    for t in get_terms():
        if t.get("term", "").lower() in text_l:
            matched.append(t)
            continue
        for alias in t.get("aliases", []):
            if alias.lower() in text_l:
                matched.append(t)
                break
    return matched


def detect_products(text: str) -> list[dict]:
    products_by_id = {p["id"]: p for p in get_products()}
    out = []
    for hit in _engine().detect_products(text):
        base = dict(
            products_by_id.get(
                hit.product_id, {"id": hit.product_id, "name": hit.product_name}
            )
        )
        base["confidence"] = hit.confidence
        base["evidence_quotes"] = hit.evidence_quotes
        out.append(base)
    return out


def get_product(name: str) -> dict | None:
    n = (name or "").strip().lower()
    if not n:
        return None
    for p in get_products():
        names = [p.get("name", "").lower()] + [a.lower() for a in p.get("aliases", [])]
        if n in names:
            return p
    return None


def match_risks(text: str, product_type: str | None = None) -> list[dict]:
    hits = _engine().match_risks(text, product_type=product_type)
    return [
        {
            "id": h.pattern_id,
            "name": h.name,
            "risk_level": h.risk_level,
            "explanation": h.explanation,
            "quote": h.quote,
            "start": h.start,
            "end": h.end,
            "confidence": h.confidence,
        }
        for h in hits
    ]


def get_grounding_block(text: str) -> dict:
    text = text or ""
    products = detect_products(text)
    product = products[0] if products else None
    terms = detect_terms_in_text(text)
    product_type_id = product.get("id") if product else None
    risk_patterns = match_risks(text, product_type=product_type_id)
    if product_type_id is None:
        risk_patterns = match_risks(text, product_type=None)

    return {
        "detected_product_types": [p["name"] for p in products],
        "product": product,
        "terms": terms,
        "risk_patterns": risk_patterns,
    }

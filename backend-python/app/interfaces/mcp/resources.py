"""P2-10：MCP Resources（只读知识，经 Repository，禁止任意路径）。"""
from __future__ import annotations

import re
from typing import Any

from app.composition_root import get_knowledge_repository
from app.interfaces.mcp.sanitize import sanitize_public_payload

_SAFE_ID = re.compile(r"^[a-zA-Z0-9_.:-]{1,64}$")

RESOURCE_WHITELIST_PREFIXES = (
    "finance://manifest",
    "finance://products/",
    "finance://terms/",
    "finance://rules/",
)


class ResourceAccessError(ValueError):
    """非法 URI 或未知资源。"""


def _require_safe_id(value: str, *, label: str) -> str:
    text = (value or "").strip()
    if not text or not _SAFE_ID.fullmatch(text):
        raise ResourceAccessError(f"非法 {label}")
    if ".." in text or "/" in text or "\\" in text:
        raise ResourceAccessError(f"非法 {label}")
    return text


def list_resource_uris() -> list[str]:
    """静态约定 + 当前知识库可枚举条目。"""
    knowledge = get_knowledge_repository()
    uris = ["finance://manifest"]
    for p in knowledge.list_products():
        uris.append(f"finance://products/{p.id}")
    for t in knowledge.list_terms():
        uris.append(f"finance://terms/{t.id}")
    for r in knowledge.list_risk_patterns():
        uris.append(f"finance://rules/{r.id}")
    return uris


def read_resource(uri: str) -> dict[str, Any]:
    """按白名单 URI 读取；不打开任意文件路径。"""
    raw = (uri or "").strip()
    if not raw.startswith("finance://"):
        raise ResourceAccessError("仅支持 finance:// 资源")
    if any(ch in raw for ch in ("..", "\\", "\n", "\r")):
        raise ResourceAccessError("非法 URI")
    if not any(
        raw == "finance://manifest" or raw.startswith(prefix)
        for prefix in ("finance://products/", "finance://terms/", "finance://rules/")
    ):
        if raw != "finance://manifest":
            raise ResourceAccessError("URI 不在白名单")

    knowledge = get_knowledge_repository()
    if raw == "finance://manifest":
        manifest = knowledge.get_manifest()
        payload = {
            "schema_version": manifest.schema_version,
            "content_version": manifest.content_version,
            "last_verified_at": manifest.last_verified_at.isoformat(),
            "supported_products": [p.id for p in knowledge.list_products()],
            "term_count": len(knowledge.list_terms()),
            "rule_count": len(knowledge.list_risk_patterns()),
        }
        return sanitize_public_payload(payload)

    if raw.startswith("finance://products/"):
        product_id = _require_safe_id(raw.removeprefix("finance://products/"), label="product_type")
        for p in knowledge.list_products():
            if p.id == product_id:
                return sanitize_public_payload(p.model_dump(mode="json"))
        raise ResourceAccessError(f"未知产品：{product_id}")

    if raw.startswith("finance://terms/"):
        term_id = _require_safe_id(raw.removeprefix("finance://terms/"), label="term_id")
        for t in knowledge.list_terms():
            if t.id == term_id:
                return sanitize_public_payload(t.model_dump(mode="json"))
        raise ResourceAccessError(f"未知术语：{term_id}")

    if raw.startswith("finance://rules/"):
        rule_id = _require_safe_id(raw.removeprefix("finance://rules/"), label="rule_id")
        for r in knowledge.list_risk_patterns():
            if r.id == rule_id:
                data = r.model_dump(mode="json")
                # 不暴露可执行正则细节给外部也可；Demo 保留说明性字段，去掉密钥类
                return sanitize_public_payload(data)
        raise ResourceAccessError(f"未知规则：{rule_id}")

    raise ResourceAccessError("URI 不在白名单")

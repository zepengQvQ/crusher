"""P2-10：MCP 输出脱敏，禁止泄露密钥与本地路径。"""
from __future__ import annotations

from typing import Any

_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "llm_api_key",
        "base_url",
        "llm_base_url",
        "authorization",
        "token",
        "secret",
        "password",
    }
)


def sanitize_public_payload(value: Any) -> Any:
    """递归去掉敏感键；不抛出异常堆栈。"""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                continue
            out[str(key)] = sanitize_public_payload(item)
        return out
    if isinstance(value, list):
        return [sanitize_public_payload(v) for v in value]
    if isinstance(value, tuple):
        return [sanitize_public_payload(v) for v in value]
    return value

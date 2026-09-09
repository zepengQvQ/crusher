"""OpenAI 兼容 Chat Completions 异步网关。"""
from __future__ import annotations

import json
import re
from typing import Optional

import httpx

from app.config.settings import Settings
from app.domain.models.llm import LlmExplanation
from app.domain.llm_errors import (
    LlmInvalidJsonError,
    LlmRateLimitedError,
    LlmTimeoutError,
    LlmUpstreamError,
)

_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*(.*?)\s*```\s*$",
    re.IGNORECASE | re.DOTALL,
)


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    matched = _FENCE_RE.match(text)
    if matched:
        return matched.group(1).strip()
    return text


def parse_llm_explanation_content(content: str) -> LlmExplanation:
    """把模型 content 解析为 LlmExplanation；失败抛 LlmInvalidJsonError。"""
    if not isinstance(content, str) or not content.strip():
        raise LlmInvalidJsonError("empty content")
    payload = _strip_json_fence(content)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise LlmInvalidJsonError("content is not json") from exc
    try:
        return LlmExplanation.model_validate(data)
    except Exception as exc:  # noqa: BLE001 — Pydantic ValidationError 等
        raise LlmInvalidJsonError("content dto invalid") from exc


class OpenAiCompatibleLlmGateway:
    """POST {base}/chat/completions，Bearer Key；不引入供应商 SDK。"""

    def __init__(
        self,
        settings: Settings,
        *,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._api_key = settings.llm_api_key.strip()
        self._model = settings.llm_model.strip()
        self._base_url = settings.llm_base_url.strip().rstrip("/")
        self._temperature = settings.llm_temperature
        self._max_tokens = settings.llm_max_tokens
        self._client = client

    async def complete(self, prompt: str) -> LlmExplanation:
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }

        if self._client is not None:
            return await self._request(self._client, url, headers, payload)

        async with httpx.AsyncClient(timeout=60.0) as client:
            return await self._request(client, url, headers, payload)

    async def _request(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        payload: dict,
    ) -> LlmExplanation:
        try:
            resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise LlmTimeoutError("timeout") from exc
        except httpx.HTTPError as exc:
            raise LlmUpstreamError("http error") from exc

        if resp.status_code == 429:
            raise LlmRateLimitedError("rate limited")
        if resp.status_code >= 400:
            raise LlmUpstreamError(f"http {resp.status_code}")

        try:
            body = resp.json()
        except ValueError as exc:
            raise LlmInvalidJsonError("response not json") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmInvalidJsonError("missing choices content") from exc

        return parse_llm_explanation_content(content)

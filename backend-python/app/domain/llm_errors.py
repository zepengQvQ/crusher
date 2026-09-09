"""LLM 网关异常（应用层映射为错误码；勿带入 Key / 完整 Prompt）。"""
from __future__ import annotations


class LlmGatewayError(Exception):
    """大模型调用失败基类。"""


class LlmTimeoutError(LlmGatewayError):
    """等待模型超时。"""


class LlmRateLimitedError(LlmGatewayError):
    """上游限流。"""


class LlmInvalidJsonError(LlmGatewayError):
    """响应或内容 DTO 非法。"""


class LlmUpstreamError(LlmGatewayError):
    """其它上游错误。"""


class LlmConfigError(LlmGatewayError):
    """真实模式缺少必要配置。"""

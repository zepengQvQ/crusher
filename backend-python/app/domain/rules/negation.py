"""否定词与上下文窗口判定。"""
from __future__ import annotations

from typing import Sequence

# 多字优先；不用单独的「不」，避免误伤「不保证本金」等风险表述本身
DEFAULT_NEGATION_CUES: tuple[str, ...] = (
    "不收取",
    "不设置",
    "不设",
    "不收",
    "无需支付",
    "无需",
    "不用",
    "没有",
    "免收",
    "免除",
    "并不",
    "绝不",
    "无",
    "未",
    "非",
)


def is_negated_near(
    text: str,
    start: int,
    *,
    cues: Sequence[str] = DEFAULT_NEGATION_CUES,
    window: int = 16,
) -> bool:
    """匹配片段左侧 window 内是否出现否定提示。"""
    if start < 0:
        start = 0
    left = text[max(0, start - window) : start]
    for cue in sorted((c for c in cues if c), key=len, reverse=True):
        if cue in left:
            return True
    return False

"""否定词与分句边界判定。"""
from __future__ import annotations

from collections.abc import Sequence

# 多字优先；不用单独的「不」，避免误伤「不保证本金」等风险表述本身
DEFAULT_NEGATION_CUES: tuple[str, ...] = (
    "不收取",
    "不设置",
    "不属于",
    "不是",
    "并非",
    "不属",
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

# 否定向前搜索时遇到即停止（分句/句界）
NEGATION_STOP_CHARS = frozenset("，,；;。！？\n")

# 正向关键词组合的强句界
STRONG_SENTENCE_CHARS = frozenset("。！？；\n")


def is_negated_near(
    text: str,
    start: int,
    *,
    cues: Sequence[str] = DEFAULT_NEGATION_CUES,
    window: int = 16,
) -> bool:
    """匹配片段左侧是否出现否定提示。

    从 start 向前看，最多 window 字符；遇到分句标点立即停止，
    因此「不收申购费，管理费…」中的「不收」不会否定「管理费」。
    """
    if start < 0:
        start = 0
    left_chars: list[str] = []
    i = start - 1
    scanned = 0
    while i >= 0 and scanned < window:
        ch = text[i]
        if ch in NEGATION_STOP_CHARS:
            break
        left_chars.append(ch)
        scanned += 1
        i -= 1
    left = "".join(reversed(left_chars))
    for cue in sorted((c for c in cues if c), key=len, reverse=True):
        if cue in left:
            return True
    return False


def strong_sentence_span(text: str, pos: int) -> tuple[int, int]:
    """返回 pos 所在强句的 [start, end)。"""
    if not text:
        return 0, 0
    pos = max(0, min(pos, len(text) - 1))
    start = pos
    while start > 0 and text[start - 1] not in STRONG_SENTENCE_CHARS:
        start -= 1
    end = pos + 1
    while end < len(text) and text[end] not in STRONG_SENTENCE_CHARS:
        end += 1
    if end < len(text) and text[end] in STRONG_SENTENCE_CHARS:
        end += 1
    return start, end


def expand_to_clause(text: str, start: int, end: int) -> tuple[int, int, str]:
    """把命中片段扩成可读分句（遇强句界/逗号停），并保证 text[start:end]==quote。"""
    if start < 0:
        start = 0
    if end > len(text):
        end = len(text)
    left = start
    while left > 0 and text[left - 1] not in NEGATION_STOP_CHARS:
        left -= 1
    right = end
    while right < len(text) and text[right] not in NEGATION_STOP_CHARS:
        right += 1
    quote = text[left:right].strip()
    # strip 后重新对齐到原文（去掉左右空白）
    if quote:
        real = text.find(quote, left, right + 1)
        if real >= 0:
            return real, real + len(quote), quote
    return start, end, text[start:end]

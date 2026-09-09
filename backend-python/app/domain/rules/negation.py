"""否定词与分句边界判定。

Java 对照：规则匹配的轻量文本工具类（句界切分 + 目标绑定否定）。
"""
from __future__ import annotations

import re
from collections.abc import Iterator, Sequence

# 多字优先；短字「未/非」需目标绑定，避免误伤「未按期」「非循环贷款」
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

# 命中片段后置、表示「不收费」的提示
POST_NEGATION_CUES: tuple[str, ...] = (
    "不收取",
    "不收",
    "免收",
    "免除",
    "无需支付",
    "无需",
)

# 「未」后接这些词时，是逾期/还款前提，不是否定收费/罚息
_WEI_PREMISE_RE = re.compile(r"^(按期|按时|到期|清偿|偿还|还款|履约)")

# 否定向前/后搜索时遇到即停止（分句/句界）
NEGATION_STOP_CHARS = frozenset("，,；;。！？\n")

# 正向关键词组合的强句界
STRONG_SENTENCE_CHARS = frozenset("。！？；\n")


def iter_strong_sentences(text: str) -> Iterator[tuple[int, int, str]]:
    """按强句界切分，yield (start, end, sentence)，end 含句末标点。"""
    if not text:
        return
    cursor = 0
    n = len(text)
    while cursor < n:
        start, end = strong_sentence_span(text, cursor)
        if end <= start:
            break
        yield start, end, text[start:end]
        if end <= cursor:
            cursor += 1
        else:
            cursor = end


def is_negated_near(
    text: str,
    start: int,
    *,
    cues: Sequence[str] = DEFAULT_NEGATION_CUES,
    window: int = 16,
    end: int | None = None,
) -> bool:
    """兼容旧接口：仅看左侧；若提供 end 则同时检查后置免收类提示。"""
    target_end = end if end is not None else start
    return is_target_negated(text, start, target_end, cues=cues, window=window)


def is_target_negated(
    text: str,
    start: int,
    end: int,
    *,
    cues: Sequence[str] = DEFAULT_NEGATION_CUES,
    window: int = 16,
) -> bool:
    """判断 [start, end) 目标是否被否定。

    - 支持目标前的「不/不是/并非/无需支付」等。
    - 支持目标后的「免收/不收取」等。
    - 支持跨关键词中间的「不收」（如提前还款不收违约金）。
    - 「未按期还款」的「未」不否定罚息；「非循环贷款」的「非」不否定贷款。
    """
    if start < 0:
        start = 0
    if end < start:
        end = start
    if _left_negates_target(text, start, cues=cues, window=window):
        return True
    if _mid_span_waiver(text, start, end, cues=cues):
        return True
    if _right_waiver_after_target(text, end, window=window):
        return True
    return False


def _mid_span_waiver(text: str, start: int, end: int, *, cues: Sequence[str]) -> bool:
    """目标跨度内部是否出现收费否定（提前还款不收违约金）。"""
    if end - start <= 0:
        return False
    mid = text[start:end]
    waiver = set(POST_NEGATION_CUES) | {
        c for c in cues if c in {"不收取", "不收", "免收", "免除", "无需支付", "无需", "没有"}
    }
    for cue in sorted(waiver, key=len, reverse=True):
        if cue and cue in mid:
            return True
    return False


def _left_negates_target(
    text: str,
    start: int,
    *,
    cues: Sequence[str],
    window: int,
) -> bool:
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
    if not left:
        return False

    for cue in sorted((c for c in cues if c), key=len, reverse=True):
        pos = left.rfind(cue)
        if pos < 0:
            continue
        between = left[pos + len(cue) :]
        if cue in {"未", "非"}:
            if between.strip() == "":
                # 「非贷款」「未收费」——短否定紧贴目标
                return True
            if cue == "未" and _WEI_PREMISE_RE.match(between):
                continue
            if cue == "非":
                # 「非循环贷款」：非与目标之间还有其它词，不视为否定产品
                continue
            continue
        # 多字否定：出现在目标左侧同一分句内即生效
        return True
    return False


def _right_waiver_after_target(text: str, end: int, *, window: int) -> bool:
    right_chars: list[str] = []
    i = end
    scanned = 0
    while i < len(text) and scanned < window:
        ch = text[i]
        if ch in NEGATION_STOP_CHARS:
            break
        right_chars.append(ch)
        scanned += 1
        i += 1
    right = "".join(right_chars)
    for cue in sorted(POST_NEGATION_CUES, key=len, reverse=True):
        if cue in right:
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
    if quote:
        real = text.find(quote, left, right + 1)
        if real >= 0:
            return real, real + len(quote), quote
    return start, end, text[start:end]


def expand_evidence_for_conditions(
    text: str,
    start: int,
    end: int,
    required_parts: Sequence[str],
) -> tuple[int, int, str]:
    """在同一强句内扩展证据，尽量覆盖 required_parts（如逾期+罚息利率）。"""
    sent_start, sent_end = strong_sentence_span(text, start)
    sentence = text[sent_start:sent_end]
    span_start, span_end = start, end
    for part in required_parts:
        if not part:
            continue
        local = sentence.find(part)
        if local < 0:
            continue
        abs_s = sent_start + local
        abs_e = abs_s + len(part)
        span_start = min(span_start, abs_s)
        span_end = max(span_end, abs_e)
    return expand_to_clause(text, span_start, span_end)

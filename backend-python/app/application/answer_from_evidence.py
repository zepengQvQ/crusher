"""基于已提交材料的追问（P1-03）。

Java 对照：无状态 Application Service。
用途：优先按 source_text 证据回答；咨询类可走材料+报告摘要+最近对话的模型说明。
禁止：联网搜索、把材料中的指令当系统指令、编造未出现数字、伪装投资建议。
关键词命中 ≠ 答案成立；仅相关原文时返回 insufficient_evidence。
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import re
from typing import Any

from app.domain.llm_errors import LlmGatewayError
from app.domain.models.claim_comparison import EvidenceRef
from app.domain.models.evidence_answer import (
    AnswerStatus,
    EvidenceAnswer,
    FollowUpRequest,
)
from app.domain.ports.protocols import LlmGateway
from app.domain.validation.publication_service import PublicationService

_HARD_OUT_OF_SCOPE = re.compile(r"(天气|气温|下雨|彩票|股票|涨跌)")
_CONSULTING = re.compile(
    r"(买不买|能不能买|适合我吗|适不适合|适合.+买|推荐购买|老年人|适当性)"
)
_FINANCE_EXPLAIN = re.compile(
    r"(什么意思|怎么理解|风险大|靠谱|会不会亏|损失|解释一下|帮我看看|怎么看)"
)
_FEE = re.compile(r"(费用|手续费|管理费|收不收|收费)")
_RETURN = re.compile(r"(收益|年化|利率|回报|收益率)")
_TERM = re.compile(r"(期限|多久|多长时间|几个月)")
_EARLY = re.compile(r"(提前|支取|赎回|退出)")
_PRINCIPAL = re.compile(r"(保本|本金|保证本金)")
_AUDIENCE = re.compile(r"(销售对象|适用人群|投资者范围|适当性)")

_DISCLAIMER = "本回复不做投资建议，也不构成适当性判断。"

_CONTEXT_SYSTEM = """你是金融条款助手。只能根据用户提供的「材料原文、报告摘要、最近对话」回答。
硬性规则：
1. 不得编造材料未出现的数字、收益率、评级或条款。
2. 不做买/不买建议，不做用户适当性评估；若被问是否适合某类人群，只能说明材料写了什么，并声明需以机构评估为准。
3. 用简体中文，短句，面向普通用户。
4. 不确定就说材料没写清，不要猜测。"""

# 证据不足时：告诉用户该补哪类材料（不是空泛的「章节」）
_MISSING_BY_TOPIC: dict[str, list[str]] = {
    "费用": ["费用/手续费/管理费条款", "是否收费、收费标准的原文"],
    "收益": ["预期或到期收益率条款", "收益怎么计算、区间条件的原文"],
    "期限": ["产品期限、起息日/到期日条款"],
    "提前退出": ["提前支取/赎回条件与费用（含违约金）条款"],
    "本金保障": ["保本或非保本、本金是否保证的原文"],
    "销售对象": ["销售对象、适用人群或投资者范围相关条款"],
}


def _topic_from_question(q: str) -> str:
    if _FEE.search(q):
        return "费用"
    if _RETURN.search(q):
        return "收益"
    if _TERM.search(q):
        return "期限"
    if _EARLY.search(q):
        return "提前退出"
    if _PRINCIPAL.search(q):
        return "本金保障"
    if _AUDIENCE.search(q):
        return "销售对象"
    return ""


def _missing_materials(topic: str, question: str) -> list[str]:
    if topic and topic in _MISSING_BY_TOPIC:
        return list(_MISSING_BY_TOPIC[topic])
    short_q = question.strip()
    if len(short_q) > 24:
        short_q = short_q[:24] + "…"
    return [f"能直接回答「{short_q}」的正式条款原文"]


def _find_snippet(text: str, *needles: str) -> EvidenceRef | None:
    for n in needles:
        idx = text.find(n)
        if idx >= 0:
            end = min(len(text), idx + max(len(n), 12))
            # 扩到句界
            right = text.find("。", idx)
            if right > idx:
                end = right + 1
            return EvidenceRef(
                source_id="source",
                quote=text[idx:end],
                start=idx,
                end=end,
                confidence=1.0,
            )
    return None


_HAS_PCT = re.compile(r"\d+(?:\.\d+)?\s*[%％]")
_HAS_TERM = re.compile(r"\d+\s*(个?月|年|天)")
_HAS_FEE_ANSWER = re.compile(r"(不收|免收|无需|没有|0|零|\d+(?:\.\d+)?\s*[%％]|违约金)")
_HAS_PRINCIPAL_ANSWER = re.compile(r"(非保本|不保本|保本|保证本金|不承诺保本|存款保险)")


def _snippet_answers(label: str, quote: str) -> bool:
    """关键词命中后，片段是否足以构成确定答案。"""
    if label == "费用":
        return bool(_HAS_FEE_ANSWER.search(quote))
    if label == "收益":
        return bool(_HAS_PCT.search(quote))
    if label == "期限":
        return bool(_HAS_TERM.search(quote))
    if label == "提前退出":
        return bool(
            re.search(r"(不支持|不可|不得|可以|支持|允许|违约金|手续费)", quote)
        )
    if label == "本金保障":
        return bool(_HAS_PRINCIPAL_ANSWER.search(quote))
    # 模糊检索：仅关键词不算答案
    return False


def _run_async(coro: Any) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _ensure_disclaimer(text: str) -> str:
    body = (text or "").strip()
    if not body:
        body = "按现有材料只能作有限说明，无法给出确定结论。"
    if "投资建议" not in body and "适当性" not in body:
        return f"{body}\n\n{_DISCLAIMER}"
    if _DISCLAIMER not in body and "不做投资建议" not in body:
        return f"{body}\n\n{_DISCLAIMER}"
    return body


class AnswerFromEvidenceUseCase:
    def __init__(
        self,
        publication: PublicationService | None = None,
        llm_gateway: LlmGateway | None = None,
    ) -> None:
        self._publication = publication or PublicationService()
        self._llm = llm_gateway

    def execute(self, request: FollowUpRequest) -> EvidenceAnswer:
        q = request.question.strip()
        text = request.source_text

        # 非金融闲聊/彩票等：硬拒答
        if _HARD_OUT_OF_SCOPE.search(q) and not _CONSULTING.search(q):
            raw = EvidenceAnswer(
                question=q,
                status=AnswerStatus.out_of_scope,
                answer="这个问题超出本 Demo 材料核对范围。",
                missing_info=[],
            )
            return self._publication.finalize_follow_up(raw, source_text=text)

        # 咨询/适当性：走上下文模型说明（2A）
        if _CONSULTING.search(q):
            return self._contextual(request)

        label = _topic_from_question(q)
        subject_hit: EvidenceRef | None = None
        if label == "费用":
            subject_hit = _find_snippet(text, "手续费", "管理费", "费用", "不收费", "免收")
        elif label == "收益":
            subject_hit = _find_snippet(text, "年化", "收益率", "利率", "收益")
        elif label == "期限":
            subject_hit = _find_snippet(text, "期限", "个月", "一年", "1年", "天")
        elif label == "提前退出":
            subject_hit = _find_snippet(text, "提前", "支取", "赎回", "违约金")
        elif label == "本金保障":
            subject_hit = _find_snippet(text, "非保本", "保本", "本金")
        elif label == "销售对象":
            subject_hit = _find_snippet(
                text, "销售对象", "适用人群", "投资者", "适当性", "个人客户"
            )
        else:
            for token in re.findall(r"[\u4e00-\u9fff]{2,8}", q):
                subject_hit = _find_snippet(text, token)
                if subject_hit:
                    label = token
                    break

        if subject_hit is None:
            if _FINANCE_EXPLAIN.search(q) or (request.report_digest or "").strip():
                return self._contextual(request)
            missing = _missing_materials(_topic_from_question(q), q)
            raw = EvidenceAnswer(
                question=q,
                status=AnswerStatus.insufficient_evidence,
                answer="当前材料里找不到足够依据，没法确定回答。",
                evidence=[],
                missing_info=missing,
            )
            return self._publication.finalize_follow_up(raw, source_text=text)

        topic = _topic_from_question(q) or label
        if not _snippet_answers(topic if topic in _MISSING_BY_TOPIC else label, subject_hit.quote):
            missing = _missing_materials(topic if topic in _MISSING_BY_TOPIC else "", q)
            raw = EvidenceAnswer(
                question=q,
                status=AnswerStatus.insufficient_evidence,
                answer="材料里只有相关字眼，还不足以给出确定结论。",
                evidence=[subject_hit],
                missing_info=missing,
            )
            return self._publication.finalize_follow_up(raw, source_text=text)

        raw = EvidenceAnswer(
            question=q,
            status=AnswerStatus.answered,
            answer=f"根据已提交材料，与「{label}」相关的原文如下，请自行核对，不作投资建议。",
            evidence=[subject_hit],
            missing_info=[],
        )
        return self._publication.finalize_follow_up(raw, source_text=text)

    def _contextual(self, request: FollowUpRequest) -> EvidenceAnswer:
        q = request.question.strip()
        text = request.source_text
        if self._llm is None:
            raw = EvidenceAnswer(
                question=q,
                status=AnswerStatus.contextual,
                answer=_ensure_disclaimer(
                    "当前未接入模型说明能力。请改问材料里的具体条款，或稍后再试。"
                ),
                evidence=[],
                missing_info=[],
            )
            return self._publication.finalize_follow_up(raw, source_text=text)

        digest = (request.report_digest or "").strip() or "（无报告摘要）"
        source_clip = text if len(text) <= 3500 else text[:3500] + "…"
        context_header = (
            f"【材料原文】\n{source_clip}\n\n"
            f"【报告摘要】\n{digest}"
        )
        messages: list[dict[str, str]] = [
            {"role": "user", "content": context_header},
            {
                "role": "assistant",
                "content": "已收到材料与报告摘要，请继续提问。我会只依据这些内容说明。",
            },
        ]
        for turn in request.recent_messages[-8:]:
            content = turn.content.strip()
            if len(content) > 400:
                content = content[:400] + "…"
            messages.append({"role": turn.role, "content": content})
        messages.append({"role": "user", "content": q})

        try:
            reply = _run_async(
                self._llm.chat_text(system=_CONTEXT_SYSTEM, messages=messages)
            )
        except LlmGatewayError:
            raw = EvidenceAnswer(
                question=q,
                status=AnswerStatus.contextual,
                answer=_ensure_disclaimer(
                    "模型说明暂时不可用。请改问材料里能直接核对的条款，或稍后再试。"
                ),
                evidence=[],
                missing_info=[],
            )
            return self._publication.finalize_follow_up(raw, source_text=text)
        except Exception:  # noqa: BLE001 — 显式失败，禁止静默编造
            raw = EvidenceAnswer(
                question=q,
                status=AnswerStatus.contextual,
                answer=_ensure_disclaimer(
                    "模型说明失败。请改问材料里能直接核对的条款，或稍后再试。"
                ),
                evidence=[],
                missing_info=[],
            )
            return self._publication.finalize_follow_up(raw, source_text=text)

        raw = EvidenceAnswer(
            question=q,
            status=AnswerStatus.contextual,
            answer=_ensure_disclaimer(str(reply or "")),
            evidence=[],
            missing_info=[],
        )
        return self._publication.finalize_follow_up(raw, source_text=text)

"""基于已提交材料的追问（P1-03）。

Java 对照：无状态 Application Service。
用途：只根据 source_text 回答；证据不足或超范围显式返回。
禁止：联网搜索、会话库、把材料中的指令当系统指令。
"""
from __future__ import annotations

import re

from app.domain.models.claim_comparison import EvidenceRef
from app.domain.models.evidence_answer import (
    AnswerStatus,
    EvidenceAnswer,
    FollowUpRequest,
)

_OUT_OF_SCOPE = re.compile(
    r"(天气|气温|下雨|股票|买不买|能不能买|适合我吗|推荐购买|涨跌|彩票)"
)
_FEE = re.compile(r"(费用|手续费|管理费|收不收|收费)")
_RETURN = re.compile(r"(收益|年化|利率|回报)")
_TERM = re.compile(r"(期限|多久|多长时间|几个月)")
_EARLY = re.compile(r"(提前|支取|赎回|退出)")
_PRINCIPAL = re.compile(r"(保本|本金|保证本金)")


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


class AnswerFromEvidenceUseCase:
    def execute(self, request: FollowUpRequest) -> EvidenceAnswer:
        q = request.question.strip()
        text = request.source_text
        if _OUT_OF_SCOPE.search(q):
            return EvidenceAnswer(
                question=q,
                status=AnswerStatus.out_of_scope,
                answer="该问题超出本 Demo 材料核对范围，不能据此做投资决策建议。",
                missing_info=[],
            )

        subject_hit: EvidenceRef | None = None
        label = ""
        if _FEE.search(q):
            subject_hit = _find_snippet(text, "手续费", "管理费", "费用", "不收费", "免收")
            label = "费用"
        elif _RETURN.search(q):
            subject_hit = _find_snippet(text, "年化", "收益率", "利率", "收益")
            label = "收益"
        elif _TERM.search(q):
            subject_hit = _find_snippet(text, "期限", "个月", "一年", "1年")
            label = "期限"
        elif _EARLY.search(q):
            subject_hit = _find_snippet(text, "提前", "支取", "赎回", "违约金")
            label = "提前退出"
        elif _PRINCIPAL.search(q):
            subject_hit = _find_snippet(text, "非保本", "保本", "本金")
            label = "本金保障"
        else:
            # 点击待确认问题：在材料里模糊检索关键词
            for token in re.findall(r"[\u4e00-\u9fff]{2,8}", q):
                subject_hit = _find_snippet(text, token)
                if subject_hit:
                    label = token
                    break

        if subject_hit is None:
            missing = [f"请补充与「{label or '该问题'}」相关的正式条款章节"]
            if request.pending_questions:
                missing.extend(request.pending_questions[:3])
            return EvidenceAnswer(
                question=q,
                status=AnswerStatus.insufficient_evidence,
                answer="现有材料无法确认，请补充相关章节后再问。",
                evidence=[],
                missing_info=missing,
            )

        return EvidenceAnswer(
            question=q,
            status=AnswerStatus.answered,
            answer=f"根据已提交材料，与「{label}」相关的原文如下，请自行核对，不作投资建议。",
            evidence=[subject_hit],
            missing_info=[],
        )

"""销售主张与正式材料对照（P1-01）。

Java 对照：无状态 Domain Service。
输入：销售 Claim 列表 + 正式材料全文。
输出：ClaimComparison 列表；数值/否定/单位标准化后再比较。
"""
from __future__ import annotations

import re
from decimal import Decimal
from uuid import uuid4

from app.domain.models.claim_comparison import Claim, ClaimComparison, EvidenceRef
from app.domain.models.p1_enums import ClaimStatus, ClaimSubject

_COND_CUES = ("若", "如果", "需满足", "在……前提下", "前提是", "附加条件", "观察区间", "达到条件后")
_VAGUE_CUES = ("视情况", "可能", "原则上", "以实际为准", "另行通知", "具体以合同为准", "约", "大约")


def _find_quote(text: str, *needles: str) -> EvidenceRef | None:
    for n in needles:
        if not n:
            continue
        idx = text.find(n)
        if idx >= 0:
            end = idx + len(n)
            return EvidenceRef(
                source_id="official",
                quote=text[idx:end],
                start=idx,
                end=end,
                confidence=1.0,
            )
    return None


def _sentence_around(text: str, start: int) -> str:
    left = max(
        text.rfind("。", 0, start),
        text.rfind("；", 0, start),
        text.rfind("\n", 0, start),
    )
    right_candidates = [
        text.find(ch, start)
        for ch in ("。", "；", "\n")
        if text.find(ch, start) >= 0
    ]
    right = min(right_candidates) if right_candidates else len(text)
    return text[left + 1 : right if right >= 0 else len(text)]


def _percent_in_text(text: str) -> list[tuple[Decimal, int, int]]:
    out: list[tuple[Decimal, int, int]] = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*%", text):
        out.append((Decimal(m.group(1)), m.start(), m.end()))
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*bp", text, re.I):
        # 50bp = 0.5%
        out.append((Decimal(m.group(1)) / Decimal(100), m.start(), m.end()))
    return out


def _term_months_in_text(text: str) -> list[tuple[Decimal, int, int]]:
    out: list[tuple[Decimal, int, int]] = []
    for m in re.finditer(r"(\d+)\s*(个?月|年|天)", text):
        n = int(m.group(1))
        u = m.group(2)
        if "年" in u:
            months = Decimal(n * 12)
        elif "天" in u:
            months = (Decimal(n) / Decimal(30)).quantize(Decimal("0.01"))
        else:
            months = Decimal(n)
        out.append((months, m.start(), m.end()))
    return out


def _has_any(text: str, cues: tuple[str, ...]) -> bool:
    return any(c in text for c in cues)


def match_claims_to_official(
    sales_claims: list[Claim],
    official_text: str,
    *,
    official_source_id: str,
) -> list[ClaimComparison]:
    """把销售主张映射到正式材料对照卡。"""
    results: list[ClaimComparison] = []
    for claim in sales_claims:
        cmp = _match_one(claim, official_text, official_source_id)
        results.append(cmp)
    return results


def _match_one(claim: Claim, official: str, official_source_id: str) -> ClaimComparison:
    cid = f"cmp_{uuid4().hex[:8]}"

    if claim.subject == ClaimSubject.expected_return:
        return _match_return(claim, official, official_source_id, cid)
    if claim.subject == ClaimSubject.fee:
        return _match_fee(claim, official, official_source_id, cid)
    if claim.subject == ClaimSubject.term:
        return _match_term(claim, official, official_source_id, cid)
    if claim.subject == ClaimSubject.early_exit:
        return _match_early(claim, official, official_source_id, cid)
    if claim.subject == ClaimSubject.principal_protection:
        return _match_principal(claim, official, official_source_id, cid)
    return ClaimComparison(
        comparison_id=cid,
        subject=claim.subject,
        status=ClaimStatus.uncertain,
        summary="当前主题暂无法自动对照",
        sales_claim=claim,
        suggested_follow_up="请人工核对正式材料相关章节",
    )


def _ev(official_source_id: str, text: str, start: int, end: int) -> EvidenceRef:
    return EvidenceRef(
        source_id=official_source_id,
        quote=text[start:end],
        start=start,
        end=end,
        confidence=1.0,
    )


def _match_return(
    claim: Claim, official: str, sid: str, cid: str
) -> ClaimComparison:
    hits = _percent_in_text(official)
    if claim.numeric_value is None:
        return ClaimComparison(
            comparison_id=cid,
            subject=claim.subject,
            status=ClaimStatus.uncertain,
            summary="销售收益主张缺少可比较数值",
            sales_claim=claim,
            suggested_follow_up="请确认销售承诺的具体收益率",
        )
    # 找同数值
    for val, s, e in hits:
        if val == claim.numeric_value:
            sent = _sentence_around(official, s)
            if _has_any(sent, _COND_CUES):
                return ClaimComparison(
                    comparison_id=cid,
                    subject=claim.subject,
                    status=ClaimStatus.conditional,
                    summary="正式材料存在同数值收益，但附加条件",
                    sales_claim=claim,
                    official_evidence=_ev(sid, official, s, e),
                    suggested_follow_up="请核对收益触发条件是否与销售口径一致",
                )
            if _has_any(sent, _VAGUE_CUES):
                return ClaimComparison(
                    comparison_id=cid,
                    subject=claim.subject,
                    status=ClaimStatus.uncertain,
                    summary="正式材料表述模糊，无法确认与销售承诺等价",
                    sales_claim=claim,
                    official_evidence=_ev(sid, official, s, e),
                    suggested_follow_up="请补充收益计算口径或找明确条款",
                )
            return ClaimComparison(
                comparison_id=cid,
                subject=claim.subject,
                status=ClaimStatus.confirmed,
                summary="正式材料写明了与销售一致的收益数值",
                sales_claim=claim,
                official_evidence=_ev(sid, official, s, e),
            )
    # 有收益相关但数值不同 → conflict；完全没有 → not_found
    if re.search(r"收益|年化|利率", official):
        # 取第一个百分比作冲突证据
        if hits:
            val, s, e = hits[0]
            return ClaimComparison(
                comparison_id=cid,
                subject=claim.subject,
                status=ClaimStatus.conflict,
                summary=f"销售称 {claim.numeric_value}%，正式材料出现 {val}%",
                sales_claim=claim,
                official_evidence=_ev(sid, official, s, e),
                suggested_follow_up="请向销售确认最终收益口径以哪份材料为准",
            )
        vague = _find_quote(official, "收益", "年化", "利率")
        if vague:
            vague.source_id = sid
            return ClaimComparison(
                comparison_id=cid,
                subject=claim.subject,
                status=ClaimStatus.uncertain,
                summary="正式材料提到收益但无明确可比数值",
                sales_claim=claim,
                official_evidence=vague,
                suggested_follow_up="请在说明书中定位具体收益率条款",
            )
    return ClaimComparison(
        comparison_id=cid,
        subject=claim.subject,
        status=ClaimStatus.not_found,
        summary="销售承诺了收益，正式材料未找到对应表述",
        sales_claim=claim,
        suggested_follow_up="请在产品说明/合同中查找收益条款",
    )


def _match_fee(claim: Claim, official: str, sid: str, cid: str) -> ClaimComparison:
    free = re.search(r"(不收|免收|无需支付|不收取).{0,8}(手续费|管理费|费用)|不收费", official)
    charge = re.search(
        r"(收取|需支付).{0,12}(\d+(?:\.\d+)?)\s*%|(\d+(?:\.\d+)?)\s*%.{0,8}(手续费|管理费|费用)",
        official,
    )
    if claim.negated or claim.numeric_value == Decimal("0"):
        if free:
            return ClaimComparison(
                comparison_id=cid,
                subject=claim.subject,
                status=ClaimStatus.confirmed,
                summary="双方均表述不收费/免收",
                sales_claim=claim,
                official_evidence=_ev(sid, official, free.start(), free.end()),
            )
        if charge:
            return ClaimComparison(
                comparison_id=cid,
                subject=claim.subject,
                status=ClaimStatus.conflict,
                summary="销售称不收费，正式材料写明收取费用",
                sales_claim=claim,
                official_evidence=_ev(sid, official, charge.start(), charge.end()),
                suggested_follow_up="请核对费用章节，确认是否存在隐藏收费",
            )
        return ClaimComparison(
            comparison_id=cid,
            subject=claim.subject,
            status=ClaimStatus.not_found,
            summary="销售称不收费，正式材料未找到费用条款",
            sales_claim=claim,
            suggested_follow_up="请在正式材料中查找费用与收费标准",
        )
    # 销售称收费
    if charge and claim.numeric_value is not None:
        nums = _percent_in_text(charge.group(0))
        if nums and nums[0][0] == claim.numeric_value:
            return ClaimComparison(
                comparison_id=cid,
                subject=claim.subject,
                status=ClaimStatus.confirmed,
                summary="费用比例与正式材料一致",
                sales_claim=claim,
                official_evidence=_ev(sid, official, charge.start(), charge.end()),
            )
        if nums:
            return ClaimComparison(
                comparison_id=cid,
                subject=claim.subject,
                status=ClaimStatus.conflict,
                summary="销售与正式材料费用比例不一致",
                sales_claim=claim,
                official_evidence=_ev(sid, official, charge.start(), charge.end()),
                suggested_follow_up="请确认最终费率以合同为准",
            )
    if free:
        return ClaimComparison(
            comparison_id=cid,
            subject=claim.subject,
            status=ClaimStatus.conflict,
            summary="销售称收费，正式材料写免收",
            sales_claim=claim,
            official_evidence=_ev(sid, official, free.start(), free.end()),
        )
    return ClaimComparison(
        comparison_id=cid,
        subject=claim.subject,
        status=ClaimStatus.not_found,
        summary="正式材料未找到对应费用表述",
        sales_claim=claim,
        suggested_follow_up="请补充费用相关正式条款",
    )


def _match_term(claim: Claim, official: str, sid: str, cid: str) -> ClaimComparison:
    if claim.numeric_value is None:
        return ClaimComparison(
            comparison_id=cid,
            subject=claim.subject,
            status=ClaimStatus.uncertain,
            summary="销售期限缺少可比较数值",
            sales_claim=claim,
        )
    terms = _term_months_in_text(official)
    for months, s, e in terms:
        if months == claim.numeric_value:
            return ClaimComparison(
                comparison_id=cid,
                subject=claim.subject,
                status=ClaimStatus.confirmed,
                summary="期限与正式材料一致（已标准化到月）",
                sales_claim=claim,
                official_evidence=_ev(sid, official, s, e),
            )
    if terms:
        months, s, e = terms[0]
        return ClaimComparison(
            comparison_id=cid,
            subject=claim.subject,
            status=ClaimStatus.conflict,
            summary=f"销售约 {claim.numeric_value} 个月，正式材料约 {months} 个月",
            sales_claim=claim,
            official_evidence=_ev(sid, official, s, e),
        )
    return ClaimComparison(
        comparison_id=cid,
        subject=claim.subject,
        status=ClaimStatus.not_found,
        summary="正式材料未找到期限表述",
        sales_claim=claim,
        suggested_follow_up="请在说明书中查找产品/借款期限",
    )


def _match_early(claim: Claim, official: str, sid: str, cid: str) -> ClaimComparison:
    allow = re.search(
        r"(支持|可|允许).{0,6}提前(支取|赎回|还款)"
        r"|提前(支取|赎回|还款).{0,6}(免费|不收)",
        official,
    )
    cost = re.search(
        r"提前(支取|赎回|还款).{0,20}(违约金|手续费|费用|需)",
        official,
    )
    cond = re.search(
        r"提前(支取|赎回|还款).{0,40}(若|如果|需|条件|满)",
        official,
    )
    if allow and not cost:
        return ClaimComparison(
            comparison_id=cid,
            subject=claim.subject,
            status=ClaimStatus.confirmed,
            summary="正式材料同样允许提前退出且未写收费",
            sales_claim=claim,
            official_evidence=_ev(sid, official, allow.start(), allow.end()),
        )
    if cost or cond:
        m = cost or cond
        assert m is not None
        status = ClaimStatus.conditional if cond and not (
            claim.summary.find("付费") >= 0
        ) else ClaimStatus.conflict
        # 销售说可提前且暗示免费，正式有条件/费用 → conditional
        if "付费" not in claim.summary and (cost or cond):
            status = ClaimStatus.conditional
        return ClaimComparison(
            comparison_id=cid,
            subject=claim.subject,
            status=status,
            summary="正式材料对提前退出有附加条件或费用",
            sales_claim=claim,
            official_evidence=_ev(sid, official, m.start(), m.end()),
            suggested_follow_up="请核对提前退出条件与费用条款",
        )
    return ClaimComparison(
        comparison_id=cid,
        subject=claim.subject,
        status=ClaimStatus.not_found,
        summary="正式材料未找到提前退出相关表述",
        sales_claim=claim,
        suggested_follow_up="请查找流动性/提前支取章节",
    )


def _match_principal(claim: Claim, official: str, sid: str, cid: str) -> ClaimComparison:
    not_p = re.search(r"非保本|不保本|不承诺保本|不保证本金", official)
    yes_p = re.search(r"(?<!非)(?<!不)保本|保证本金", official)
    if claim.negated:
        if not_p:
            return ClaimComparison(
                comparison_id=cid,
                subject=claim.subject,
                status=ClaimStatus.confirmed,
                summary="双方均表述非保本/不承诺保本",
                sales_claim=claim,
                official_evidence=_ev(sid, official, not_p.start(), not_p.end()),
            )
        if yes_p:
            return ClaimComparison(
                comparison_id=cid,
                subject=claim.subject,
                status=ClaimStatus.conflict,
                summary="销售称非保本，正式材料出现保本表述",
                sales_claim=claim,
                official_evidence=_ev(sid, official, yes_p.start(), yes_p.end()),
            )
    else:
        if yes_p and not not_p:
            return ClaimComparison(
                comparison_id=cid,
                subject=claim.subject,
                status=ClaimStatus.confirmed,
                summary="双方均表述保本",
                sales_claim=claim,
                official_evidence=_ev(sid, official, yes_p.start(), yes_p.end()),
            )
        if not_p:
            return ClaimComparison(
                comparison_id=cid,
                subject=claim.subject,
                status=ClaimStatus.conflict,
                summary="销售称保本，正式材料写明非保本",
                sales_claim=claim,
                official_evidence=_ev(sid, official, not_p.start(), not_p.end()),
            )
    return ClaimComparison(
        comparison_id=cid,
        subject=claim.subject,
        status=ClaimStatus.not_found,
        summary="正式材料未找到本金保障相关表述",
        sales_claim=claim,
        suggested_follow_up="请在风险揭示中查找本金条款",
    )

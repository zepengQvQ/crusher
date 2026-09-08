"""
金融知识库加载与查询模块（唯一的事实真相源）

所有金融事实数据来自 data/knowledge/ 下的 JSON（terms / products / risk_patterns）。
本模块是纯同步、无状态的确定性查询，被两处复用：
  1. backend/knowledge_client.py —— pipeline 进程内直接调用（热路径）
  2. mcp/server.py —— 把同一套函数暴露成 MCP 工具（供外部 agent / Claude Code）

模型不得自行编造金融知识；本模块查不到的事实，上层一律标注「未收录」。
"""
import json
import os
import re
from functools import lru_cache

_KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "knowledge",
)


@lru_cache(maxsize=1)
def _load_json(filename: str):
    """加载知识库 JSON，模块级缓存（跨 pipeline run 复用）。"""
    path = os.path.join(_KNOWLEDGE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_terms() -> list[dict]:
    return _load_json("terms.json")


def get_products() -> list[dict]:
    return _load_json("products.json")


def get_risk_patterns() -> list[dict]:
    return _load_json("risk_patterns.json")


# ============================================================
# 术语查询
# ============================================================

def search_terms(query: str, limit: int = 10) -> list[dict]:
    """按关键词搜术语词典（匹配 term / aliases / category）。"""
    q = (query or "").strip().lower()
    if not q:
        return []
    results = []
    for t in get_terms():
        haystack = " ".join([
            t.get("term", ""),
            " ".join(t.get("aliases", [])),
            t.get("category", ""),
        ]).lower()
        if q in haystack:
            results.append(t)
            if len(results) >= limit:
                break
    return results


def detect_terms_in_text(text: str) -> list[dict]:
    """从条款文本中提取命中的术语条目（term / aliases 子串匹配）。"""
    text_l = (text or "").lower()
    matched = []
    for t in get_terms():
        if t.get("term", "").lower() in text_l:
            matched.append(t)
            continue
        for alias in t.get("aliases", []):
            if alias.lower() in text_l:
                matched.append(t)
                break
    return matched


# ============================================================
# 产品类型查询
# ============================================================

def detect_products(text: str) -> list[dict]:
    """按 aliases 关键词扫描，识别条款涉及的产品类型。"""
    text_l = (text or "").lower()
    detected = []
    for p in get_products():
        for alias in p.get("aliases", []):
            if alias.lower() in text_l:
                detected.append(p)
                break
    return detected


def get_product(name: str) -> dict | None:
    """按名称 / 别名查产品类型，返回完整条目（未命中返回 None）。"""
    n = (name or "").strip().lower()
    if not n:
        return None
    for p in get_products():
        names = [p.get("name", "").lower()] + [a.lower() for a in p.get("aliases", [])]
        if n in names:
            return p
    return None


# ============================================================
# 风险模式匹配
# ============================================================

def match_risks(text: str, product_type: str | None = None) -> list[dict]:
    """对条款文本匹配风险模式（keywords 子串 + regex 精匹配）。"""
    text = text or ""
    matched = []
    for rp in get_risk_patterns():
        if product_type and product_type not in rp.get("applicable_product_types", []):
            continue

        hit = any(kw in text for kw in rp.get("keywords", []))
        if not hit and rp.get("regex"):
            try:
                if re.search(rp["regex"], text):
                    hit = True
            except re.error:
                pass

        if hit:
            matched.append({
                "id": rp["id"],
                "name": rp["name"],
                "risk_level": rp["risk_level"],
                "explanation": rp["explanation"],
            })
    return matched


# ============================================================
# 聚合事实检索（pipeline 主路径入口）
# ============================================================

def get_grounding_block(text: str) -> dict:
    """
    对一段金融条款做确定性事实检索，一次返回：
      - detected_product_types: 命中的产品类型名称列表
      - product: 首个命中产品类型的完整条目（可能为 None）
      - terms: 命中的术语词典条目
      - risk_patterns: 命中的风险模式（按产品类型过滤）
    纯确定性匹配，不调用 LLM。
    """
    text = text or ""
    products = detect_products(text)
    product = products[0] if products else None
    terms = detect_terms_in_text(text)
    product_type_id = product.get("id") if product else None
    risk_patterns = match_risks(text, product_type=product_type_id)

    return {
        "detected_product_types": [p["name"] for p in products],
        "product": product,
        "terms": terms,
        "risk_patterns": risk_patterns,
    }

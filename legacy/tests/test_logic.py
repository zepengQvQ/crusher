"""快速验证 legacy 工具函数（对照用，不进 make test）。"""
import json
import os
import sys
from pathlib import Path

_LEGACY = Path(__file__).resolve().parents[1]
_ROOT = _LEGACY.parent
sys.path.insert(0, str(_LEGACY))

from backend.llm_client import LLMClient

test1 = 'Some text\n```json\n{"a": 1, "b": "hello"}\n```\nmore text'
r1 = LLMClient._parse_json(test1)
assert r1 == {"a": 1, "b": "hello"}, f"Failed: {r1}"
print("JSON parse (code block): OK")

test2 = '[{"snippet": "test", "risk_level": "高"}]'
r2 = LLMClient._parse_json(test2)
assert isinstance(r2, list) and len(r2) == 1
print("JSON parse (array): OK")

test3 = "Here is the chart:\n```mermaid\nflowchart TD\n    A-->B\n```"
r3 = LLMClient.extract_mermaid(test3)
assert "flowchart TD" in r3 and "A-->B" in r3
print("Mermaid extract: OK")

with open(_ROOT / "data" / "examples.json", "r", encoding="utf-8") as f:
    examples = json.load(f)
assert len(examples) == 5
print(f"Examples loaded: {len(examples)} cases OK")

from backend.config import load_config, PROVIDER_DEFAULTS

cfg = load_config()
assert cfg.provider in PROVIDER_DEFAULTS
print(f"Config load OK (provider={cfg.provider}, model={cfg.model})")

from backend.prompts import STAGE1_USER_PROMPT, STAGE2_USER_PROMPT, STAGE3_USER_PROMPT

p1 = STAGE1_USER_PROMPT.replace("{knowledge_context}", "（测试事实）").replace("{raw_text}", "测试条款")
assert "测试条款" in p1 and "（测试事实）" in p1
p3 = STAGE3_USER_PROMPT.replace("{matched_risk_context}", "（测试风险）").replace("{raw_text}", "测试条款")
assert "测试条款" in p3
print("Prompt replace OK")
print("All legacy logic checks passed.")

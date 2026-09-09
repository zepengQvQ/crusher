#!/usr/bin/env python3
"""从 FastAPI 导出 OpenAPI，并生成前端类型文件。

生成物：
- contracts/openapi.json
- frontend-h5/src/api/generated-types.js  （枚举常量 + 主要 DTO 的 JSDoc）
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

try:
    from app.main import create_app
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "无法导入 app。请先 pip install -e backend-python/. "
        "或 export PYTHONPATH=backend-python"
    ) from exc

# 前端最常用的 schema，优先生成完整 typedef
PRIORITY_SCHEMAS = [
    "CreateAnalysisRequest",
    "CreateAnalysisResponse",
    "TaskResponse",
    "AnalysisReport",
    "Finding",
    "Evidence",
    "KeyParameter",
    "ProductCandidate",
    "ProductRiskGrade",
    "PlainLanguage",
    "MissingDisclosure",
    "GeneralReference",
    "StageInfo",
    "ApiErrorDetail",
    "ApiErrorResponse",
    "DualAnalysisRequest",
    "DualAnalysisReport",
    "ClaimComparison",
    "Claim",
    "SourceDocument",
    "EvidenceRef",
    "ExtractedDocument",
    "PageExtractResult",
    "FollowUpRequest",
    "EvidenceAnswer",
    "CalculateScenarioRequest",
    "CalculationResult",
    "ExtractedDecimalField",
]


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _js_type(prop: dict[str, Any], schemas: dict[str, Any]) -> str:
    if "$ref" in prop:
        name = _ref_name(prop["$ref"])
        target = schemas.get(name) or {}
        if "enum" in target:
            return f"{name}Value"
        return name
    if "anyOf" in prop:
        parts = [_js_type(p, schemas) for p in prop["anyOf"]]
        # 常见 Optional
        parts = [p for p in parts if p != "null"]
        if not parts:
            return "null"
        return "|".join(parts) if len(parts) > 1 else parts[0]
    if "enum" in prop:
        return "|".join(json.dumps(v, ensure_ascii=False) for v in prop["enum"])
    t = prop.get("type")
    if t == "array":
        items = prop.get("items") or {}
        return f"Array<{_js_type(items, schemas)}>"
    if t == "string":
        return "string"
    if t == "integer":
        return "number"
    if t == "number":
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "object":
        return "Object"
    if t == "null":
        return "null"
    return "any"


def _emit_enum(name: str, schema: dict[str, Any]) -> list[str]:
    values = schema.get("enum") or []
    union = "|".join(json.dumps(v, ensure_ascii=False) for v in values) or "string"
    lines = [
        "/**",
        f" * @typedef {{{union}}} {name}Value",
        " */",
        "",
        f"export const {name} = Object.freeze({{",
    ]
    for v in values:
        key = re.sub(r"[^a-zA-Z0-9_]", "_", str(v))
        if key and key[0].isdigit():
            key = f"_{key}"
        lines.append(f"  {key}: {json.dumps(v, ensure_ascii=False)},")
    lines.append("})")
    lines.append("")
    return lines


def _emit_typedef(name: str, schema: dict[str, Any], schemas: dict[str, Any]) -> list[str]:
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    lines = ["/**", f" * @typedef {{Object}} {name}"]
    for pname, pschema in props.items():
        typ = _js_type(pschema, schemas)
        if pname in required:
            lines.append(f" * @property {{{typ}}} {pname}")
        else:
            lines.append(f" * @property {{{typ}}} [{pname}]")
    lines.append(" */")
    lines.append("")
    return lines


def _max_input_chars(components: dict[str, Any]) -> int:
    try:
        text_schema = components["CreateAnalysisRequest"]["properties"]["text"]
        return int(text_schema["maxLength"])
    except (KeyError, TypeError, ValueError):
        return 8000


def main() -> None:
    app = create_app()
    schema = app.openapi()
    contracts = ROOT / "contracts"
    contracts.mkdir(exist_ok=True)
    openapi_path = contracts / "openapi.json"
    openapi_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    components = schema.get("components", {}).get("schemas", {})
    names = sorted(components.keys())
    max_chars = _max_input_chars(components)

    lines: list[str] = [
        "/**",
        " * 由 scripts/export_openapi.py 自动生成，勿手改。",
        " * 与 contracts/openapi.json / 后端 Pydantic 保持一致。",
        " * 更新命令：make export-openapi",
        " */",
        "",
        f"export const SCHEMA_NAMES = {json.dumps(names, ensure_ascii=False)}",
        "",
        f"export const MAX_INPUT_CHARS = {max_chars}",
        "",
        "export const DISCLAIMER = '本 Demo 不进行用户适当性评估，不构成投资建议。'",
        "",
    ]

    # 全部 enum（含 Value typedef）
    for name in names:
        sch = components[name]
        if "enum" in sch:
            lines.extend(_emit_enum(name, sch))

    # 优先 object typedef
    emitted: set[str] = set()
    for name in PRIORITY_SCHEMAS:
        if name in components and "properties" in components[name]:
            lines.extend(_emit_typedef(name, components[name], components))
            emitted.add(name)
    for name in names:
        if name in emitted:
            continue
        sch = components[name]
        if "properties" in sch and "enum" not in sch:
            lines.extend(_emit_typedef(name, sch, components))

    out = ROOT / "frontend-h5" / "src" / "api" / "generated-types.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {openapi_path}")
    print(f"wrote {out} ({len(names)} schemas)")


if __name__ == "__main__":
    main()

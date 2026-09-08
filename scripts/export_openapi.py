#!/usr/bin/env python3
"""从 FastAPI 导出 OpenAPI，并生成前端类型文件。

生成物：
- contracts/openapi.json
- frontend-h5/src/api/generated-types.js  （枚举常量 + 主要 DTO 的 JSDoc）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.main import create_app  # noqa: E402

# 前端最常用的 schema，优先生成完整 typedef
PRIORITY_SCHEMAS = [
    "TaskResponse",
    "CreateAnalysisResponse",
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
]


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _js_type(prop: dict[str, Any], schemas: dict[str, Any]) -> str:
    if "$ref" in prop:
        return _ref_name(prop["$ref"])
    if "anyOf" in prop:
        parts = [_js_type(p, schemas) for p in prop["anyOf"]]
        # 常见 Optional
        parts = [p for p in parts if p != "null"]
        if not parts:
            return "null"
        return "|".join(parts) if len(parts) > 1 else parts[0]
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
    lines = [f"export const {name} = Object.freeze({{"]
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
    lines = ["/**", f" * @typedef {name}"]
    for pname, pschema in props.items():
        opt = "" if pname in required else " [optional]"
        lines.append(f" * @property {{{_js_type(pschema, schemas)}}}{opt} {pname}")
    lines.append(" */")
    lines.append("")
    return lines


def main() -> None:
    app = create_app()
    schema = app.openapi()
    contracts = ROOT / "contracts"
    contracts.mkdir(exist_ok=True)
    openapi_path = contracts / "openapi.json"
    openapi_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    components = schema.get("components", {}).get("schemas", {})
    names = sorted(components.keys())

    lines: list[str] = [
        "/**",
        " * 由 scripts/export_openapi.py 自动生成，勿手改。",
        " * 与 contracts/openapi.json / 后端 Pydantic 保持一致。",
        " * 更新命令：make export-openapi",
        " */",
        "",
        f"export const SCHEMA_NAMES = {json.dumps(names, ensure_ascii=False)}",
        "",
        "export const DISCLAIMER = '本 Demo 不进行用户适当性评估，不构成投资建议。'",
        "",
    ]

    # 全部 enum
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

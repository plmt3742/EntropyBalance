"""零依赖的 JSON Schema 子集校验器（B-04 专用）。

为什么不用 jsonschema 库：仓库规矩是不引新依赖（AGENTS.md），而本轮的验收
只需要"这份实例合不合 schema"这一个问题。所以我们自己实现够用的子集，
并在 README 里写明不支持哪些关键字——不装成通用校验器。

支持：$ref(本地 #/$defs/*)、type、enum、const、required、properties、
additionalProperties、items、minItems、maxItems、minLength、maxLength、
pattern、anyOf、oneOf、allOf、if/then/else。

不支持：format、$dynamicRef、unevaluatedProperties、dependentSchemas。
遇到不认识的关键字直接忽略（不报错），这是刻意的：宁可漏查，不误报。

用法：
    from b04_schema_lite import load_schema, check
    schema = load_schema(Path("packages/shared/extraction.schema.json"))
    errors = check(instance, schema["$defs"]["Assertion"], schema)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
    "null": type(None),
}


def load_schema(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _type_ok(value: Any, expected: Any) -> bool:
    names = expected if isinstance(expected, list) else [expected]
    for name in names:
        py = _TYPES.get(name)
        if py is None:
            continue
        if name in {"integer", "number"} and isinstance(value, bool):
            continue  # JSON 里 true 不是数字
        if isinstance(value, py):
            return True
    return False


def _resolve(ref: str, root: dict) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"只支持本地 $ref：{ref}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def check(value: Any, schema: dict, root: dict, path: str = "$") -> list[str]:
    """返回错误列表；空列表表示通过。"""
    errors: list[str] = []

    if "$ref" in schema:
        merged = dict(_resolve(schema["$ref"], root))
        merged.update({k: v for k, v in schema.items() if k != "$ref"})
        return check(value, merged, root, path)

    if "type" in schema and not _type_ok(value, schema["type"]):
        errors.append(f"{path}: 类型应为 {schema['type']}，实际 {type(value).__name__}")
        return errors  # 类型不对，后续检查没有意义

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: 应等于 {schema['const']!r}，实际 {value!r}")

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: 取值 {value!r} 不在枚举 {schema['enum']} 内")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: 小于最小值 {schema['minimum']}（实际 {value}）")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: 大于最大值 {schema['maximum']}（实际 {value}）")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: 长度至少 {schema['minLength']}，实际 {len(value)}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: 长度至多 {schema['maxLength']}，实际 {len(value)}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: 不匹配 {schema['pattern']}：{value!r}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: 至少 {schema['minItems']} 项，实际 {len(value)}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: 至多 {schema['maxItems']} 项，实际 {len(value)}")
        if "items" in schema:
            for i, item in enumerate(value):
                errors.extend(check(item, schema["items"], root, f"{path}[{i}]"))

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: 缺必填字段 {key}")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in value:
                errors.extend(check(value[key], sub, root, f"{path}.{key}"))
        extra = schema.get("additionalProperties", True)
        if extra is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}: 多出未定义字段 {key}")
        elif isinstance(extra, dict):
            for key in value:
                if key not in props:
                    errors.extend(check(value[key], extra, root, f"{path}.{key}"))

    if "allOf" in schema:
        for sub in schema["allOf"]:
            errors.extend(check(value, sub, root, path))

    if "anyOf" in schema:
        branches = [check(value, sub, root, path) for sub in schema["anyOf"]]
        if all(branches):
            errors.append(f"{path}: anyOf 全部失败 -> {branches}")

    if "oneOf" in schema:
        hits = [sub for sub in schema["oneOf"] if not check(value, sub, root, path)]
        if len(hits) != 1:
            errors.append(f"{path}: oneOf 应恰好命中 1 个分支，实际 {len(hits)}")

    if "if" in schema:
        matched = not check(value, schema["if"], root, path)
        branch = schema.get("then") if matched else schema.get("else")
        if branch is not None:
            errors.extend(check(value, branch, root, path))

    return errors

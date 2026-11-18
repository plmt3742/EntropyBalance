#!/usr/bin/env python3
"""B-04 抽样检查：验证 schema 能表达 10 条边界案例，并守住"合成数据不得冒充真实记录"。

用途
----
B-04 的验收标准之一：10 条"必须能表达"的边界案例全部通过，不需要临时加字段。
本脚本把这条标准变成可复现的检查，不依赖第三方库（不引入新依赖，AGENTS.md）。

用法
----
    python scripts/check-b04-samples.py
    python scripts/check-b04-samples.py --file data/samples/B-04-boundary-cases.jsonl
    python scripts/check-b04-samples.py --file data/samples/B-04-real-records.jsonl  # 真实记录到位后

退出码：0 = 全部通过；1 = 有失败项。

注意
----
本脚本只检查"断言能否被 schema 表达"，不检查标注质量。
标注一致性（三人 κ）必须由真人完成，见 findings 文档 §9。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLES = ROOT / "data" / "samples" / "B-04-boundary-cases.jsonl"
SCHEMA_PATH = ROOT / "packages" / "shared" / "extraction.schema.json"

ENUMS = {
    "type": {"decision", "task", "commitment", "status_update", "discussion"},
    "polarity": {"affirmative", "negated"},
    "modality": {"asserted", "hypothetical", "quoted", "joking", "reported"},
    "task_state": {"proposed", "active", "done", "cancelled", None},
    "decision_state": {"proposed", "ratified", "reversed", "superseded", None},
    "role": {"owner", "contributor", "approver", "backup", "mentioned"},
    "actor_status": {"known", "ambiguous", "missing", "group"},
    "time_kind": {"absolute", "relative", "event_ref", "fuzzy", "none"},
    "dep_kind": {"precedence", "resource", "approval", "information"},
    "dep_strength": {"hard", "soft"},
}


def owners(sample: dict) -> list[dict]:
    return [a for a in sample["expected"].get("actors", []) if a.get("role") == "owner"]


# --- must_hold 规则：每条都是对 schema 表达能力的断言 -------------------------


def rule_decision_has_no_owner(s: dict) -> None:
    assert not owners(s), "决定不应挂 owner：决定的落点是 approver，任务才有 owner"


def rule_hypothetical_not_in_graph(s: dict) -> None:
    e = s["expected"]
    if e.get("modality") == "hypothetical":
        assert e.get("graph_eligible") is False, "假设句不得入图"


def rule_negated_not_in_graph(s: dict) -> None:
    e = s["expected"]
    if e.get("polarity") == "negated":
        assert e.get("graph_eligible") is False, "否定断言不得入图"


def rule_joking_not_in_graph(s: dict) -> None:
    e = s["expected"]
    if e.get("modality") == "joking":
        assert e.get("graph_eligible") is False, "玩笑不得入图"


def rule_single_owner_at_most(s: dict) -> None:
    active = [o for o in owners(s) if o.get("status") in {"known", "ambiguous"}]
    assert len(active) <= 1, "一个任务最多一个 owner 位置；多候选应放进同一个 ambiguous actor"


def rule_owner_missing_kept(s: dict) -> None:
    miss = [o for o in owners(s) if o.get("status") == "missing"]
    assert miss, "本用例应保留无责任人的断言"
    assert s["expected"].get("type") in ENUMS["type"], "保留的断言必须有合法类型"


def rule_multi_candidate_not_forced(s: dict) -> None:
    amb = [o for o in owners(s) if o.get("status") == "ambiguous"]
    assert amb, "本用例应是多候选归属"
    assert len(amb[0].get("persons", [])) >= 2, "多候选至少并列两个人，不强迫选一个"


def rule_group_owner_not_person(s: dict) -> None:
    grp = [o for o in owners(s) if o.get("status") == "group"]
    assert grp, "本用例应是群体归属"
    assert grp[0].get("persons") == [], "『大家』不得映射到具体人"
    assert grp[0].get("group_scope") in {"team", "present", "unspecified"}, "群体必须有作用域"


def rule_commitment_owner_present(s: dict) -> None:
    e = s["expected"]
    if e.get("type") == "commitment" and e.get("modality") == "asserted":
        assert any(o.get("status") == "known" for o in owners(s)), "承诺必须有明确负责人"


def rule_dependency_direction_single(s: dict) -> None:
    for d in s["expected"].get("dependencies", []):
        assert d.get("direction", "depends_on") == "depends_on", "方向只允许 depends_on 一种写法"
        assert d.get("kind") in ENUMS["dep_kind"], f"未知依赖类型：{d.get('kind')}"
        assert d.get("strength") in ENUMS["dep_strength"], f"未知强弱：{d.get('strength')}"


def rule_relative_time_needs_anchor(s: dict) -> None:
    t = s["expected"].get("time", {})
    if t.get("kind") in {"relative", "event_ref"}:
        assert t.get("raw"), "相对时间必须保留原文表达"
        assert s["record"].get("captured_at") or t.get("anchor"), "相对时间必须有锚点才能归一"


def rule_time_unresolved_reason(s: dict) -> None:
    t = s["expected"].get("time", {})
    if t.get("kind") == "fuzzy":
        assert t.get("unresolved_reason"), "模糊时间必须给出未归一理由，不许猜日期"


def rule_cycle_flagged(s: dict) -> None:
    e = s["expected"]
    assert e.get("review_reason") == "dependency_cycle", "成环必须打 dependency_cycle 标记"
    assert len(e.get("dependencies", [])) >= 2, "环至少需要两条依赖边"


def rule_quoted_or_unresolved_person_flagged(s: dict) -> None:
    e = s["expected"]
    unresolved = any(a.get("identity_unresolved") for a in e.get("actors", []))
    assert e.get("modality") == "quoted" or unresolved, "本用例应涉及引用或指代不明"
    assert e.get("review_reason") is not None, "引用/指代不明必须进人工确认队列"


def rule_cross_record_merge_key(s: dict) -> None:
    key = s["expected"].get("merge_key")
    assert isinstance(key, str) and key, "跨记录同一任务必须给出 merge_key 供 R-06 聚类"


def rule_mixed_language_terms_kept(s: dict) -> None:
    import re

    assert re.search(r"[A-Za-z]{2,}", s["text"]), "本用例应是中英混用"
    assert s["expected"].get("type") in ENUMS["type"], "混用语料仍必须产出合法断言"


def rule_discussion_not_ratified(s: dict) -> None:
    if s["expected"].get("type") == "discussion":
        assert s["expected"].get("decision_state") != "ratified", "讨论不能标成已定决定"


def check_origin(s: dict) -> list[str]:
    """来源守卫：合成数据不许出现在"真实记录"的位置上。

    约定：
      kind=edge_case  -> origin 必须是 constructed（构造的极端案例）
      kind=sample     -> origin 必须是 redacted_real（真实记录，已脱敏）
    没有 origin 字段一律判失败——"来源不明"本身就是要拦的东西。
    """
    origin = s.get("origin")
    kind = s.get("kind", "sample")
    if origin is None:
        return [f"{s['sample_id']}: 缺 origin 字段（constructed / redacted_real 必须显式写）"]
    want = "constructed" if kind == "edge_case" else "redacted_real"
    if origin != want:
        return [f"{s['sample_id']}: kind={kind} 时 origin 必须是 {want}，实际是 {origin}"]
    if origin == "redacted_real":
        # 真实记录必须能追溯到来源记录号，否则无法复核
        rid = s.get("record", {}).get("record_id", "")
        if not rid:
            return [f"{s['sample_id']}: 真实记录必须有 record_id 以便追溯"]
    return []


RULES = {
    "decision_has_no_owner": rule_decision_has_no_owner,
    "hypothetical_not_in_graph": rule_hypothetical_not_in_graph,
    "negated_not_in_graph": rule_negated_not_in_graph,
    "joking_not_in_graph": rule_joking_not_in_graph,
    "single_owner_at_most": rule_single_owner_at_most,
    "owner_missing_kept": rule_owner_missing_kept,
    "multi_candidate_not_forced": rule_multi_candidate_not_forced,
    "group_owner_not_person": rule_group_owner_not_person,
    "commitment_owner_present": rule_commitment_owner_present,
    "dependency_direction_single": rule_dependency_direction_single,
    "relative_time_needs_anchor": rule_relative_time_needs_anchor,
    "time_unresolved_reason": rule_time_unresolved_reason,
    "cycle_flagged": rule_cycle_flagged,
    "quoted_or_unresolved_person_flagged": rule_quoted_or_unresolved_person_flagged,
    "cross_record_merge_key": rule_cross_record_merge_key,
    "mixed_language_terms_kept": rule_mixed_language_terms_kept,
    "discussion_not_ratified": rule_discussion_not_ratified,
}


def check_enums(sample: dict) -> list[str]:
    """expected 里的取值必须落在 schema 允许的枚举内。"""
    errs: list[str] = []
    e = sample["expected"]
    for key, allowed in (
        ("type", ENUMS["type"]),
        ("polarity", ENUMS["polarity"]),
        ("modality", ENUMS["modality"]),
        ("task_state", ENUMS["task_state"]),
        ("decision_state", ENUMS["decision_state"]),
    ):
        if key in e and e[key] not in allowed:
            errs.append(f"{key}={e[key]!r} 不在枚举内")
    for a in e.get("actors", []):
        if a.get("role") not in ENUMS["role"]:
            errs.append(f"role={a.get('role')!r} 不在枚举内")
        if a.get("status") not in ENUMS["actor_status"]:
            errs.append(f"actor.status={a.get('status')!r} 不在枚举内")
    t = e.get("time", {})
    if t.get("kind") not in ENUMS["time_kind"]:
        errs.append(f"time.kind={t.get('kind')!r} 不在枚举内")
    return errs


def _enum_values(node: object):
    """递归收集 schema 中所有 enum 的取值。"""
    if isinstance(node, dict):
        for key, val in node.items():
            if key == "enum" and isinstance(val, list):
                for item in val:
                    yield item
            else:
                yield from _enum_values(val)
    elif isinstance(node, list):
        for item in node:
            yield from _enum_values(item)


def check_schema_file() -> list[str]:
    """schema 文件必须能被解析，且不含逃避字段。"""
    errs: list[str] = []
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"schema 文件不存在：{SCHEMA_PATH}"]
    except json.JSONDecodeError as exc:
        return [f"schema 不是合法 JSON：{exc}"]
    banned = {"其他", "其它", "杂项", "misc", "other", "others", "unknown"}
    for value in _enum_values(schema):
        if isinstance(value, str) and value.strip().lower() in banned:
            errs.append(f"schema 的 enum 里出现逃避式取值：{value}")
    if "unicode_code_point" not in json.dumps(schema, ensure_ascii=False):
        errs.append("schema 必须声明证据偏移单位")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=DEFAULT_SAMPLES)
    args = ap.parse_args()

    errs = check_schema_file()
    if errs:
        for e in errs:
            print(f"[FAIL] schema: {e}")
        return 1

    lines = [ln for ln in args.file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    samples = [json.loads(ln) for ln in lines]

    rows: list[tuple[str, str, str]] = []
    failures = 0
    for s in samples:
        sid, kind = s["sample_id"], s.get("kind", "sample")
        problems = check_enums(s) + check_origin(s)
        for name in s["expected"].get("must_hold", []):
            fn = RULES.get(name)
            if fn is None:
                problems.append(f"未知规则 {name}")
                continue
            try:
                fn(s)
            except AssertionError as exc:
                problems.append(f"{name}: {exc}")
        if problems:
            failures += len(problems)
            rows.append((sid, kind, "FAIL " + "; ".join(problems)))
        else:
            rows.append((sid, kind, "PASS"))

    width = max(len(r[0]) for r in rows) + 2
    for sid, kind, verdict in rows:
        print(f"{sid:<{width}}{kind:<11}{verdict}")

    edge = [r for r in rows if r[1] == "edge_case"]
    edge_pass = [r for r in edge if r[2] == "PASS"]
    real = [r for r in rows if r[1] != "edge_case"]
    print()
    print(f"真实记录 {len(real)} 条（本轮未标注），边界案例 {len(edge)} 条")
    print(f"边界案例通过 {len(edge_pass)}/{len(edge)}")
    if failures:
        print(f"失败项 {failures} 个")
        return 1
    if not real:
        print("注意：当前没有真实记录样本，仅边界案例通过——不构成验收所需的「20 条真实记录」")
    print("全部通过：schema 能表达全部用例，无需临时加字段")
    return 0


if __name__ == "__main__":
    sys.exit(main())

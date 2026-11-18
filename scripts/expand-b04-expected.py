"""把样本里的"简写期望"翻译成完整断言，并用 schema 校验。

分工（v0.1.1 决定）：
- 标注人只写简写：`{"type": "task", "actors": [{"role": "owner", "status": "known", "persons": ["P02"]}]}`
  因为 20 条手写嵌套 JSON 会写错括号，成本远高于收益。
- 机器要的是完整断言：persons 是对象数组、review 是对象、time 是对象。
- 这个脚本就是那层翻译。翻译规则集中在一处，改规则只改这里。

约定（v0.1.1）：
1. 相对时间锚点 = 记录的 captured_at（自然周：周一起，见 docs 的 §时间归一）。
2. 置信度按归属状态给：known=0.9 / ambiguous=0.6 / 指代不明或缺失=0.3。
3. 需要人工确认 ⇔ 写了 review_reason。没写就是"机器可以自己过"。

用法：
    python scripts/expand-b04-expected.py                # 打印翻译结果
    python scripts/expand-b04-expected.py --validate     # 同时用 schema 校验
    python scripts/expand-b04-expected.py --out out.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from b04_schema_lite import check, load_schema  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLES = ROOT / "data" / "samples" / "B-04-boundary-cases.jsonl"
SCHEMA_PATH = ROOT / "packages" / "shared" / "extraction.schema.json"

CONFIDENCE_BY_STATUS = {"known": 0.9, "ambiguous": 0.6, "missing": 0.3, "group": 0.3}


def _persons(actor: dict) -> list[dict]:
    conf = 0.3 if actor.get("identity_unresolved") else CONFIDENCE_BY_STATUS.get(actor.get("status"), 0.3)
    return [{"person_id": pid, "confidence": conf} for pid in actor.get("persons", [])]


def _actor(actor: dict) -> dict:
    out: dict = {
        "role": actor["role"],
        "status": actor["status"],
        "persons": _persons(actor),
    }
    if actor.get("group_scope") is not None:
        out["group_scope"] = actor["group_scope"]
    if actor.get("source") is not None:
        out["source"] = actor["source"]
    if actor.get("identity_unresolved"):
        out["note"] = "身份未核实（转述或指代不明）"
    return out


def _time(t: dict | None, record: dict) -> dict:
    t = t or {}
    kind = t.get("kind", "none")
    out: dict = {"raw": t.get("raw", ""), "kind": kind}
    if t.get("start") is not None:
        out["start"] = t["start"]
    if t.get("end") is not None:
        out["end"] = t["end"]
    if t.get("granularity") is not None:
        out["granularity"] = t["granularity"]
    if kind in {"relative", "event_ref"}:
        # 锚点取记录的采集时间：没有它，"下周""周五"永远算不出来
        out["anchor"] = t.get("anchor") or record.get("captured_at")
    if t.get("unresolved_reason") is not None:
        out["unresolved_reason"] = t["unresolved_reason"]
    return out


def _deps(deps: list[dict] | None, evidence: dict) -> list[dict] | None:
    if not deps:
        return None
    out = []
    for d in deps:
        item: dict = {"direction": "depends_on", "kind": d["kind"], "strength": d["strength"]}
        if d.get("target_task_id") is not None:
            item["target_task_id"] = d["target_task_id"]
        if d.get("target_label") is not None:
            item["target_label"] = d["target_label"]
        item["evidence"] = evidence
        out.append(item)
    return out


def expand(sample: dict, index: int) -> dict:
    e = sample["expected"]
    record = sample["record"]
    text = sample["text"]
    ev = e.get("evidence") or {"span_start": 0, "span_end": len(text), "quote": text}
    evidence = {
        "record_id": record["record_id"],
        "span_start": ev["span_start"],
        "span_end": ev["span_end"],
        "quote": ev["quote"],
    }
    reason = e.get("review_reason")
    assertion: dict = {
        "assertion_id": e.get("assertion_id") or f"A-{index:04d}",
        "record_id": record["record_id"],
        "type": e["type"],
        "statement": text,
        "evidence": evidence,
        "polarity": e.get("polarity", "affirmative"),
        "modality": e.get("modality", "asserted"),
        "graph_eligible": e.get("graph_eligible", True),
        "actors": [_actor(a) for a in e.get("actors", [])],
        "time": _time(e.get("time"), record),
        "confidence": e.get("confidence", 0.9 if any(a.get("status") == "known" for a in e.get("actors", [])) else 0.6),
        "review": {"needs_human": reason is not None, "reason": reason},
    }
    if e.get("task_state") is not None:
        assertion["task_state"] = e["task_state"]
    if e.get("decision_state") is not None:
        assertion["decision_state"] = e["decision_state"]
    if e.get("merge_key") is not None:
        assertion["merge_key"] = e["merge_key"]
    deps = _deps(e.get("dependencies"), evidence)
    if deps:
        assertion["dependencies"] = deps
    return assertion


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=DEFAULT_SAMPLES)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--validate", action="store_true")
    args = ap.parse_args()

    schema = load_schema(SCHEMA_PATH)
    rows = [json.loads(line) for line in args.file.read_text(encoding="utf-8").splitlines() if line.strip()]

    assertions: list[dict] = []
    failures = 0
    for i, sample in enumerate(rows, start=1):
        a = expand(sample, i)
        assertions.append(a)
        if args.validate:
            errs = check(a, schema["$defs"]["Assertion"], schema)
            mark = "PASS" if not errs else "FAIL"
            print(f"[{mark}] {sample['sample_id']} -> {a['assertion_id']}")
            for err in errs:
                print(f"       {err}")
            if errs:
                failures += 1

    payload = "\n".join(json.dumps(a, ensure_ascii=False) for a in assertions) + "\n"
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
        print(f"已写出 {len(assertions)} 条断言 -> {args.out}")
    elif not args.validate:
        print(payload, end="")

    if args.validate:
        print(f"\n合计 {len(assertions)} 条，失败 {failures} 条")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

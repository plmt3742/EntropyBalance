#!/usr/bin/env python3
"""B-06 冲突提示（对应任务单 2.4「至少有一个明确的冲突提示」）。

什么叫冲突：**同一份数据里，有两条信息指向不同结论，且系统自己无法判断谁对。**
不做这件事的后果是：合并悄悄做完了，没人知道有争议——这比不做还危险。

三类冲突（每条都给出给人看的中文提示，而不是只报一个错误码）：

  C1 一个称呼对应多个人      `队长` 在本记录里能指 P01 或 P02  → 提示「请指认是哪一个」
  C2 同一称呼在不同记录里指了不同的人  跨记录的语义漂移      → 提示「这个称呼不是全局唯一的」
  C3 人工合并与在场事实矛盾   合并目标在本记录里没出现过     → 提示「这条合并可能指错了人」

输出：data/samples/B-06-conflicts.jsonl，一行一个冲突。
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "data" / "samples"
CANDS = S / "B-06-alias-candidates.jsonl"
LOG = S / "B-06-merge-log.jsonl"
OUT = S / "B-06-conflicts.jsonl"
TEXTS = S / "B-04-real-records.jsonl"

AUTHOR_RE = re.compile(r"^(P\d{2})\s*[:：]")
PID_RE = re.compile(r"(?<![A-Za-z0-9])P\d{2}(?!\d)")


def load(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def persons_in(text: str):
    ids = {m.group(0) for m in PID_RE.finditer(text)}
    for line in text.split("\n"):
        a = AUTHOR_RE.match(line)
        if a:
            ids.add(a.group(1))
    return ids


def main() -> int:
    argv = sys.argv[1:]
    for flag, name in (("--cands", "CANDS"), ("--log", "LOG"), ("--out", "OUT"), ("--texts", "TEXTS")):
        if flag in argv:
            globals()[name] = Path(argv[argv.index(flag) + 1])
    cands = load(CANDS)
    log = load(LOG)
    texts = {r["record"]["record_id"]: r["text"] for r in load(TEXTS)}
    out = []

    # C1：一个称呼对应多个人
    for c in cands:
        if c["status"] == "ambiguous" and len(c["targets"]) >= 2:
            out.append({
                "conflict_id": f"C1-{c['mention_id']}",
                "type": "C1",
                "severity": "需要人指认",
                "mention_ids": [c["mention_id"]],
                "scope": f"{c['record_id']}#{c['message_index']}",
                "message": f"「{c['surface']}」在本记录里可能指 {len(c['targets'])} 个人（{','.join(c['targets'])}）。"
                           f"系统不替你选，请指认是哪一个，或标「无法确定」。",
                "suggestion": "在候选队列里点选一个人；或标 ambiguous 保留争议",
            })

    # C2：同一称呼在不同记录里被判成不同的人
    by_surface = defaultdict(lambda: defaultdict(set))
    for c in cands:
        if c["status"] == "resolved" and c["kind"] in ("role", "department"):
            for t in c["targets"]:
                by_surface[c["surface"]][t].add(c["record_id"])
    for surface, tmap in by_surface.items():
        if len(tmap) >= 2:
            detail = "；".join(f"{t}（{','.join(sorted(rs))}）" for t, rs in tmap.items())
            mids = [c["mention_id"] for c in cands if c["surface"] == surface and c["status"] == "resolved"]
            out.append({
                "conflict_id": f"C2-{surface}", "type": "C2", "severity": "提示",
                "mention_ids": mids, "scope": surface,
                "message": f"「{surface}」在不同记录里被判定成不同对象：{detail}。"
                           f"说明这个称呼不是全局唯一的，跨记录合并必须带上下文。",
                "suggestion": "在同一任务/同一时间窗内才允许跨记录合并",
            })

    # C3：人工合并的目标不在该记录里出现过
    for e in log:
        if e["action"] not in ("merge", "split") or e.get("undo_of"):
            continue
        c = next((x for x in cands if x["mention_id"] == e.get("mention_id")), None)
        if not c:
            continue
        tgt = e.get("to", "")
        if tgt.startswith("P") and tgt not in persons_in(texts.get(c["record_id"], "")):
            out.append({
                "conflict_id": f"C3-{e['op_id']}", "type": "C3", "severity": "可能是错合并",
                "mention_ids": [c["mention_id"]], "scope": f"{c['record_id']}#{c['message_index']}",
                "message": f"{e['op_id']} 把「{c['surface']}」并到了 {tgt}，但 {tgt} 没有出现在 {c['record_id']} 里。"
                           f"要么这条记录提到了外部的人，要么并错了。",
                "suggestion": f"复核 {e['op_id']}；如错，python scripts/b06_merge.py undo {e['op_id']}",
            })

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
    for t in ("C1", "C2", "C3"):
        n = sum(1 for r in out if r["type"] == t)
        print(f"{t}: {n} 条")
    print("合计", len(out), "条冲突 ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""B-06 合并记录与撤销（对应任务单 2.2-4 / 2.4「合并可撤销、可解释」）。

为什么不改候选文件：候选是「机器判断」，合并是「人的决定」。两者混在一个文件里，
就再也分不清哪条是算法结论、哪条是谁在什么时候拍的板，撤销也无从谈起。

做法：**追加式日志 + 重放**。
  - `data/samples/B-06-merge-log.jsonl` 一行一个操作，永不修改、永不删除；
  - 当前状态 = 候选的原始判定 + 按时间重放日志（撤销就是追加一条 `undo`，把目标操作作废）；
  - 随时可以重放，结果必须是幂等的——这是「可撤销」的可验证形式。

操作类型：
  merge   把一条提及并到某个人（例：`老师` → P18）
  split   把一条提及从原目标拆出来，重新指定（拆分同一人被误合并的情况）
  undo    作废某个 op_id（不是删除它）

用法：
  python scripts/b06_merge.py list
  python scripts/b06_merge.py show M0123
  python scripts/b06_merge.py merge M0123 P18 --rule R2 --evidence "P05: 要叫P18老师" --by 0002
  python scripts/b06_merge.py split M0123 EXT-老师A --by 0002 --note "其实指田姐"
  python scripts/b06_merge.py undo OP-0001 --by 0002
  python scripts/b06_merge.py replay          # 打印重放后的最终状态（可 diff）
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "data" / "samples"
CANDS = S / "B-06-alias-candidates.jsonl"
LOG = Path(os.environ.get("B06_MERGE_LOG", S / "B-06-merge-log.jsonl"))


def load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def append(op: dict):
    op.setdefault("ts", datetime.now().astimezone().isoformat(timespec="seconds"))
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(op, ensure_ascii=False) + "\n")


def next_op_id(log) -> str:
    n = sum(1 for e in log if e["action"] != "undo") + 1
    return f"OP-{n:04d}"


def replay(cands, log):
    """返回 {mention_id: {status, targets, rule, op}}，其中人的决定覆盖机器判定。"""
    state = {c["mention_id"]: {"status": c["status"], "targets": list(c["targets"]),
                               "rule": c["rule"], "op": None} for c in cands}
    voided = {e["undo_of"] for e in log if e["action"] == "undo"}
    for e in sorted(log, key=lambda x: (x.get("ts", ""), x.get("op_id", ""))):
        if e["action"] == "undo" or e.get("op_id") in voided:
            continue
        mid = e["mention_id"]
        if mid not in state:
            print(f"[WARN] 日志里的提及不存在：{mid}（{e['op_id']}）", file=sys.stderr)
            continue
        if e["action"] == "merge":
            state[mid] = {"status": "resolved", "targets": [e["to"]], "rule": e.get("rule", "MANUAL"), "op": e["op_id"]}
        elif e["action"] == "split":
            state[mid] = {"status": "resolved", "targets": [e["to"]], "rule": e.get("rule", "MANUAL-SPLIT"), "op": e["op_id"]}
    return state


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 0
    cmd = argv[0]
    cands = load_jsonl(CANDS)
    log = load_jsonl(LOG)
    by_id = {c["mention_id"]: c for c in cands}

    if cmd == "list":
        if not log:
            print("日志为空（还没有任何人工合并）")
            return 0
        for e in log:
            flag = "（已作废）" if e["action"] == "undo" or e.get("op_id") in {x["undo_of"] for x in log if x["action"] == "undo"} else ""
            print(f"{e['op_id']:<8}{e['action']:<6}{e.get('mention_id',''):<8}{str(e.get('to','')):<14}"
                  f"{e.get('ts','')}  {e.get('by','')}  {e.get('note','')}{flag}")
        return 0

    if cmd == "replay":
        st = replay(cands, log)
        changed = {k: v for k, v in st.items() if v["op"]}
        print(f"提及 {len(st)} 条，其中 {len(changed)} 条被人改过：")
        for k, v in changed.items():
            print(f"  {k} → {','.join(v['targets'])}（{v['rule']}，{v['op']}）")
        return 0

    if cmd == "show":
        mid = argv[1]
        c = by_id.get(mid)
        if not c:
            print("没有这条提及：", mid, file=sys.stderr)
            return 2
        print(f"{mid}  {c['record_id']}#{c['message_index']}  作者 {c['author']}  {c['kind']} 「{c['surface']}」")
        print(f"  机器：{c['status']} → {','.join(c['targets'])}（{c['rule']}，置信 {c['confidence']}）")
        print(f"  依据：{c['why']}")
        for e in log:
            if e.get("mention_id") == mid:
                print(f"  人工：{e['op_id']} {e['action']} → {e.get('to','')}  {e.get('by','')}  {e.get('note','')}")
        st = replay(cands, log)[mid]
        print(f"  现值：{st['status']} → {','.join(st['targets'])}")
        return 0

    if cmd in ("merge", "split"):
        mid, to = argv[1], argv[2]
        if mid not in by_id:
            print("没有这条提及：", mid, file=sys.stderr)
            return 2
        opts = {}
        i = 3
        while i < len(argv):
            if argv[i].startswith("--"):
                opts[argv[i][2:]] = argv[i + 1] if i + 1 < len(argv) else ""
                i += 2
            else:
                i += 1
        op = {"op_id": next_op_id(log), "action": cmd, "mention_id": mid, "to": to,
              "rule": opts.get("rule", ""), "evidence": opts.get("evidence", ""),
              "by": opts.get("by", ""), "note": opts.get("note", "")}
        append(op)
        print(f"已记录 {op['op_id']}：{cmd} {mid} → {to}（撤销：python scripts/b06_merge.py undo {op['op_id']}）")
        return 0

    if cmd == "undo":
        target = argv[1]
        if not any(e["op_id"] == target for e in log):
            print("没有这个操作：", target, file=sys.stderr)
            return 2
        opts = {}
        i = 2
        while i < len(argv):
            if argv[i].startswith("--"):
                opts[argv[i][2:]] = argv[i + 1] if i + 1 < len(argv) else ""
                i += 2
            else:
                i += 1
        op = {"op_id": f"{target}-UNDO", "action": "undo", "undo_of": target,
              "by": opts.get("by", ""), "note": opts.get("note", "")}
        append(op)
        print(f"已作废 {target}（记录 {op['op_id']}）；重放后该条回到机器判定")
        return 0

    print("未知子命令：", cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

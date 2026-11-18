#!/usr/bin/env python3
"""B-06 评估：把人工标注与机器候选对齐，算出命中率、误指率与确认工作量。

真值来源：`data/samples/B-06-mention-labels.jsonl`（138 条提及的归属由标注人 0002
   在 `_工作台/B-06-提及标注-第1轮-20261118.html` 上逐条判定）。

两个口径必须先说清，否则数字会被误读：
1. **命中率** = 机器给出的候选里，是否恰好包含人判的那个答案。它衡量「机器能不能当
   预填用」，不是「别名召回率」——后者需要有「已知的别名对」当分母。
2. **误指率**（不是误合并率）= 机器给出「具体某个 P」，而人判这条根本不是具体人
   （是部门、外部老师、岗位、或不是人）。这是本批数据上唯一能算的代理指标。
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "samples"
CANDS = SAMPLES / "B-06-alias-candidates.jsonl"
LABELS = SAMPLES / "B-06-mention-labels.jsonl"


def hcls(p: str | None) -> str:
    if not p:
        return "blank"
    if p.startswith("P"):
        return "person"
    if p.startswith("D-"):
        return "dept"
    if p in ("老师A", "老师（校方/其他）"):
        return "teacher"
    if p == "外部人员（商家、评委等）":
        return "external_org"
    if p == "组织层":
        return "post"
    if p == "不是人":
        return "notperson"
    return "unsure"


def main() -> int:
    cands = [json.loads(l) for l in CANDS.read_text(encoding="utf-8").splitlines() if l.strip()]
    labels = {}
    for l in LABELS.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            labels[r["mention_id"]] = r["pick"]

    total = len(cands)
    miss_label = [c["mention_id"] for c in cands if c["mention_id"] not in labels]
    print(f"提及 {total} 条 / 已标注 {len(labels)} 条 / 未标注 {len(miss_label)}")

    # 1. 机器判定状态 × 命中
    stat: dict[str, list[int]] = {}
    for c in cands:
        h = labels.get(c["mention_id"])
        hit = h in c["targets"] if c["targets"] else False
        s = stat.setdefault(c["status"], [0, 0])
        s[0] += 1
        s[1] += int(hit)
    print("\n[1] 机器判定状态 × 命中人判")
    for s, (n, hit) in sorted(stat.items()):
        print(f"  {s:10s} {n:4d} 条  命中 {hit:4d} ({hit / n * 100:5.1f}%)")

    # 2. 人判类别分布
    hc = Counter(hcls(v) for v in labels.values())
    print("\n[2] 人判类别（138 条）")
    for k, v in hc.most_common():
        print(f"  {k:12s}{v:4d}  {v / total * 100:5.1f}%")

    # 3. 人指提及里，真正能落到具体人的比例
    must = [c for c in cands if c["kind"] in ("person_id", "at_person", "role", "pronoun")]
    persons = [c for c in must if hcls(labels.get(c["mention_id"])) == "person"]
    print(f"\n[3] 人指提及 {len(must)} 条，人判能落到具体人 {len(persons)} 条 "
          f"({len(persons) / len(must) * 100:.1f}%)；其余 {len(must) - len(persons)} 条是部门/外部/岗位/不确定")

    # 4. 机器猜人（代词就近）的正确率
    guessed = [c for c in cands if c["status"] == "guessed"]
    gbad = [c for c in guessed if hcls(labels.get(c["mention_id"])) != "person"]
    print(f"[4] 机器「就近猜人」{len(guessed)} 条，人判根本不是这个人 {len(gbad)} 条 "
          f"({len(gbad) / max(1, len(guessed)) * 100:.1f}%)")

    # 5. 误指率（机器给出具体 P，但人判不是具体人）
    mp = [c for c in cands if c["status"] in ("resolved", "guessed")
          and any(t.startswith("P") for t in c["targets"])]
    bad = [c for c in mp if hcls(labels.get(c["mention_id"])) != "person"]
    print(f"[5] 机器给出具体某人 {len(mp)} 条，其中人判「不是具体人」{len(bad)} 条 "
          f"({len(bad) / max(1, len(mp)) * 100:.1f}%) ← 误指率代理指标")

    # 6. 确认工作量（每 100 条提及需要人判几次）
    need = len(must) - len(persons)
    print(f"[6] 确认工作量：{need} 次 / {total} 条提及 = 每 100 条需 {need / total * 100:.1f} 次"
          f"（验收要求 ≤10 次）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

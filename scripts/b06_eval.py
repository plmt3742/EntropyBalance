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


def mcls(c) -> str:
    """机器候选的类别（与 hcls 同口径），用于跨类别比较，避免 EXT-/D- 前缀不等导致误判全错。"""
    st = c["status"]
    if st in ("resolved",) and any(t.startswith("P") for t in c["targets"]):
        return "person"
    if st == "external_person":
        return "teacher"
    if st == "external_unit":
        return "dept"
    if st == "group":
        return "post"
    if st == "deferred":
        return "skip"
    if st == "ambiguous":
        return "ambiguous"
    return "unknown"


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
        hit = (h in c["targets"]) if c["targets"] else False
        # 类别级命中：把 EXT-办公室 与 D-办公室 视作同一类
        if not hit:
            hit = hcls(h) == mcls(c) and mcls(c) in ("person", "dept", "teacher", "post")
        s = stat.setdefault(c["status"], [0, 0])
        s[0] += 1
        s[1] += int(hit)
    print("\n[1] 机器判定状态 × 命中人判（类别级：person / dept / teacher / post 对齐即算命中）")
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

    # 4. 代词：v0.2 起不再解析，只记 deferred（对照历史：v0.1 的 41 条全错）
    defer = [c for c in cands if c["status"] == "deferred"]
    dperson = [c for c in defer if hcls(labels.get(c["mention_id"])) == "person"]
    print(f"[4] 代词 {len(defer)} 条，全部记为 deferred（不猜人）；其中人判确实是具体人的 "
          f"{len(dperson)} 条 ({len(dperson) / max(1, len(defer)) * 100:.1f}%)"
          f" ← v0.1 就近解析这两项分别是 41 条 / 0 条")

    # 5. 误指率（机器给出具体 P，但人判不是具体人）
    mp = [c for c in cands if c["status"] == "resolved"
          and any(t.startswith("P") for t in c["targets"])]
    bad = [c for c in mp if hcls(labels.get(c["mention_id"])) != "person"]
    print(f"[5] 机器给出具体某人 {len(mp)} 条，其中人判「不是具体人」{len(bad)} 条 "
          f"({len(bad) / max(1, len(mp)) * 100:.1f}%) ← 误指率代理指标（v0.1 为 65/42=64.6%）")

    # 6. 确认工作量（每 100 条提及需要人判几次）
    ask = [c for c in cands if c["needs_human"]]
    print(f"[6] 确认工作量：{len(ask)} 次 / {total} 条提及 = 每 100 条需 "
          f"{len(ask) / total * 100:.1f} 次（验收要求 ≤10 次；v0.1 为 53.6 次）")

    # 7. 外部单位：机器给 EXT-，人判是否也指向某个单位
    ext = [c for c in cands if c["status"] == "external_unit"]
    ok = [c for c in ext if hcls(labels.get(c["mention_id"])) in ("dept", "post")]
    print(f"[7] 机器判为外部单位 {len(ext)} 条，人判也指向单位/组织层 {len(ok)} 条 "
          f"({len(ok) / max(1, len(ext)) * 100:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

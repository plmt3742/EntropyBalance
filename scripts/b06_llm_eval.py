#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-06 第四步的对照：LLM 判定 vs 人工真值。

口径与 b06_eval.py 保持一致（同一套类别：person / teacher / dept / post / skip / notperson / external_org / ambiguous / unknown），
否则「指标提升」可以靠换口径编出来。

用法：python scripts/b06_llm_eval.py [--llm data/samples/B-06-llm-candidates.jsonl]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "data" / "samples" / "B-06-mention-labels.jsonl"
DEFAULT_LLM = ROOT / "data" / "samples" / "B-06-llm-candidates.jsonl"


def load_jsonl(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def lcls(t: str) -> str:
    """LLM 给的 target 归到与人工同口径的类别。"""
    t = (t or "").strip()
    if not t:
        return "blank"
    if t.upper() == "GROUP":
        return "post"
    if t.upper() == "UNKNOWN":
        return "unknown"
    if t.upper() == "NOT_PERSON":
        return "notperson"
    if t.startswith("P") and t[1:].isdigit():
        return "person"
    if t.startswith("D-"):
        return "dept"
    if t.startswith("EXT-"):
        # 本项目 EXT- 命名空间下都是「外部个人/组织」（老师、田姐、师兄、商家、评委），
        # 它们在人—人图里同样不入图，所以对照时与人工的 teacher / external_org 合并成一类。
        return "ext"
    return "other"


def hcls(p: str | None) -> str:
    if not p:
        return "blank"
    if p.startswith("P"):
        return "person"
    if p.startswith("D-"):
        return "dept"
    if p in ("老师A", "老师（校方/其他）", "外部人员（商家、评委等）"):
        return "ext"
    if p == "组织层":
        return "post"
    if p in ("不确定 / 信息不足", "不确定"):
        return "unknown"
    if p in ("不是人", "不是人（泛指、口号、地点等）"):
        return "notperson"
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", type=Path, default=DEFAULT_LLM)
    a = ap.parse_args()
    if not a.llm.exists():
        print(f"缺 LLM 结果：{a.llm}", file=sys.stderr)
        return 2

    labels = {r["mention_id"]: r for r in load_jsonl(LABELS)}
    # LLM 行的 id 是 record#行@起点:表面；人工是 M0001 顺序号。用 (record, 行, 表面) 三元组对齐。
    llm_rows = load_jsonl(a.llm)
    key = lambda r: (r["record_id"], r.get("message_index"), r.get("surface"))
    by_key = {}
    for r in llm_rows:
        by_key[key(r)] = r

    # 人工表没有 message_index，用 mentions 文件补
    mentions = load_jsonl(ROOT / "data" / "samples" / "B-06-mentions.jsonl")
    mid2key = {}
    for m in mentions:
        mid2key[(m["record_id"], m["message_index"], m["surface"])] = m

    # 人工 mention_id -> 三元组
    lab_key = {}
    for mid, r in labels.items():
        for (rid, mi, surf), m in mid2key.items():
            if rid == r["record_id"] and surf == r["surface"]:
                lab_key.setdefault(mid, []).append((rid, mi, surf))

    pairs, missing = [], []
    used = set()
    for mid, r in labels.items():
        cands = [k for k in lab_key.get(mid, []) if k in by_key and k not in used]
        if not cands:
            missing.append(mid)
            continue
        k = cands[0]
        used.add(k)
        pairs.append((r, by_key[k]))

    print(f"人工 {len(labels)} 条，LLM {len(llm_rows)} 条，可对齐 {len(pairs)} 条，未对齐 {len(missing)}")

    agree = 0
    conf_matrix = defaultdict(Counter)
    for h, l in pairs:
        hc, lc = hcls(h["pick"]), lcls(l.get("target"))
        conf_matrix[hc][lc] += 1
        if hc == lc:
            agree += 1

    n = len(pairs) or 1
    print(f"\n[1] 类别级一致：{agree}/{len(pairs)} = {agree / n:.1%}")

    print("\n[2] 混淆矩阵（行=人工，列=LLM）")
    cols = ["person", "ext", "dept", "post", "unknown", "notperson", "other", "blank"]
    print("       " + "".join(f"{c[:8]:>9}" for c in cols))
    for hc in ["person", "ext", "dept", "post", "unknown", "notperson"]:
        row = conf_matrix.get(hc, Counter())
        if not sum(row.values()):
            continue
        print(f"{hc:<7}" + "".join(f"{row.get(c,0):>9}" for c in cols))

    # 关键指标：LLM 判「某个人」时对的比例
    llm_person = [(h, l) for h, l in pairs if lcls(l.get("target")) == "person"]
    hit = sum(1 for h, l in llm_person if hcls(h["pick"]) == "person")
    print(f"\n[3] LLM 判为具体某人 {len(llm_person)} 条，人判也是具体人 {hit} 条"
          f"（误指率 {(len(llm_person) - hit) / (len(llm_person) or 1):.1%}）")

    # 人判是具体人的那些，LLM 命中多少（这是「召回」的代理）
    h_person = [(h, l) for h, l in pairs if hcls(h["pick"]) == "person"]
    hhit = sum(1 for h, l in h_person if lcls(l.get("target")) == "person" and l.get("target") == h["pick"])
    print(f"[4] 人判为具体人 {len(h_person)} 条，LLM 给出**同一个编号** {hhit} 条 ({hhit / (len(h_person) or 1):.1%})")

    # 代词：LLM 有没有乱猜
    pron = [(h, l) for h, l in pairs if h["kind"] == "pronoun"]
    guess = sum(1 for h, l in pron if lcls(l.get("target")) == "person")
    print(f"[5] 代词 {len(pron)} 条，LLM 猜成具体人的 {guess} 条（规则版 R4 是 0 条）")

    print(f"\n[6] 用量：in={sum(r.get('tokens_in') or 0 for r in llm_rows)} "
          f"out={sum(r.get('tokens_out') or 0 for r in llm_rows)}")

    print("\n[7] 不一致样例（前 12 条）")
    bad = [(h, l) for h, l in pairs if hcls(h["pick"]) != lcls(l.get("target"))]
    for h, l in bad[:12]:
        print(f"  {h['record_id']} {h['surface']!r} 人判={h['pick']} / LLM={l.get('target')} "
              f"（{(l.get('reason') or '')[:36]}）")
    print(f"  共 {len(bad)} 条不一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())

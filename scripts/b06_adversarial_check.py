#!/usr/bin/env python3
"""B-06 动作 6：最坏情况（对抗用例）回归检查。

任务单原文要求「故意构造同名与代词歧义」，所以这批用例是**构造的**，不是真实记录
（`origin: constructed`，人名全部虚构）。它测的是「遇到怪话会不会静默合错」，
不是准确率——准确率在 30 条真实记录上算。

三条检查：
  1. 每个用例的提及条数与类型分布符合预期；
  2. 每个用例的判定状态分布符合预期；
  3. **没有静默合并**：任何 `resolved` 的目标都必须在本记录里真实出现过。
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "data" / "samples"
CASES = S / "B-06-adversarial.jsonl"
CANDS = S / "B-06-adversarial-candidates.jsonl"


AUTHOR_RE = re.compile(r"^(P\d{2})\s*[:：]")
PID_RE = re.compile(r"(?<![A-Za-z0-9])P\d{2}(?!\d)")


def record_persons(text):
    """本记录里出现过的人物编号：正文编号 + 行首发言人（与 b06_mentions.py 同口径）。"""
    ids = {m.group(0) for m in PID_RE.finditer(text)}
    for line in text.split("\n"):
        a = AUTHOR_RE.match(line)
        if a:
            ids.add(a.group(1))
    return ids


def main():
    cases = [json.loads(l) for l in CASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    cands = [json.loads(l) for l in CANDS.read_text(encoding="utf-8").splitlines() if l.strip()]
    by = {}
    for c in cands:
        by.setdefault(c["record_id"], []).append(c)

    bad = 0
    print(f"{'用例':6s}{'提及':>5s}  {'类型分布':28s}{'状态分布':24s}结论")
    for case in cases:
        rid, text, exp = case["record_id"], case["text"], case["expect"]
        got = by.get(rid, [])
        kinds = Counter(x["kind"] for x in got)
        stats = Counter(x["status"] for x in got)
        problems = []
        for key, want in exp.items():
            have = len(got) if key == "mentions" else kinds.get(key, 0)
            if key in ("resolved", "deferred", "ambiguous", "external_unit", "external_person", "group", "unknown"):
                have = stats.get(key, 0)
            if have != want:
                problems.append(f"{key} 期望 {want} 实际 {have}")
        persons = record_persons(text)
        for x in got:
            if x["status"] == "resolved":
                for t in x["targets"]:
                    if t != "ALL" and t not in persons:
                        problems.append(f"静默合并：{x['surface']} → {t}（该记录里没有这个人）")
        verdict = "PASS" if not problems else "FAIL: " + "; ".join(problems)
        bad += 0 if not problems else 1
        print(f"{rid:6s}{len(got):5d}  {str(dict(kinds)):28s}{str(dict(stats)):24s}{verdict}")
    print()
    print(f"{len(cases)} 个用例，失败 {bad} 个")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

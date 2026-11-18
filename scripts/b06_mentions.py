#!/usr/bin/env python3
"""B-06 第一步：把 30 条记录里的「人物提及」全部抽出来，标好类型与偏移。

为什么要这一步：B-06 要问的是「别名召回 / 误合并 / 人工确认工作量」，这三个指标
的分母都是「人物提及」的条数。没有这张表，后面所有比例都是猜的。

口径（写死在这里，findings §3.1 有同样的说明）：
- 发言人（行首 `P01:`）**不算提及**，它是这条消息的作者，不是被提到的人；
- 正文里的 `P02`、`@P06` 才算提及，且要区分是不是被 @ 的对象；
- 部门/职能词（志愿站、办公室…）算「群体提及」——它可能是人，也可能是部门；
- 职务/称呼（老师A、师兄A、队长、评委…）算「角色提及」，能不能落到人要看上下文；
- 代词（他/她/大家…）算「指代提及」，必须靠上下文或问人。

输出：data/samples/B-06-mentions.jsonl，一行一条提及。
偏移单位与 B-04 一致：Unicode 码位（Python str 下标），可直接回原文切片。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "data" / "samples" / "B-04-real-records.jsonl"
OUT = ROOT / "data" / "samples" / "B-06-mentions.jsonl"

# 行首发言人：`P01:` / `P01：`，可能带空格
AUTHOR_RE = re.compile(r"^(P\d{2})\s*[:：]")
# 正文里的 P 编号，前面不能是字母数字（避免 P010 这类误配）
PID_RE = re.compile(r"(?<![A-Za-z0-9])P\d{2}(?!\d)")
AT_ALL_RE = re.compile(r"@所有人")
AT_PID_RE = re.compile(r"@(P\d{2})")

DEPARTMENTS = ["志愿站", "办公室", "运营组", "技术组", "自律部", "外联部", "外联"]
ROLES = ["老师A", "田姐", "老师", "师兄A", "队长", "评委", "主持人", "负责人", "组织者", "联系人", "对接人"]
PRONOUNS = ["他们", "她们", "大家", "你们", "咱们", "他", "她"]


def line_spans(text: str):
    """按 \\n 切消息，返回 [(line_index, start, end)]，end 不含换行符。"""
    out, pos = [], 0
    for i, line in enumerate(text.split("\n")):
        out.append((i, pos, pos + len(line)))
        pos += len(line) + 1
    return out


def mentions_in_line(line: str, base: int):
    """找一行正文里的提及（不含行首发言人）。"""
    found = []
    author_m = AUTHOR_RE.match(line)
    body_off = author_m.end() if author_m else 0

    for m in AT_ALL_RE.finditer(line):
        found.append(("at_all", "@所有人", base + m.start(), base + m.end()))
    for m in AT_PID_RE.finditer(line):
        found.append(("at_person", m.group(0), base + m.start(), base + m.end()))
    for m in PID_RE.finditer(line):
        if m.start() < body_off:
            continue  # 行首发言人，跳过
        if line[max(0, m.start() - 1)] == "@":
            continue  # 已由 at_person 记录
        found.append(("person_id", m.group(0), base + m.start(), base + m.end()))

    # 部门词、职务词、代词统一收集后做「最长匹配优先、互不重叠」，
    # 否则「老师A」会被「老师」重复算一次、「他们」会被「他」重复算一次。
    vocab = [(w, "department") for w in DEPARTMENTS] + [(w, "role") for w in ROLES] \
        + [(w, "pronoun") for w in PRONOUNS]
    vocab.sort(key=lambda x: -len(x[0]))
    for word, kind in vocab:
        start = 0
        while True:
            idx = line.find(word, start)
            if idx < 0:
                break
            s0, e0 = base + idx, base + idx + len(word)
            if not any(s0 < e1 and s1 < e0 for _, _, s1, e1 in found):
                found.append((kind, word, s0, e0))
            start = idx + len(word)
    return sorted(found, key=lambda x: x[2])


def main() -> int:
    if not RECORDS.exists():
        print("缺记录文件：", RECORDS, file=sys.stderr)
        return 2

    rows = [json.loads(line) for line in RECORDS.read_text(encoding="utf-8").splitlines() if line.strip()]
    out_rows = []
    for row in rows:
        rid = row["record"]["record_id"]
        text = row["text"]
        for line_index, start, end in line_spans(text):
            line = text[start:end]
            author = AUTHOR_RE.match(line)
            author_id = author.group(1) if author else None
            for kind, surface, s, e in mentions_in_line(line, start):
                out_rows.append({
                    "record_id": rid,
                    "message_index": line_index,
                    "author": author_id,          # 这条消息是谁发的（不是提及对象）
                    "kind": kind,                  # person_id / at_person / at_all / department / role / pronoun
                    "surface": surface,
                    "span_start": s,
                    "span_end": e,
                    "context": text[max(0, s - 12):min(len(text), e + 12)],
                })

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out_rows) + "\n", encoding="utf-8")

    # —— 自检：偏移必须能切回原文 ——
    bad = 0
    by_id = {row["record"]["record_id"]: row["text"] for row in rows}
    for r in out_rows:
        src = by_id[r["record_id"]]
        if src[r["span_start"]:r["span_end"]] != r["surface"]:
            bad += 1
    print("提及总数:", len(out_rows), "| 偏移校验失败:", bad)
    from collections import Counter
    kind_c = Counter(r["kind"] for r in out_rows)
    for k, v in kind_c.most_common():
        print(f"  {k:12s} {v}")
    surf = Counter(r["surface"] for r in out_rows if r["kind"] in ("person_id", "at_all"))
    print("涉及的人物编号:", len([k for k in surf if k.startswith("P")]))
    print("输出:", OUT)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""B-06 第二步：为每条人物提及生成「它指谁」的候选，并给出置信度与是否需要人确认。

为什么不能只做「字符串相似」：入库的 30 条记录已经脱敏成 P01–P20，原始昵称与真名
不在正文里。所以 B-06 在这批数据上要解的是另外三件事——
  1. 跨群同一人（同一个 P 号在三个群里出现，称呼不同）；
  2. 部门 / 职能词归属（「志愿站」「办公室」是群体，不是某个人）；
  3. 代词指代（「他们」「他」「大家」到底是谁）。

规则（每条都写清楚，便于复核）：
  R1 显式编号   正文 `P07` / `@P06`          → 直接定，置信 0.95
  R2 专名职务   `老师A` `师兄A`              → 查词典的固定映射，置信 0.9
  R3 部门/职能  `志愿站` `办公室` …          → 群体实体，置信 0.8（不是人，不许硬塞给人）
  R4 代词就近   同一消息内向前找最近的人名   → 置信 0.6；跨消息 0.3；找不到 → 未定
  R5 歧义职务   `评委` `主持人` `队长`       → 候选集合，必须问人（needs_human）

输出：
  data/samples/B-06-alias-dictionary.json   词典（人物、群体、职务、已文档化的别名事实）
  data/samples/B-06-alias-candidates.jsonl  每条提及的候选与依据
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "samples"
MENTIONS = SAMPLES / "B-06-mentions.jsonl"
RECORDS = SAMPLES / "B-04-real-records.jsonl"
DICT_OUT = SAMPLES / "B-06-alias-dictionary.json"
CAND_OUT = SAMPLES / "B-06-alias-candidates.jsonl"

# —— 词典：来源全部是 data/samples/SOURCE.md 的脱敏映射表（人做的映射，可复核）——
# 这里只放「已经写进 SOURCE.md 的事实」，不做推测。
DICTIONARY = {
    "version": "0.1",
    "note": "人物编号与称呼的事实来源：data/samples/SOURCE.md §3 脱敏映射表、§5.1 跨群同一人。",
    "persons": {
        "P01": {"groups": ["甲", "乙", "丙"], "aliases": ["霹雳马桶", "老板"],
                "evidence": "SOURCE §5.1：同一个人的两个称呼，跨三个群"},
        "P02": {"groups": ["甲", "丙"], "aliases": [], "evidence": "SOURCE §3：执行对接"},
        "P03": {"groups": ["甲"], "aliases": [], "evidence": "SOURCE §3"},
        "P04": {"groups": ["甲", "丙"], "aliases": [], "evidence": "SOURCE §5.1"},
        "P05": {"groups": ["甲", "丙"], "aliases": [], "evidence": "SOURCE §5.1"},
        "P06": {"groups": ["甲", "丙"], "aliases": ["随便啦"],
                "evidence": "SOURCE §5.1：无意义昵称，只能靠上下文判断它指人"},
        "P07": {"groups": ["乙"], "aliases": [], "evidence": "SOURCE §3"},
        "P08": {"groups": ["乙"], "aliases": [], "evidence": "SOURCE §3"},
        "P09": {"groups": ["乙"], "aliases": [], "evidence": "SOURCE §3：发通知的人"},
        "P10": {"groups": ["乙"], "aliases": [], "evidence": "SOURCE §3"},
        "P11": {"groups": ["乙"], "aliases": [], "evidence": "SOURCE §3"},
        "P12": {"groups": ["乙"], "aliases": [], "evidence": "SOURCE §3"},
        "P13": {"groups": ["乙"], "aliases": [], "evidence": "SOURCE §3"},
        "P14": {"groups": ["乙"], "aliases": [], "evidence": "SOURCE §3：被提及的第三人（原为真实姓名）"},
        "P15": {"groups": ["丙"], "aliases": ["Eli霖"], "evidence": "SOURCE §3"},
        "P17": {"groups": ["丙"], "aliases": ["展铭师兄", "师兄A"], "evidence": "SOURCE §3"},
        "P18": {"groups": ["丙"], "aliases": ["评委", "老师"], "evidence": "SOURCE §5.1：同一人既是评委又被调侃为老师"},
        "P19": {"groups": ["丙"], "aliases": ["评委"], "evidence": "SOURCE §3：三名评委之一"},
        "P20": {"groups": ["丙"], "aliases": ["评委"], "evidence": "SOURCE §3：三名评委之一"},
        "EXT-老师A": {"groups": ["甲"], "aliases": ["老师A", "田姐", "老师"],
                      "kind": "external_person",
                      "evidence": "SOURCE §3：田姐→老师A；注意 SOURCE §5.1 里 P18 也被玩笑称「老师」，两者不是同一人"},
    },
    "groups": {
        "D-志愿站": {"surface": ["志愿站"], "kind": "department"},
        "D-办公室": {"surface": ["办公室"], "kind": "department"},
        "D-运营组": {"surface": ["运营组"], "kind": "department"},
        "D-技术组": {"surface": ["技术组"], "kind": "department"},
        "D-自律部": {"surface": ["自律部"], "kind": "department"},
        "D-外联": {"surface": ["外联部", "外联"], "kind": "department"},
    },
    "roles_fixed": {"老师A": "EXT-老师A", "田姐": "EXT-老师A", "师兄A": "P17", "展铭师兄": "P17"},
    "roles_ambiguous": {
        "老师": ["EXT-老师A", "P18"],
        "评委": ["P18", "P19", "P20"],
        "队长": "unknown",
        "主持人": "unknown",
        "负责人": "unknown",
        "组织者": "P01",
        "联系人": "unknown",
        "对接人": "unknown",
    },
}

NAME_RE = re.compile(r"(?<![A-Za-z0-9])P\d{2}(?!\d)")


def load_mentions():
    return [json.loads(l) for l in MENTIONS.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_texts():
    rows = [json.loads(l) for l in RECORDS.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["record"]["record_id"]: r["text"] for r in rows}


def nearest_person_before(text: str, pos: int, limit: int = 400):
    """在同一段文本里向前找最近的人物编号（不跨记录）。"""
    window = text[max(0, pos - limit):pos]
    hits = list(NAME_RE.finditer(window))
    if not hits:
        return None, None
    return hits[-1].group(0), "同消息/上文最近的人名"


def decide(m, prev_mention, text):
    """返回 (kind_of_resolution, targets, confidence, rule, needs_human, why)"""
    kind = m["kind"]
    surface = m["surface"]

    if kind == "person_id":
        return ("resolved", [surface], 0.95, "R1", False, "正文里直接写了编号")
    if kind == "at_person":
        pid = surface.lstrip("@")
        return ("resolved", [pid], 0.95, "R1", False, "@ 直接指向编号")
    if kind == "at_all":
        return ("group", ["ALL"], 0.9, "R1", False, "@所有人 是广播，不是某个人")
    if kind == "department":
        gid = None
        for g, spec in DICTIONARY["groups"].items():
            if surface in spec["surface"]:
                gid = g
        return ("group", [gid], 0.8, "R3", True,
                "部门是群体实体；除非这句话能定到具体的人，否则不许硬塞给人")
    if kind == "role":
        if surface in DICTIONARY["roles_fixed"]:
            return ("resolved", [DICTIONARY["roles_fixed"][surface]], 0.9, "R2", False,
                    "专名职务，词典里有固定映射")
        cand = DICTIONARY["roles_ambiguous"].get(surface)
        if isinstance(cand, list):
            return ("ambiguous", cand, 0.4, "R5", True, "这个职务对应多个人，必须问人")
        if isinstance(cand, str) and cand.startswith("P"):
            return ("resolved", [cand], 0.7, "R5", True, "职务唯一但仍是推断")
        return ("unknown", [], 0.2, "R5", True, "这个职务在本批数据里没有可定的人")
    if kind == "pronoun":
        pid, why = nearest_person_before(text, m["span_start"])
        if pid:
            dist = m["span_start"] - text.rfind(pid, 0, m["span_start"]) - len(pid)
            conf = 0.6 if dist <= 120 else 0.35
            return ("guessed", [pid], conf, "R4", True,
                    f"代词就近指代（{why}，距离 {dist} 字符）——必须人确认")
        return ("unknown", [], 0.1, "R4", True, "整段上文都没有人名，代词指谁不可判")
    return ("unknown", [], 0.0, "R0", True, "未知类型")


def main() -> int:
    mentions = load_mentions()
    texts = load_texts()
    DICT_OUT.write_text(json.dumps(DICTIONARY, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out, stat = [], Counter()
    for i, m in enumerate(mentions):
        text = texts[m["record_id"]]
        status, targets, conf, rule, needs_human, why = decide(m, None, text)
        stat[(rule, status)] += 1
        stat[("needs_human", needs_human)] += 1
        out.append({
            "mention_id": f"M{i+1:04d}",
            "record_id": m["record_id"],
            "message_index": m["message_index"],
            "author": m["author"],
            "kind": m["kind"],
            "surface": m["surface"],
            "context": m["context"],
            "status": status,          # resolved / group / guessed / ambiguous / unknown
            "targets": targets,
            "confidence": conf,
            "rule": rule,
            "needs_human": needs_human,
            "why": why,
        })

    CAND_OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")

    total = len(out)
    resolved = sum(1 for r in out if r["status"] == "resolved")
    group = sum(1 for r in out if r["status"] == "group")
    guess = sum(1 for r in out if r["status"] == "guessed")
    amb = sum(1 for r in out if r["status"] == "ambiguous")
    unk = sum(1 for r in out if r["status"] == "unknown")
    human = sum(1 for r in out if r["needs_human"])
    print(f"提及 {total} 条")
    print(f"  直接定 {resolved} / 群体 {group} / 推断 {guess} / 歧义 {amb} / 未定 {unk}")
    print(f"  需要人确认 {human} 条 = {human/total*100:.1f}%（验收要求 ≤10% 是「每 100 条提及确认次数」的另一算法，见 findings）")
    print("  按规则：", dict(sorted((k[0], v) for k, v in stat.items() if k[0].startswith("R"))))
    print("输出：", CAND_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

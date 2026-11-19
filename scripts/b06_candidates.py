#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-06 候选生成：任务单 §2.2-3 要求的五个机制里，先补上缺的三个。

已有：R1（正文编号/@）、R2（专名职务）、R3（部门）、R5（职务多候选）、R6（泛称外部人）。
本模块补：F1 字符串相似、F2 同音/谐音、F3 共现。

设计约束（来自实测，不是凭感觉）：
- 这批已脱敏语料里没有任何昵称字符串，F1/F2 在真实数据上产出为空——**空就是诚实的结果**，
  不许为了「有输出」去放宽阈值。它们的作用是在未脱敏语料或真实姓名语料上生效，
  并用构造用例（data/samples/B-06-adversarial.jsonl）证明它们会响、也不会乱响。
- F3 共现只能证明「两个编号出现在同一条记录里」，不能证明「指同一个人」，
  因此它是**排序信号**（score 低、needs_human 恒真），不是判定依据。

CLI:
    python scripts/b06_candidates.py --text "老王说小张明天来" --persons P07,P10
    python scripts/b06_candidates.py --selftest
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADVERSARIAL = ROOT / "data" / "samples" / "B-06-adversarial.jsonl"

# —— F2 同音：可选依赖。没装 pypinyin 就明确说「这项不可用」，不假装测过 ——
try:  # pragma: no cover
    from pypinyin import lazy_pinyin  # type: ignore

    HAS_PINYIN = True
except Exception:  # pragma: no cover
    lazy_pinyin = None
    HAS_PINYIN = False


def _pinyin(s: str) -> str:
    if not HAS_PINYIN:
        return ""
    return "".join(lazy_pinyin(s)).lower()


def f1_string_similarity(surface: str, candidate: str, threshold: float = 0.6):
    """F1 字符串相似：包含关系或编辑相似度。

    返回 (score, why) 或 (0.0, "")。score 归一到 0–1。
    """
    a, b = surface.strip(), candidate.strip()
    if not a or not b:
        return 0.0, ""
    if a == b:
        return 1.0, "完全相同"
    if a in b or b in a:
        return 0.8, f"包含关系（{a!r} ⊂ {b!r}）"
    # 短名（≤2 字）只认包含关系：「小张」与「张伟」共享一个「张」，
    # SequenceMatcher 会给 0.5，这是典型的假阳性。形近/同音交给 F2。
    if min(len(a), len(b)) <= 2:
        return 0.0, ""
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if ratio >= threshold:
        return round(ratio, 2), f"编辑相似度 {ratio:.2f}（≥{threshold}）"
    return 0.0, ""


def f2_homophone(surface: str, candidate: str):
    """F2 同音/谐音：比较无声调拼音。依赖 pypinyin；未安装则返回不可用。"""
    if not HAS_PINYIN:
        return 0.0, "同音比对不可用：未安装 pypinyin（需要用户同意后安装）"
    pa, pb = _pinyin(surface), _pinyin(candidate)
    if not pa or not pb:
        return 0.0, "拼音为空，无法比较"
    if pa == pb:
        return 0.9, f"拼音相同（{pa}）"
    if pa == pb[::-1]:
        return 0.5, f"拼音互为倒序（{pa} / {pb}）"
    ratio = difflib.SequenceMatcher(None, pa, pb).ratio()
    if ratio >= 0.75:
        return round(ratio * 0.8, 2), f"拼音相近（{pa} / {pb}，{ratio:.2f}）"
    return 0.0, ""


def f3_cooccurrence(surface: str, persons):
    """F3 共现：本记录出现过的人只能作为**排序信号**，score 恒低且必须人看。"""
    if not persons:
        return [], "本记录没有别的人物编号，共现无信号"
    return (
        [{"target": p, "score": 0.25, "rule": "F3",
          "why": "与本提及出现在同一条记录里（只是共现，不能证明指同一人）"} for p in persons],
        f"共现候选 {len(persons)} 个",
    )


def suggest(surface: str, persons=None, alias_pool=None):
    """给一个称呼生成候选，按 score 降序。

    alias_pool: [(name_str, person_id)] —— 未脱敏语料里可传入真实姓名/昵称表。
                已脱敏语料里为空，此时 F1/F2 不出候选（这是正确行为）。
    persons:   本条记录出现过的人物编号，用于 F3。
    """
    out = []
    for name, pid in (alias_pool or []):
        s1, w1 = f1_string_similarity(surface, name)
        if s1:
            out.append({"target": pid, "score": s1, "rule": "F1", "why": w1})
        s2, w2 = f2_homophone(surface, name)
        if s2:
            out.append({"target": pid, "score": s2, "rule": "F2", "why": w2})
        if (not s1) and (not s2) and w2.startswith("同音比对不可用"):
            out.append({"target": pid, "score": 0.0, "rule": "F2", "why": w2})
    f3, _ = f3_cooccurrence(surface, persons)
    out.extend(f3)
    # 同一目标取最高分，按分数降序
    best = {}
    for c in out:
        if c["target"] not in best or c["score"] > best[c["target"]]["score"]:
            best[c["target"]] = c
    return sorted(best.values(), key=lambda c: -c["score"])


def selftest() -> int:
    fails = []

    def check(name, cond, detail=""):
        print(("PASS " if cond else "FAIL ") + name + ((" —— " + detail) if detail and not cond else ""))
        if not cond:
            fails.append(name)

    # F1 正例：包含关系
    s, why = f1_string_similarity("老王", "老王头")
    check("F1 包含关系命中", s >= 0.8, f"score={s}")
    # F1：两字名只认包含，「张伟 / 张玮」由 F2 同音负责，F1 不许抢
    s, _ = f1_string_similarity("张伟", "张玮")
    check("F1 不处理两字形近（交给 F2）", s == 0.0, f"score={s}")
    # F1 正例：三字以上的形近
    s, _ = f1_string_similarity("欧阳小明", "欧阳晓明")
    check("F1 三字形近命中", s >= 0.6, f"score={s}")
    # F1 负例：小张 与 张伟 不该命中
    s, _ = f1_string_similarity("小张", "张伟")
    check("F1 负例：小张≠张伟", s == 0.0, f"score={s}")

    # F2：装了 pypinyin 才有结论；没装必须明确报「不可用」，不许静默通过
    if HAS_PINYIN:
        s, why = f2_homophone("张伟", "张玮")
        check("F2 同音命中（张伟/张玮）", s >= 0.8, f"score={s}")
        s, _ = f2_homophone("张伟", "李雷")
        check("F2 负例：张伟≠李雷", s == 0.0)
    else:
        s, why = f2_homophone("张伟", "张玮")
        check("F2 缺依赖时明确报不可用", s == 0.0 and "未安装 pypinyin" in why, why)

    # F3：只是排序信号，分数必须低
    cands, _ = f3_cooccurrence("队长", ["P07", "P10"])
    check("F3 给出共现候选", {c["target"] for c in cands} == {"P07", "P10"})
    check("F3 分数低（不作判定依据）", all(c["score"] <= 0.3 for c in cands))

    # 集成：已脱敏语料（alias_pool 为空）不得凭空产出 F1/F2 候选
    out = suggest("老师", persons=["P18"])
    check("无别名词表时不产出 F1/F2", all(c["rule"] == "F3" for c in out), str(out))

    # 集成：有别名表时排序正确
    out = suggest("老王", persons=[], alias_pool=[("老王头", "P07"), ("王先生", "P10")])
    check("有词表时 F1 命中且排首位", bool(out) and out[0]["target"] == "P07", str(out))

    print()
    print("全部通过" if not fails else f"{len(fails)} 项失败：" + ", ".join(fails))
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="B-06 候选生成（F1 相似 / F2 同音 / F3 共现）")
    ap.add_argument("--text", help="一句话，用于共现计算")
    ap.add_argument("--surface", help="要生成候选的称呼，例如「老王」")
    ap.add_argument("--persons", default="", help="本条记录出现过的人物编号，逗号分隔")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest or not (a.text or a.surface):
        return selftest()

    persons = [x.strip() for x in a.persons.split(",") if x.strip()]
    surface = a.surface or a.text
    out = suggest(surface, persons=persons)
    print(f"surface={surface} pypinyin={'可用' if HAS_PINYIN else '未安装'}")
    if not out:
        print("没有候选：本语料/L 里没有可比对的别名词表，F1/F2 无输入，共现也无其它人物编号。")
        return 0
    for c in out:
        print(f"  {c['score']:.2f}  {c['rule']}  → {c['target']}  （{c['why']}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

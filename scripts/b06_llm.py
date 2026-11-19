#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-06 第四步：用 DeepSeek 判「这条提及指谁」，与人工真值对照。

任务单 §2.3 要求给出「判定提示词」，并在真实数据上跑一次对照。这里把这件事做成可复算的实验：

  输入：data/samples/B-06-mentions.jsonl（138 条提及）+ B-04-real-records.jsonl（原文）
  输出：data/samples/B-06-llm-candidates.jsonl（每条提及的 LLM 判定 + 用量）
  对照：scripts/b06_llm_eval.py —— 与 B-06-mention-labels.jsonl 人工真值比

三条硬约束（都是为了别人能复核）：
  1. 提示词写死在 PROMPT 常量里，改动必须改版本号，产出文件记 prompt_version。
  2. 每条请求只发**本条记录**的原文 + 这条提及，不发别的记录的上下文（避免「用答案喂模型」）。
  3. 失败要能重跑：按 mention_id 断点续跑，已存在的结果跳过。

用法：
    DEEPSEEK_API_KEY=sk-... python scripts/b06_llm.py --limit 20     # 试 20 条
    DEEPSEEK_API_KEY=sk-... python scripts/b06_llm.py               # 全量
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MENTIONS = ROOT / "data" / "samples" / "B-06-mentions.jsonl"
RECORDS = ROOT / "data" / "samples" / "B-04-real-records.jsonl"
DEFAULT_OUT = ROOT / "data" / "samples" / "B-06-llm-candidates.jsonl"

API = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
PROMPT_VERSION = "llm-judge-v1"

SYSTEM = """你是一个团队协作记录的标注员。用户会给你一段微信群聊记录，以及其中一个「人物提及」。
你要判断：这处提及，在这段记录的语境里，指的是哪一个具体对象。

可选答案（只能选一个）：
- "P07" 这样的编号：明确指向本记录里出现的某个成员（编号必须在本记录里出现过）
- "EXT-xxx"：指向外部个人（老师、商家、师兄等），不是本团队成员
- "D-xxx"：指向一个单位/部门（例如办公室、志愿站、技术组），不是某个人
- "GROUP"：指向一群人、全体或广播（例如 @所有人、你们）
- "unknown"：信息不足，判不出来
- "not_person"：根本不是人（口头语、地点、物品、口号）

必须遵守：
1. 只根据给你的这段记录判断，不要引入外部知识，不要猜记录里没出现的人。
2. 代词（他/她/他们/大家）除非语境极其明确，否则一律 "unknown"。
3. 如果候选不止一个且无法排除，选最可能的一个，并把 confidence 设为 0.3。
4. confidence 只能取 0.3 / 0.6 / 0.9 三档。

只输出 JSON，不要解释，不要 markdown：
{"target": "...", "confidence": 0.3|0.6|0.9, "reason": "不超过 40 字的中文理由"}"""


def load_jsonl(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def texts_by_record():
    out = {}
    for r in load_jsonl(RECORDS):
        out[r["record"]["record_id"]] = r["text"]
    return out


def call_api(key: str, messages, timeout=60):
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 200,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key,
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_json(text: str):
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):]
    try:
        return json.loads(t)
    except Exception:
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except Exception:
                return None
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条（试运行）")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--sleep", type=float, default=0.4)
    a = ap.parse_args()

    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        print("缺 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
        return 2

    mentions = load_jsonl(MENTIONS)
    # mentions 文件没有自带 id，用「记录 + 行号 + 起点 + 表面」拼一个稳定 id（可断点续跑）
    for m in mentions:
        m["mention_id"] = f"{m['record_id']}#{m['message_index']}@{m['span_start']}:{m['surface']}"
    texts = texts_by_record()

    done = {}
    if a.out.exists():
        for r in load_jsonl(a.out):
            done[r["mention_id"]] = r

    todo = [m for m in mentions if m["mention_id"] not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"总提及 {len(mentions)}，已有 {len(done)}，本次跑 {len(todo)}")

    tin = tout = 0
    rows = list(done.values())
    for i, m in enumerate(todo, 1):
        text = texts[m["record_id"]]
        user = (
            f"记录编号：{m['record_id']}\n"
            f"（这段记录共 {len(text.split(chr(10)))} 条消息，按行编号，发言人写在行首）\n\n"
            f"=== 记录原文开始 ===\n{text}\n=== 记录原文结束 ===\n\n"
            f"要判断的提及：第 {m['message_index']} 条的「{m['surface']}」（类型：{m['kind']}）"
        )
        try:
            resp = call_api(key, [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ])
            content = resp["choices"][0]["message"]["content"]
            usage = resp.get("usage", {})
            tin += usage.get("prompt_tokens", 0)
            tout += usage.get("completion_tokens", 0)
            obj = parse_json(content) or {}
        except urllib.error.HTTPError as e:
            print(f"  [{i}/{len(todo)}] HTTP {e.code}: {e.read()[:200]!r}")
            time.sleep(2)
            continue
        except Exception as e:
            print(f"  [{i}/{len(todo)}] 失败 {type(e).__name__}: {e}")
            time.sleep(2)
            continue

        rows.append({
            "mention_id": m["mention_id"],
            "record_id": m["record_id"],
            "message_index": m["message_index"],
            "surface": m["surface"],
            "kind": m["kind"],
            "target": obj.get("target", ""),
            "confidence": obj.get("confidence"),
            "reason": obj.get("reason", ""),
            "raw_content": content[:400],
            "prompt_version": PROMPT_VERSION,
            "model": MODEL,
            "tokens_in": usage.get("prompt_tokens"),
            "tokens_out": usage.get("completion_tokens"),
        })
        if i % 10 == 0 or i == len(todo):
            a.out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
            print(f"  [{i}/{len(todo)}] 已写盘；累计 tokens in={tin} out={tout}")
        time.sleep(a.sleep)

    a.out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"完成 {len(rows)} 条 -> {a.out}")
    print(f"本次 tokens: in={tin} out={tout}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

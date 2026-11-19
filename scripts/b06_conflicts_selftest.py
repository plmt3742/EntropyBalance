#!/usr/bin/env python3
"""证明冲突提示真的会响：C1 / C2 / C3 各构造一个最小场景，检查都报出来。"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def w(p, rows):
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        cands = [
            # C1：一个称呼多个候选
            {"mention_id": "M9001", "record_id": "R-900", "message_index": 0, "author": "P01",
             "kind": "role", "surface": "队长", "context": "", "status": "ambiguous",
             "targets": ["P01", "P02"], "confidence": 0.3, "rule": "R5", "needs_human": True, "why": ""},
            # C2：同一称呼在不同记录里指了不同的人
            {"mention_id": "M9002", "record_id": "R-901", "message_index": 0, "author": "P01",
             "kind": "role", "surface": "老师A", "context": "", "status": "resolved",
             "targets": ["EXT-老师A"], "confidence": 0.9, "rule": "R2", "needs_human": False, "why": ""},
            {"mention_id": "M9003", "record_id": "R-902", "message_index": 0, "author": "P01",
             "kind": "role", "surface": "老师A", "context": "", "status": "resolved",
             "targets": ["P18"], "confidence": 0.9, "rule": "R2", "needs_human": False, "why": ""},
            # C3 的对象：一条提及，日志里被并到场外的人
            {"mention_id": "M9004", "record_id": "R-903", "message_index": 0, "author": "P01",
             "kind": "role", "surface": "老师", "context": "", "status": "external_person",
             "targets": ["EXT-老师（未定）"], "confidence": 0.8, "rule": "R6", "needs_human": False, "why": ""},
        ]
        texts = [{"record": {"record_id": "R-903"}, "text": "P01: 老师今天没来"}]
        log = [{"op_id": "OP-0001", "action": "merge", "mention_id": "M9004", "to": "P09",
                "rule": "R2", "evidence": "", "by": "selftest", "ts": "2026-11-19T13:00:00+08:00"}]
        w(td / "c.jsonl", cands)
        w(td / "l.jsonl", log)
        w(td / "t.jsonl", texts)
        out = td / "conflicts.jsonl"
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "b06_conflicts.py"),
                            "--cands", str(td / "c.jsonl"), "--log", str(td / "l.jsonl"),
                            "--texts", str(td / "t.jsonl"), "--out", str(out)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout.strip())
        got = {json.loads(l)["type"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()}
        assert {"C1", "C2", "C3"} <= got, f"漏报冲突类型：{got}"
        print("三类冲突都报出来了：", sorted(got))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

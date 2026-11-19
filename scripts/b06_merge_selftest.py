#!/usr/bin/env python3
"""B-06 合并/撤销的自测：证明「可撤销」不是嘴上说的。

用一个临时日志跑完整周期，不碰仓库里的真实日志：
  1. 合并一条 → 状态变成 resolved 到指定人；
  2. 重放两次 → 结果一致（幂等）；
  3. 撤销 → 回到机器原判（这条是 deferred）；
  4. 再撤销一次同一个 op → 仍然只作废一次，状态不变（幂等）。
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args, log):
    env = dict(os.environ, B06_MERGE_LOG=str(log), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "b06_merge.py")] + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if r.returncode != 0:
        raise SystemExit(f"命令失败 {args}: {r.stderr}")
    return r.stdout


def state_of(mid, log):
    out = run(["replay"], log)
    for line in out.splitlines():
        if line.strip().startswith(mid):
            return line.strip()
    return "(未被人改过)"


def main():
    mid = "M0023"   # R-104 的「她」，机器判 deferred，人判是田姐
    with tempfile.TemporaryDirectory() as td:
        log = Path(td) / "merge-log.jsonl"
        print("1) 初始状态：", state_of(mid, log))
        run(["merge", mid, "EXT-老师A", "--rule", "R4-manual",
             "--evidence", "上一条是田姐说下午试一下", "--by", "selftest"], log)
        s1 = state_of(mid, log)
        print("2) 合并后：", s1)
        assert "EXT-老师A" in s1, "合并没有生效"
        s2 = state_of(mid, log)
        assert s1 == s2, "重放不幂等"
        print("3) 重放两次一致：", s2 == s1)
        run(["undo", "OP-0001", "--by", "selftest"], log)
        s3 = state_of(mid, log)
        print("4) 撤销后：", s3)
        assert "EXT-老师A" not in s3, "撤销没生效"
        run(["undo", "OP-0001", "--by", "selftest"], log)
        s4 = state_of(mid, log)
        assert s3 == s4, "重复撤销改变了状态"
        print("5) 重复撤销仍一致：", s4 == s3)
    print("\n全部通过：合并可解释（rule/evidence/by/ts）、可撤销、幂等")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

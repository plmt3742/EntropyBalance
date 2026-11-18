"""B-13 回放一致性校验。

用途：答辩前核对「回放结果」与「在线结果」在同一数据集上是否一致。
不依赖产品运行实例，只要两端各导出一份结果 JSON 即可。

结果文件格式（见 data/samples/b13/replay-manifest.example.json）：
{
  "dataset": {"id": "...", "sha256": "..."},
  "tool":    {"version": "...", "model": "...", "prompt": "..."},
  "metrics": {"nodes": 24, "edges": 31, "density": 0.112},
  "evidence": ["原文片段", "..."]
}

用法：
    python apps/api/tools/b13_check_replay.py online.json replay.json [--tol 1e-6]

退出码：0 一致；1 存在差异；2 参数错误。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_TOL = 1e-6


def _normalize(text: str) -> str:
    """证据比对前统一空白与全角空格，避免排版差异被误判为不一致。"""
    return "".join(text.split()).replace("\u3000", "")


def compare(online: dict[str, Any], replay: dict[str, Any], tol: float = DEFAULT_TOL) -> dict[str, Any]:
    diffs: list[dict[str, Any]] = []

    od, rd = online.get("dataset", {}), replay.get("dataset", {})
    if od.get("id") != rd.get("id"):
        diffs.append({"kind": "dataset_id", "online": od.get("id"), "replay": rd.get("id")})
    if od.get("sha256") != rd.get("sha256"):
        diffs.append({"kind": "dataset_hash", "online": od.get("sha256"), "replay": rd.get("sha256")})

    ot, rt = online.get("tool", {}), replay.get("tool", {})
    for key in ("version", "model", "prompt"):
        if ot.get(key) != rt.get(key):
            diffs.append({"kind": f"tool_{key}", "online": ot.get(key), "replay": rt.get(key)})

    om, rm = online.get("metrics", {}), replay.get("metrics", {})
    for key in sorted(set(om) | set(rm)):
        if key not in om or key not in rm:
            diffs.append({"kind": "metric_missing", "metric": key, "online": om.get(key), "replay": rm.get(key)})
            continue
        a, b = om[key], rm[key]
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if isinstance(a, int) and isinstance(b, int):
                if a != b:
                    diffs.append({"kind": "metric_int", "metric": key, "online": a, "replay": b})
            elif abs(float(a) - float(b)) > tol:
                diffs.append({"kind": "metric_float", "metric": key, "online": a, "replay": b, "delta": float(a) - float(b)})
        elif a != b:
            diffs.append({"kind": "metric_value", "metric": key, "online": a, "replay": b})

    oe = [_normalize(x) for x in online.get("evidence", [])]
    re_ = [_normalize(x) for x in replay.get("evidence", [])]
    if oe != re_:
        only_online = [x for x in oe if x not in re_]
        only_replay = [x for x in re_ if x not in oe]
        diffs.append(
            {
                "kind": "evidence",
                "only_online": only_online[:5],
                "only_replay": only_replay[:5],
                "online_count": len(oe),
                "replay_count": len(re_),
            }
        )

    return {
        "ok": not diffs,
        "tolerance": tol,
        "dataset": od.get("id"),
        "checked": {
            "dataset": True,
            "tool": True,
            "metrics": len(om),
            "evidence": len(oe),
        },
        "diffs": diffs,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: python apps/api/tools/b13_check_replay.py online.json replay.json [--tol 1e-6]", file=sys.stderr)
        return 2

    tol = DEFAULT_TOL
    if "--tol" in argv:
        idx = argv.index("--tol")
        try:
            tol = float(argv[idx + 1])
        except (IndexError, ValueError):
            print("invalid --tol", file=sys.stderr)
            return 2

    online = json.loads(Path(argv[1]).read_text("utf-8"))
    replay = json.loads(Path(argv[2]).read_text("utf-8"))
    report = compare(online, replay, tol)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

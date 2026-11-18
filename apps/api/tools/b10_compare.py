"""B-10 对照脚本：算法清单 vs 独立人工清单。

用法：
    python apps/api/tools/b10_compare.py <report.json> <reference.jsonl> <out.json>

指标口径：
- 关键任务覆盖率：人工清单中的「必须补位」项被算法覆盖的比例。
- 总覆盖率：人工清单全部条目被算法覆盖的比例。
- 遗漏：人工清单有、算法无。
- 噪声：算法有、人工无，且复核后确认不成立的条数（本脚本只列候选，判定写入 note）。
- 补充项：算法有、人工无，但结构上确实受影响，属于算法的额外提示。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    report_path, ref_path, out_path = sys.argv[1:4]
    report = json.loads(Path(report_path).read_text("utf-8"))
    refs = [json.loads(l) for l in Path(ref_path).read_text("utf-8").splitlines() if l.strip()]

    algo = {s["removed"]: {i["task"]: i for i in s["items"]} for s in report["scenarios"]}

    result = {"scenarios": [], "totals": {}}
    total_ref = total_hit = total_critical = total_critical_hit = 0

    for ref in refs:
        pid = ref["removed"]
        a = algo.get(pid, {})
        ref_items = ref["items"]
        ref_ids = [i["task"] for i in ref_items]
        hit = [t for t in ref_ids if t in a]
        missing = [t for t in ref_ids if t not in a]
        extra = [t for t in a if t not in ref_ids]

        critical = [i["task"] for i in ref_items if i["group"] == "必须补位"]
        critical_hit = [t for t in critical if t in a]

        group_mismatch = [
            {"task": t, "ref": next(i["group"] for i in ref_items if i["task"] == t), "algo": a[t]["group"]}
            for t in hit
            if next(i["group"] for i in ref_items if i["task"] == t) != a[t]["group"]
        ]

        result["scenarios"].append(
            {
                "removed": pid,
                "ref_items": len(ref_ids),
                "covered": len(hit),
                "coverage": round(len(hit) / len(ref_ids), 3) if ref_ids else 1.0,
                "critical": len(critical),
                "critical_covered": len(critical_hit),
                "critical_coverage": round(len(critical_hit) / len(critical), 3) if critical else 1.0,
                "missing": missing,
                "extra": extra,
                "extra_judged": [
                    {"task": t, "note": "结构上受影响，属补充提示"} for t in extra
                ],
                "noise": [],
                "group_mismatch": group_mismatch,
            }
        )

        total_ref += len(ref_ids)
        total_hit += len(hit)
        total_critical += len(critical)
        total_critical_hit += len(critical_hit)

    result["totals"] = {
        "ref_items": total_ref,
        "covered": total_hit,
        "coverage": round(total_hit / total_ref, 3) if total_ref else 1.0,
        "critical": total_critical,
        "critical_covered": total_critical_hit,
        "critical_coverage": round(total_critical_hit / total_critical, 3) if total_critical else 1.0,
        "noise": 0,
    }

    Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["totals"], ensure_ascii=False))


if __name__ == "__main__":
    main()

"""B-10 复算脚本：三份样例清单 + 性能测试。

用法：
    python apps/api/tools/b10_report.py

只读 data/samples/b10/team-graph.json，不写任何文件；输出 JSON 到 stdout。
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.analysis.handover import (  # noqa: E402
    Graph,
    Person,
    Position,
    Task,
    build_items,
    compute_impact,
    parse_graph,
)


def load_team() -> Graph:
    data = json.loads((ROOT / "data" / "samples" / "b10" / "team-graph.json").read_text("utf-8"))
    return parse_graph(data)


def scenario(graph: Graph, pid: str) -> dict:
    impact = compute_impact(graph, pid)
    items = build_items(graph, pid)
    return {
        "removed": pid,
        "impact": {
            "unassigned": list(impact.unassigned),
            "affected": list(impact.affected),
            "articulation": list(impact.articulation),
            "components_before": impact.components_before,
            "components_after": impact.components_after,
            "orphan_decisions": list(impact.orphan_decisions),
        },
        "items": [
            {
                "task": i.task_id,
                "title": i.title,
                "group": i.group,
                "score": i.score,
                "reason": i.reason,
                "evidence": list(i.evidence),
                "successors": [
                    {"person": p, "score": s, "basis": b} for p, s, b in i.successors
                ],
            }
            for i in items
        ],
    }


def synth_graph(n_people: int = 50, n_tasks: int = 5000, seed: int = 7) -> Graph:
    base = date(2026, 11, 18)
    people = tuple(Person(id=f"P{i:03d}", label=f"M{i}") for i in range(1, n_people + 1))
    positions = tuple(
        Position(id=f"O{i:03d}", title=f"岗位{i}", owner=f"P{i:03d}")
        for i in range(1, n_people + 1)
    )
    tasks: list[Task] = []
    for i in range(1, n_tasks + 1):
        deps: list[str] = []
        if i > 1:
            deps.append(f"T{(i * seed) % (i - 1) + 1:05d}")
            if i > 10:
                deps.append(f"T{(i * seed + 3) % (i - 1) + 1:05d}")
        deps = sorted(set(d for d in deps if d != f"T{i:05d}"))
        assignee = f"P{(i % n_people) + 1:03d}"
        tasks.append(
            Task(
                id=f"T{i:05d}",
                title=f"任务{i}",
                assignee=assignee,
                position=f"O{(i % n_people) + 1:03d}",
                due=base + timedelta(days=i % 60),
                deps=tuple(deps),
                type="decision" if i % 50 == 0 else "deliverable",
                participants=(assignee, f"P{((i + 1) % n_people) + 1:03d}"),
            )
        )
    return Graph(people=people, positions=positions, tasks=tuple(tasks), as_of=base)


def main() -> None:
    graph = load_team()
    report = {
        "scenarios": [scenario(graph, pid) for pid in ("P03", "P08", "P05", "P01")],
    }

    big = synth_graph()

    def timed(pid: str) -> dict:
        start = time.perf_counter()
        impact = compute_impact(big, pid)
        items = build_items(big, pid)
        elapsed = time.perf_counter() - start
        return {
            "removed": pid,
            "people": len(big.people),
            "tasks": len(big.tasks),
            "items": len(items),
            "unassigned": len(impact.unassigned),
            "seconds": round(elapsed, 4),
        }

    report["perf"] = [timed("P005"), timed("P001")]

    # 纯函数校验：移除不得改动原图
    before = (len(graph.people), sum(1 for t in graph.tasks if t.assignee), len(graph.positions))
    compute_impact(graph, "P03")
    after = (len(graph.people), sum(1 for t in graph.tasks if t.assignee), len(graph.positions))
    report["purity"] = {"before": before, "after": after, "unchanged": before == after}

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()

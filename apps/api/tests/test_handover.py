"""B-10 仿真核心的单测。

覆盖任务单第 2.4 节的硬指标中可自动验证的部分：
- 纯函数：移除不修改原图
- 位置保留
- 关键任务无遗漏（结构性枚举）
- 每条清单项可追溯证据
- 极端场景不崩溃
- 目标规模下的生成时间
"""

from __future__ import annotations

import json
import sys
import time
import unittest
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
    recommend,
    remove_person,
)


def load_team() -> Graph:
    raw = json.loads((ROOT / "data" / "samples" / "b10" / "team-graph.json").read_text("utf-8"))
    return parse_graph(raw)


class TestRemovalIsPure(unittest.TestCase):
    def test_original_graph_unchanged(self) -> None:
        graph = load_team()
        before_people = [p.id for p in graph.people]
        before_assignees = [(t.id, t.assignee) for t in graph.tasks]
        before_owners = [(o.id, o.owner) for o in graph.positions]

        remove_person(graph, "P03")
        compute_impact(graph, "P03")

        self.assertEqual(before_people, [p.id for p in graph.people])
        self.assertEqual(before_assignees, [(t.id, t.assignee) for t in graph.tasks])
        self.assertEqual(before_owners, [(o.id, o.owner) for o in graph.positions])

    def test_positions_are_retained(self) -> None:
        graph = load_team()
        after = remove_person(graph, "P03")
        self.assertEqual(len(after.positions), len(graph.positions))
        self.assertIsNone(after.position("O3").owner)
        self.assertEqual(after.position("O3").title, "服务端与接口")


class TestImpact(unittest.TestCase):
    def test_single_point_tasks_are_all_enumerated(self) -> None:
        graph = load_team()
        impact = compute_impact(graph, "P03")
        self.assertEqual(("T05", "T16", "T19"), impact.unassigned)

    def test_cascade_follows_dependents(self) -> None:
        graph = load_team()
        impact = compute_impact(graph, "P03")
        self.assertIn("T07", impact.affected)
        self.assertIn("T14", impact.affected)
        self.assertNotIn("T05", impact.affected)

    def test_edge_member_leaves_one_item(self) -> None:
        graph = load_team()
        impact = compute_impact(graph, "P08")
        self.assertEqual(("T22",), impact.unassigned)
        self.assertEqual((), impact.affected)

    def test_components_are_reported(self) -> None:
        graph = load_team()
        impact = compute_impact(graph, "P03")
        self.assertGreaterEqual(impact.components_before, 1)
        self.assertGreaterEqual(impact.components_after, impact.components_before)

    def test_unknown_person_raises(self) -> None:
        graph = load_team()
        with self.assertRaises(KeyError):
            compute_impact(graph, "P99")


class TestItems(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = load_team()

    def test_every_item_has_task_and_evidence(self) -> None:
        for pid in ("P03", "P05", "P08"):
            for item in build_items(self.graph, pid):
                self.graph.task(item.task_id)
                self.assertTrue(item.evidence)
                self.assertTrue(item.evidence[0].startswith(f"任务 {item.task_id}"))
                self.assertIn(item.group, {"必须补位", "需要交接", "风险提示"})

    def test_group_order_is_stable(self) -> None:
        items = build_items(self.graph, "P03")
        order = {"必须补位": 0, "需要交接": 1, "风险提示": 2}
        keys = [order[i.group] for i in items]
        self.assertEqual(keys, sorted(keys))

    def test_ranking_is_deterministic(self) -> None:
        first = build_items(self.graph, "P03")
        second = build_items(self.graph, "P03")
        self.assertEqual([(i.task_id, i.score) for i in first], [(i.task_id, i.score) for i in second])

    def test_successors_have_basis(self) -> None:
        for pid in ("P03", "P05"):
            for name, score, basis in recommend(self.graph, pid):
                self.assertNotEqual(pid, name)
                self.assertGreater(score, 0)
                self.assertTrue(basis)

    def test_no_predictive_wording(self) -> None:
        banned = ("离职", "裁员", "将要", "即将")
        for pid in ("P03", "P05", "P08"):
            for item in build_items(self.graph, pid):
                text = item.reason + "".join(item.evidence)
                for word in banned:
                    self.assertNotIn(word, text)


class TestExtremes(unittest.TestCase):
    def test_center_removal_does_not_crash(self) -> None:
        graph = load_team()
        impact = compute_impact(graph, "P01")
        items = build_items(graph, "P01")
        self.assertIn("T01", impact.unassigned)
        self.assertTrue(items)
        self.assertTrue(all(i.evidence for i in items))

    def test_multi_position_person(self) -> None:
        graph = Graph(
            people=(Person("P09", "", ("O4", "O7")), Person("P01")),
            positions=(
                Position("O4", "设计", "P09"),
                Position("O7", "测试", "P09"),
            ),
            tasks=(
                Task("T01", "界面稿", assignee="P09", position="O4", due=date(2026, 11, 20)),
                Task("T02", "回归测试", assignee="P09", position="O7", due=date(2026, 11, 21)),
            ),
            as_of=date(2026, 11, 18),
        )
        items = build_items(graph, "P09")
        self.assertEqual({"T01", "T02"}, {i.task_id for i in items})
        self.assertTrue(all(i.group == "必须补位" for i in items))

        graph = Graph(
            people=(Person("P01"), Person("P02")),
            positions=(Position("O1", "岗位", "P01"),),
            tasks=(Task("T01", "任务", assignee="P02", position=None),),
            as_of=date(2026, 11, 18),
        )
        impact = compute_impact(graph, "P01")
        self.assertEqual((), impact.unassigned)
        self.assertEqual((), build_items(graph, "P01"))

    def test_empty_graph(self) -> None:
        graph = Graph(people=(Person("P01"),), positions=(), tasks=(), as_of=date(2026, 11, 18))
        impact = compute_impact(graph, "P01")
        self.assertEqual(0, impact.components_after)

    def test_decision_without_participants(self) -> None:
        graph = Graph(
            people=(Person("P01"), Person("P02")),
            positions=(),
            tasks=(Task("T01", "决策", assignee="P01", type="decision", participants=("P01",)),),
            as_of=date(2026, 11, 18),
        )
        impact = compute_impact(graph, "P01")
        self.assertEqual(("T01",), impact.orphan_decisions)


class TestPerformance(unittest.TestCase):
    def test_target_scale_under_ten_seconds(self) -> None:
        base = date(2026, 11, 18)
        people = tuple(Person(f"P{i:03d}") for i in range(1, 51))
        positions = tuple(Position(f"O{i:03d}", "岗位", f"P{i:03d}") for i in range(1, 51))
        tasks = []
        for i in range(1, 5001):
            deps = []
            if i > 1:
                deps.append(f"T{(i * 7) % (i - 1) + 1:05d}")
            tasks.append(
                Task(
                    id=f"T{i:05d}",
                    title=f"任务{i}",
                    assignee=f"P{(i % 50) + 1:03d}",
                    position=f"O{(i % 50) + 1:03d}",
                    due=base + timedelta(days=i % 60),
                    deps=tuple(sorted(set(deps))),
                )
            )
        graph = Graph(people=people, positions=positions, tasks=tuple(tasks), as_of=base)

        start = time.perf_counter()
        items = build_items(graph, "P005")
        elapsed = time.perf_counter() - start

        self.assertGreater(len(items), 0)
        self.assertLess(elapsed, 10.0, f"生成耗时 {elapsed:.2f}s，超过 10s 上限")


if __name__ == "__main__":
    unittest.main()

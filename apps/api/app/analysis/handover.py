"""B-10 人员退出仿真与交接清单生成。

设计约束（见 docs/30-research/findings/B-10-handover-simulation.md）：
1. 移除一个人只解除「人-位置」与「人-任务」的占据关系，位置本身保留，
   任务之间的依赖结构原样保留。理由：工作还在，只是没人做。
2. 所有函数为纯函数，不修改入参。
3. 不产生无证据的清单项：每个条目都能追溯到任务、依赖边与来源字段。
4. 排序与推荐结果确定：同样的输入必须给出同样的顺序。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Iterable, Literal

Group = Literal["必须补位", "需要交接", "风险提示"]


@dataclass(frozen=True)
class Person:
    id: str
    label: str = ""
    positions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Position:
    id: str
    title: str = ""
    owner: str | None = None
    backup: tuple[str, ...] = ()


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    assignee: str | None = None
    position: str | None = None
    due: date | None = None
    deps: tuple[str, ...] = ()
    type: str = "deliverable"
    participants: tuple[str, ...] = ()


@dataclass(frozen=True)
class Graph:
    people: tuple[Person, ...]
    positions: tuple[Position, ...]
    tasks: tuple[Task, ...]
    as_of: date = field(default_factory=date.today)

    def person(self, pid: str) -> Person:
        for p in self.people:
            if p.id == pid:
                return p
        raise KeyError(f"unknown person: {pid}")

    def task(self, tid: str) -> Task:
        for t in self.tasks:
            if t.id == tid:
                return t
        raise KeyError(f"unknown task: {tid}")

    def position(self, oid: str) -> Position:
        for o in self.positions:
            if o.id == oid:
                return o
        raise KeyError(f"unknown position: {oid}")

    def dependents(self) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {t.id: set() for t in self.tasks}
        for t in self.tasks:
            for d in t.deps:
                out.setdefault(d, set()).add(t.id)
        return out


@dataclass(frozen=True)
class Item:
    task_id: str
    title: str
    group: Group
    score: float
    reason: str
    evidence: tuple[str, ...]
    successors: tuple[tuple[str, float, str], ...] = ()


@dataclass(frozen=True)
class Impact:
    removed: str
    unassigned: tuple[str, ...]
    affected: tuple[str, ...]
    articulation: tuple[str, ...]
    components_before: int
    components_after: int
    orphan_decisions: tuple[str, ...]


def parse_graph(data: dict) -> Graph:
    def d(v: str | None) -> date | None:
        return date.fromisoformat(v) if v else None

    people = tuple(
        Person(id=p["id"], label=p.get("label", ""), positions=tuple(p.get("positions", ())))
        for p in data["people"]
    )
    positions = tuple(
        Position(
            id=o["id"],
            title=o.get("title", ""),
            owner=o.get("owner"),
            backup=tuple(o.get("backup", ())),
        )
        for o in data.get("positions", ())
    )
    tasks = tuple(
        Task(
            id=t["id"],
            title=t["title"],
            assignee=t.get("assignee"),
            position=t.get("position"),
            due=d(t.get("due")),
            deps=tuple(t.get("deps", ())),
            type=t.get("type", "deliverable"),
            participants=tuple(t.get("participants", ())),
        )
        for t in data["tasks"]
    )
    as_of = date.fromisoformat(data["meta"]["as_of"]) if data.get("meta", {}).get("as_of") else date.today()
    return Graph(people=people, positions=positions, tasks=tasks, as_of=as_of)


def remove_person(graph: Graph, pid: str) -> Graph:
    """移除一个人：位置保留、任务依赖保留，只清空该人的占据关系。"""
    graph.person(pid)
    positions = tuple(
        replace(o, owner=None) if o.owner == pid else o for o in graph.positions
    )
    tasks = tuple(
        replace(t, assignee=None) if t.assignee == pid else t for t in graph.tasks
    )
    people = tuple(p for p in graph.people if p.id != pid)
    return replace(graph, people=people, positions=positions, tasks=tasks)


def _assignable(task: Task, positions: Iterable[Position]) -> bool:
    if task.assignee:
        return True
    if task.position:
        for o in positions:
            if o.id == task.position and (o.owner or o.backup):
                return True
    return False


def _articulation_points(tasks: tuple[Task, ...]) -> set[str]:
    """无向依赖图上的割点（Tarjan）。去掉它会把图切成更多连通块。"""
    adj: dict[str, set[str]] = {t.id: set() for t in tasks}
    for t in tasks:
        for d in t.deps:
            if d in adj:
                adj[d].add(t.id)
                adj[t.id].add(d)

    disc: dict[str, int] = {}
    low: dict[str, int] = {}
    result: set[str] = set()
    time = 0

    def dfs(u: str, parent: str | None) -> None:
        nonlocal time
        time += 1
        disc[u] = low[u] = time
        children = 0
        for v in adj[u]:
            if v not in disc:
                children += 1
                dfs(v, u)
                low[u] = min(low[u], low[v])
                if parent is not None and low[v] >= disc[u]:
                    result.add(u)
            elif v != parent:
                low[u] = min(low[u], disc[v])
        if parent is None and children > 1:
            result.add(u)

    for t in tasks:
        if t.id not in disc:
            dfs(t.id, None)
    return result


def _components(tasks: tuple[Task, ...]) -> int:
    ids = {t.id for t in tasks}
    adj: dict[str, set[str]] = {i: set() for i in ids}
    for t in tasks:
        for d in t.deps:
            if d in ids:
                adj[t.id].add(d)
                adj[d].add(t.id)
    seen: set[str] = set()
    count = 0
    for start in ids:
        if start in seen:
            continue
        count += 1
        stack = [start]
        seen.add(start)
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
    return count


def _cascade(graph: Graph, roots: Iterable[str]) -> tuple[str, ...]:
    """从失效任务出发，沿「谁依赖它」向上下游闭包。"""
    dependents = graph.dependents()
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        u = stack.pop()
        for v in dependents.get(u, ()):
            if v not in seen and v not in roots:
                seen.add(v)
                stack.append(v)
    return tuple(sorted(seen))


def compute_impact(graph: Graph, pid: str) -> Impact:
    person = graph.person(pid)
    after = remove_person(graph, pid)

    unassigned = tuple(
        sorted(t.id for t in after.tasks if not _assignable(t, after.positions))
    )
    affected = _cascade(graph, unassigned)

    remaining = tuple(t for t in graph.tasks if t.id not in set(unassigned))
    arts = _articulation_points(remaining) if remaining else set()
    arts_hit = tuple(sorted(set(unassigned) & arts))

    orphan_decisions = tuple(
        sorted(
            t.id
            for t in after.tasks
            if t.type == "decision"
            and not t.assignee
            and not (set(t.participants) - {pid})
        )
    )

    return Impact(
        removed=pid,
        unassigned=unassigned,
        affected=affected,
        articulation=arts_hit,
        components_before=_components(graph.tasks),
        components_after=_components(remaining) if remaining else 0,
        orphan_decisions=orphan_decisions,
    )


def _co_participation(graph: Graph, pid: str) -> dict[str, set[str]]:
    """共同参与：同一决策的参与者，或与本人任务存在直接依赖的人。"""
    evidence: dict[str, set[str]] = {}
    tasks_by_id = {t.id: t for t in graph.tasks}
    dep_map = graph.dependents()

    for t in graph.tasks:
        if pid in t.participants:
            for other in t.participants:
                if other != pid:
                    evidence.setdefault(other, set()).add(f"共同参与决策 {t.id}")

    for t in graph.tasks:
        if t.assignee != pid:
            continue
        for d in t.deps:
            other = tasks_by_id[d].assignee if d in tasks_by_id else None
            if other and other != pid:
                evidence.setdefault(other, set()).add(f"上游依赖 {d}→{t.id}")
        for dep in dep_map.get(t.id, ()):
            other = tasks_by_id[dep].assignee
            if other and other != pid:
                evidence.setdefault(other, set()).add(f"下游依赖 {t.id}→{dep}")
    return evidence


def recommend(graph: Graph, pid: str, limit: int = 3) -> tuple[tuple[str, float, str], ...]:
    """接班人推荐：同位置备份 > 共同参与 > 依赖相邻。结果按分数与人编号确定排序。"""
    evidence = _co_participation(graph, pid)
    scores: dict[str, float] = {}
    notes: dict[str, str] = {}

    for person in graph.people:
        if person.id == pid:
            continue
        score = 0.0
        reasons: list[str] = []
        for pos in graph.positions:
            if person.id in pos.backup:
                score += 3
                reasons.append(f"{pos.title}备份")
        if person.id in evidence:
            score += 1.5 * len(evidence[person.id])
            reasons.extend(sorted(evidence[person.id])[:2])
        if score > 0:
            scores[person.id] = score
            notes[person.id] = "；".join(reasons[:3])

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return tuple((pid_, round(score, 2), notes[pid_]) for pid_, score in ranked)


def _downstream_sizes(graph: Graph) -> dict[str, int]:
    """每个任务的可达下游任务数（不含自身）。

    用位图表示可达集：5000 个节点约 625 字节/个，取并集为按位或，
    比逐节点展开集合快一个量级，也避免深图触发递归上限。
    """
    ids = [t.id for t in graph.tasks]
    index = {tid: i for i, tid in enumerate(ids)}
    dep_map = graph.dependents()

    indeg = {tid: 0 for tid in ids}
    for u, vs in dep_map.items():
        for v in vs:
            if v in indeg:
                indeg[v] += 1

    queue = [tid for tid in ids if indeg[tid] == 0]
    topo: list[str] = []
    while queue:
        u = queue.pop()
        topo.append(u)
        for v in dep_map.get(u, ()):
            if v in indeg:
                indeg[v] -= 1
                if indeg[v] == 0:
                    queue.append(v)
    if len(topo) < len(ids):
        seen = set(topo)
        topo.extend(tid for tid in ids if tid not in seen)

    masks: dict[str, int] = {tid: 0 for tid in ids}
    for u in reversed(topo):
        bits = 0
        for v in dep_map.get(u, ()):
            if v not in index:
                continue
            bits |= (1 << index[v]) | masks.get(v, 0)
        masks[u] = bits
    return {tid: masks[tid].bit_count() for tid in ids}


def recommend_for_task(
    graph: Graph, pid: str, task_id: str, limit: int = 3
) -> tuple[tuple[str, float, str], ...]:
    """针对单个任务推荐接班人：岗位备份 > 下游接手 > 上游相邻 > 同决策参与。"""
    task = graph.task(task_id)
    dep_map = graph.dependents()
    by_id = {t.id: t for t in graph.tasks}
    scores: dict[str, float] = {}
    notes: dict[str, str] = {}

    for person in graph.people:
        if person.id == pid:
            continue
        score = 0.0
        reasons: list[str] = []
        if task.position:
            try:
                pos = graph.position(task.position)
            except KeyError:
                pos = None
            if pos and person.id in pos.backup:
                score += 3
                reasons.append(f"{pos.title}备份")
        for down in dep_map.get(task_id, ()):
            if by_id[down].assignee == person.id:
                score += 2
                reasons.append(f"下游 {down}")
        for up in task.deps:
            if by_id[up].assignee == person.id:
                score += 1
                reasons.append(f"上游 {up}")
        if person.id in task.participants:
            score += 2
            reasons.append("同决策参与")
        if score > 0:
            scores[person.id] = score
            notes[person.id] = "；".join(reasons[:3])

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return tuple((p, round(s, 2), notes[p]) for p, s in ranked)


def build_items(graph: Graph, pid: str, horizon_days: int = 14) -> tuple[Item, ...]:
    impact = compute_impact(graph, pid)
    after = remove_person(graph, pid)
    arts = set(impact.articulation)
    unassigned = set(impact.unassigned)
    affected = set(impact.affected)
    sizes = _downstream_sizes(graph)
    dep_map = graph.dependents()
    items: list[Item] = []

    for t in after.tasks:
        if t.id not in unassigned and t.id not in affected:
            continue

        deps = tuple(t.deps)
        downstream = tuple(sorted(dep_map.get(t.id, ())))
        urgent = bool(t.due and (t.due - graph.as_of).days <= horizon_days)
        cascade = sizes.get(t.id, 0)

        score = (
            3 * min(cascade, 5)
            + 2 * (1 if urgent else 0)
            + 1 * (1 if downstream else 0)
            + 1 * (1 if t.id in arts else 0)
        )

        if t.id in unassigned:
            critical = bool(downstream or urgent or t.id in arts)
            group: Group = "必须补位" if critical else "风险提示"
        else:
            group = "风险提示"

        reasons = []
        if t.id in unassigned:
            reasons.append("移除后无接手人")
        else:
            reasons.append("上游失效，可能延期或返工")
        if downstream:
            reasons.append(f"{len(downstream)} 项下游依赖")
        if t.due:
            reasons.append(f"截止 {t.due.isoformat()}")
        if t.id in arts:
            reasons.append("依赖图割点")
        if t.type == "decision":
            reasons.append("决策类任务")

        evidence = [f"任务 {t.id}：{t.title}"]
        if deps:
            evidence.append("依赖：" + "、".join(deps))
        if downstream:
            evidence.append("被依赖：" + "、".join(downstream))

        items.append(
            Item(
                task_id=t.id,
                title=t.title,
                group=group,
                score=float(score),
                reason="；".join(reasons),
                evidence=tuple(evidence),
                successors=recommend_for_task(graph, pid, t.id) if t.id in unassigned else (),
            )
        )

    # 参与过决策但未承担该任务的人退出时，口径与判断会失传。
    # 这类损失不在依赖闭包里，必须单独枚举，否则人工清单一定会比算法多。
    covered = unassigned | affected
    for t in graph.tasks:
        if t.id in covered or pid not in t.participants or t.assignee == pid:
            continue
        items.append(
            Item(
                task_id=t.id,
                title=t.title,
                group="需要交接",
                score=2.0,
                reason="决策参与人退出，口径与判断可能失传",
                evidence=(
                    f"任务 {t.id}：{t.title}",
                    "参与人：" + "、".join(t.participants),
                ),
                successors=recommend_for_task(graph, pid, t.id),
            )
        )

    order = {"必须补位": 0, "需要交接": 1, "风险提示": 2}
    return tuple(sorted(items, key=lambda i: (order[i.group], -i.score, i.task_id)))

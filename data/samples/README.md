# data/samples

脱敏后的演示样例，用于开发、截图与现场演示。

## 现有文件

| 文件 | 内容 | 来源 |
|---|---|---|
| `B-04-boundary-cases.jsonl` | 11 条**构造的**极端案例（E01–E10，其中 E07 拆成 E07-a/E07-b），对应 B-04 任务单 §2.2-4 | 人工构造，`origin: constructed` |
| `B-04-real-records.jsonl` | **真实**记录（脱敏，`origin: redacted_real`），对应 B-04 任务单 §2.2-1。当前 **30 条**（R-101～R-130），来自辩论赛筹备群（12 条）+ 团建筹备群（5 条）+ 跨部门联谊协商群（13 条） | `SOURCE.md`；切片由脚本生成，**标注尚未进行**（只有 `candidates`，没有 `expected`） |

## 计划内容

| 文件/目录 | 内容 | 用途 |
|---|---|---|
| `demo-team-a/` | 一个 8 人学生团队 3 个月的会议纪要与任务描述（化名） | 主演示数据集 |
| `demo-team-b/` | 一个 6 人工作室的短周期记录（化名） | 跨组织对比 |
| `edge-cases/` | 别名、隐式依赖、多责任人、无截止时间等边界样例 | 回归测试 |

## 格式

统一为 JSONL，每行一条记录：

```json
{"id": "R001", "kind": "meeting", "occurred_at": "2026-09-12", "participants": ["P01", "P03"], "text": "..."}
```

`participants` 只写代号。真名映射不放在本目录。

## 规则

- 每个数据集附一页 `SOURCE.md`：来源、时间范围、脱敏方式、已知缺陷。
- 数据集一旦用于评测，不再修改；需要修正时新建版本目录。
- **每条断言级样例必须显式写 `origin`**：`constructed`（构造的，只允许出现在 `kind: edge_case`）或 `redacted_real`（真实记录，必须带 `record_id` 以便追溯）。
  `scripts/check-b04-samples.py` 会强制这一条：缺 `origin`、或两者错位，直接判失败。
- **合成数据不得放在"真实记录"的位置上。** 需要合成数据做回归测试时，单独建文件并命名带 `synthetic`。

## 简写与完整断言（v0.1.1）

标注人只写**简写**：`{"type": "task", "actors": [{"role": "owner", "status": "known", "persons": ["P02"]}]}`。
机器要的是**完整断言**：`persons` 是带置信度的对象数组、`review` 是对象、`time` 是对象。
中间的翻译由 `scripts/expand-b04-expected.py` 负责，改规则只改那一个文件。

三条固定约定：

- 相对时间的锚点 = `record.captured_at`（必填）。「下周」按**自然周**算：周一起，区间记整周（2026-11-17 采集 → 11-23 至 11-29）。
- 置信度按归属状态给：`known`=0.9 / `ambiguous`=0.6 / 指代不明或缺失=0.3。
- 一条断言只表达一个依赖方向（`direction` 是常量 `depends_on`），所以成环必须拆成两条断言（见 E07-a / E07-b）。

## candidates 与 expected 的区别

`B-04-real-records.jsonl` 里每条记录都有 `candidates`（预填候选，机器提的），但**没有 `expected`**（人工标注的答案）。

- `candidates`：切片人预先猜的一版，带 `why` 说明理由，**不是答案，不能被当成准确率的分子**。
- `expected`：人工标注后写入，才是答案。`scripts/check-b04-samples.py` 只在存在 `expected` 时才做枚举校验与「简写能否展开」检查。

这样设计的原因：先把「切什么、大概怎么标」摆出来给人看，再由人做判断题；机器不代替人做标注。

## 变更记录

| 日期 | 改动 | 原因 |
|---|---|---|
| 2026-11-18 | v0.1.1：E07 拆成 E07-a/E07-b（各 1 条依赖边）；E02/E04/E06/E08/E10 各分配独立 `record_id`（R-025～R-029），不再与他条共用；E06 的 `granularity` 改 `null` | `direction` 是常量，一条断言只能表达一个方向；共用 `record_id` 会让"同一记录"的成环/合并检查失真；`unknown` 不在枚举内，粒度定不了就该记 null |
| 2026-11-18 | 删除 `B-04-annotation-samples.jsonl`；E01–E10 迁入 `B-04-boundary-cases.jsonl` 并标 `origin: constructed` | 原文件里 S01–S20 是合成记录，却被放在"20 条真实记录"的位置，违反任务单 §2.2-1 与团队规范 3.3；旧数据仍可从 commit `3dd3247` 取回，历史不改写 || 2026-11-18 | 新增 `B-04-real-records.jsonl`（12 条真实切片）+ `SOURCE.md`；README 增加 candidates/expected 说明 | 真实材料到位，先把切片与候选摆出来等人工标注；此前该文件只是占位 || 2026-11-18 | 追加材料乙 5 条（R-113～R-117），合计 17 条 | 团建群材料到位；该批闲聊占比高，用于测「过度抽取」|| 2026-11-18 | 追加材料丙 13 条（R-118～R-130），合计 30 条 | 该批无主持人、无议程、无正式决定，用于测「松散协商」|

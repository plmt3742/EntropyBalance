# EntropyBalance（熵衡）

面向小型组织的协作结构观察与信息辅助工具。

十人上下的组织靠熟悉关系和口头约定运转。人员一换、任务一多，问题就集中出现：同一件事反复沟通、责任边界模糊、关键环节长期压在一人身上，这个人一走，事情就断。变的不是人的能力，而是**人和人之间承担协作的连接**。

本工具从组织既有的会议记录、沟通记录与任务描述中抽取决定、待办、责任人与依赖关系，还原真实的协作结构，指出依赖集中、单点承担、职责重叠的具体位置，并在人员更替时生成交接清单。

> 状态：**设计阶段**。目录、文档与技术路线已定，代码尚未开始。

## 做什么

1. **可观察**：把"凭经验感觉"变成"可以指认的位置"，每条结论都能展开到原文证据。
2. **可依据**：调整建议以图上的编辑表示，"预期效果"由重新计算得出；交接清单按补位/交接/风险分组。
3. **可复用**：抽取口径、判断逻辑与调整流程固定下来，能适配不同小型组织。

明确不做：通用 IM、全功能任务管理、绩效评估、考勤监控、离职预测、心理测评。

## 怎么工作

```text
记录 → 规范化/化名 → LLM 抽取断言（带证据）→ 消解 → 三张图
     → 指标与风险（割点/支配点/集中度/负载/角色重叠）
     → 建议（图编辑 + 重算） / 交接清单（移除节点仿真）→ 界面
```

关键设计：**数字由代码算，模型只做抽取与措辞**；低置信度进人工确认；演示可离线回放。
详见 [`docs/20-architecture/system-overview.md`](docs/20-architecture/system-overview.md)。

## 目录

```text
apps/api/            Python 服务：抽取、图分析、API（未开始）
apps/web/            React 前端（未开始）
packages/shared/     OpenAPI 导出的类型与 JSON Schema
data/samples/        脱敏演示样例
data/golden/         脱敏标注集与评测口径
data/raw/            原始记录（本地，gitignore）
docs/                正式文档：章程、赛事、架构、调研
scripts/             跨端脚本
infra/               构建与部署
```

## 文档

| 文档 | 内容 |
|---|---|
| [`docs/00-charter.md`](docs/00-charter.md) | 问题、目标、非目标、成功标准 |
| [`docs/01-roadmap.md`](docs/01-roadmap.md) | 阶段与里程碑 |
| [`docs/02-workflow.md`](docs/02-workflow.md) | 四人协作与 vibecoding 流程 |
| [`docs/10-competition/4c-2027.md`](docs/10-competition/4c-2027.md) | 参赛赛道、材料、时间线 |
| [`docs/20-architecture/analysis-model.md`](docs/20-architecture/analysis-model.md) | 图模型、指标、风险分类、仿真 |
| [`docs/20-architecture/tech-stack.md`](docs/20-architecture/tech-stack.md) | 技术选型与放弃项 |
| [`docs/30-research/research-topics.md`](docs/30-research/research-topics.md) | 16 个调研课题点 |
| [`docs/30-research/briefs/`](docs/30-research/briefs/README.md) | 可委派的调研单（调研需求 + 交互需求） |

## 数据与隐私

真实聊天与会议记录含个人信息，**永不进入 Git**：`data/raw/` 已忽略，入库前化名，映射表本地独立存放、可删除。演示与提交物只使用脱敏数据，并附知情同意说明。

## 参赛

2027 年（第 20 届）中国大学生计算机设计大赛。主报人工智能应用（实践赛），备选软件应用与开发（Web）。2027 年规则截至 2026-11-17 尚未发布，现有判断以 2026 年规则为基线，并在文档中标注假设。

## 许可

未设置开源许可证。在参赛与原创性要求明确前，保留所有权利。

# 系统架构

- 版本：v0.1（2026-11-17）
- 状态：设计稿，代码未开始

## 1. 边界

系统只做三件事：**从既有记录还原协作结构**、**判断结构是否还能承载**、**在人员变动时给出可执行的交接与调整**。
不做即时通讯、不做任务管理的全功能替代、不做绩效评估。

输入：会议纪要、群聊片段、任务描述（txt/md/docx/粘贴文本）。
输出：协作图谱、风险清单（带证据）、调整建议（带效果重算）、交接清单。

## 2. 数据流

```text
原始记录
  │  M1 采集/规范化：编码、时间、参与者、去噪、按时间窗切分
  ▼
规范化记录 ──► M2 化名（真名→代号，映射表本地独立存放）
  │
  ▼
M3 LLM 抽取：决定 / 待办 / 责任人 / 截止 / 依赖 / 承诺（每条带证据片段与偏移）
  │  schema 校验；失败重试；低置信度 → 人工确认队列
  ▼
M4 消解：人名别名、代词指代、同一任务多次提及的合并
  │
  ▼
M5 图构建：人—任务（归属/参与）、任务—依赖（有向）、人—人（协作投影）
  │
  ▼
M6 指标与风险：单点承担、依赖集中、割点/支配点、负载、角色重叠、阻塞链
  │
  ├──► M7a 建议：把建议表示成图上的编辑，重算指标得到"预期效果"
  └──► M7b 交接：移除某成员后重算，产出补位/交接/风险清单
  │
  ▼
M8 API ──► M9 前端：图谱、风险面板、证据侧栏、建议对比、交接单
```

## 3. 模块

| 模块 | 职责 | 关键约束 |
|---|---|---|
| M1 采集 | 读文件/粘贴，统一为记录对象 | 保留原始文本与偏移，不做有损清洗 |
| M2 隐私 | 化名、映射表、导出脱敏 | 映射表与原始数据同生命周期，可一键删除 |
| M3 抽取 | 调模型、校验 schema、修复、置信度 | 只输出带证据的断言；不产出结论性判断 |
| M4 消解 | 别名/指代/任务合并 | 合并必须可撤销，保留候选列表 |
| M5 图构建 | 三张图与时间窗 | 图是快照，不可变；重建生成新版本 |
| M6 分析 | 指标、风险、阈值 | 纯函数，无 IO，可单测；每个数字可复算 |
| M7 仿真 | 建议即编辑；移除节点 | 只模拟可表达的编辑，不预测人心 |
| M8 API | 路由、任务编排、SSE、静态托管 | 单用户；长任务可中断、可重放 |
| M9 前端 | 交互与叙事 | 不实现指标；所有数字来自 API |

## 4. 数据模型（计划）

| 实体 | 关键字段 | 说明 |
|---|---|---|
| `source_record` | id, kind, occurred_at, participants, text, hash | 原始记录（化名后） |
| `extraction_run` | id, model, prompt_version, schema_version, status, cost | 一次抽取批次 |
| `assertion` | id, run_id, type, subject, predicate, object, confidence, evidence | 最小事实 |
| `evidence_span` | assertion_id, record_id, start, end, quote | 可高亮回原文 |
| `entity` | id, kind(person/task/decision/position), canonical_name | 消解后的实体 |
| `entity_alias` | entity_id, alias, source | 别名候选与确认状态 |
| `edge` | id, src, dst, type, weight, evidence_id | 图边，统一存储 |
| `snapshot` | id, window_start, window_end, graph_hash | 不可变快照 |
| `issue` | id, snapshot_id, type, severity, nodes, evidence_ids | 风险项 |
| `suggestion` | id, issue_id, edit_ops, delta_metrics, cost_estimate | 建议与仿真结果 |
| `handover_item` | id, snapshot_id, departing, group, task_id, evidence_ids | 交接清单 |

## 5. 接口（计划）

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/records` | 导入记录（文本/文件） |
| POST | `/api/runs` | 触发抽取（可指定模型与提示词版本） |
| GET | `/api/runs/{id}/events` | SSE 进度与降级事件 |
| POST | `/api/snapshots` | 基于某次运行建快照 |
| GET | `/api/snapshots/{id}/graph` | 三张图的节点/边 |
| GET | `/api/snapshots/{id}/issues` | 风险项 + 证据 |
| POST | `/api/suggestions` | 生成建议并返回效果差值 |
| POST | `/api/handover` | 指定离职成员，生成清单 |
| GET | `/api/health` | 存活与模型可用性 |

## 6. 部署形态

- 开发：Vite dev server（5173）反代 `/api` 到 FastAPI（8000）。
- 演示/提交：多阶段构建，前端产物由 FastAPI 静态托管，**单进程单端口**；SQLite 文件随包携带。
- 回放：启动时加载预置快照，不触网、不调模型。
- 若省赛要求公网地址：仅部署脱敏演示数据 + 访问口令，不接真实组织数据。

## 7. 设计原则

1. **证据可追溯**：界面上任何一条结论都能展开到原文片段。
2. **数值由代码算**：模型只做抽取与措辞（ADR-0005）。
3. **人在环**：低置信度进确认队列；调整必须人工确认后生效。
4. **离线可演示**：回放模式是一等公民，不是补丁（ADR-0006）。
5. **默认本地**：真实数据不出机器；导出的演示包必须已脱敏。
6. **小样本诚实**：指标附置信区间或稳定性提示，不把小样本噪声包装成结论。

## 8. 降级路径

| 故障 | 表现 | 降级 |
|---|---|---|
| 模型 API 不可用 | 抽取请求失败 | 切回放快照；提示"当前为演示数据" |
| 抽取质量差 | 断言稀疏或置信度低 | 缩小时间窗、要求人工确认；界面标注覆盖率 |
| 图过大 | 前端卡顿 | 只渲染 k-core 或按风险过滤；提供表格视图 |
| 数据不足 | 指标不可计算 | 明确显示"数据不足"，不给结论 |

## 9. 相关文档

- 分析口径：`docs/20-architecture/analysis-model.md`
- 技术选型：`docs/20-architecture/tech-stack.md`
- 目录规则：`.agent/30-architecture/repo-layout.md`

# B-04 · 从中文记录中抽取哪些事实、字段边界如何界定

- 调研人：张至顺 · 0002
- 完成日期：2026-11-17（v0.3 修订：2026-11-18）
- 对应单子：B-04（P0 · 5 人日 · 建议 数据/抽取）
- 状态：草稿（待队长评审）
- 版本：v0.3
- 用途与范围：确定抽取 schema v0.1 的字段与边界；**不含**抽取实现、提示词、评测协议（评测见 B-05）。

**变更记录**

| 版本 | 日期 | 改了什么 | 为什么 |
| --- | --- | --- | --- |
| v0.1 | 2026-11-17 | 初稿：结论、九个问题、字段表、十条边界、映射表 | 首版交付 |
| v0.2 | 2026-11-18 | ①§2 重写：加"核实级别"列，9 条扩到 19 条，逐条摘原句/页码；②新增 §6.1"只写核实过的对照"；③§8 增两条、改两条；④版本号与变更记录 | 上一版 9 条来源里 8 条实际只到"题录级"，却按已核实使用，违反规范 3.3 |
| v0.3 | 2026-11-18 | 删除合成的 20 条"真实记录"，边界案例迁到 `B-04-boundary-cases.jsonl` 并标 `origin: constructed`；§1-5、§5、§9、§10 与复现命令随之更新 | 合成数据不允许占"真实记录"的位置（任务单 §2.2-1、规范 3.3）|

> 读法：§1 是结论，§3 是九个问题的逐个回答，§4 是字段表（写代码时查这里），§5 是十条最难的边界案例，§6 是和外部的换算表。不想读全文的话，读 §1 与 §5。

---

## 1. 结论

1. **分类看的不是"这句话像什么"，而是"这句话让谁、在什么时候、对什么负责"。** 一句"这块我来吧"是承诺不是待办，因为它自己认领了 owner；一句"这块得有人弄"是待办，因为 owner 缺失。判据是归属，不是措辞。
2. **所有"说不清"的地方都不许猜，改用一个状态字段把它记下来，再进人工队列。** 具体是 `Actor.status`（known / ambiguous / missing / group）、`TimeRef.unresolved_reason`、`confidence` 三档、`review.needs_human`。这样错误是**可见的**，而不是被平均掉。
3. **一句话可以同时是"事实"和"态度"**：`polarity`（肯定/否定）与 `modality`（断言/假设/引用/玩笑/转述）是两条独立轴。"不需要做 X"是 negated 的任务，不能当成"没有任务"删掉。
4. **依赖只存一个方向**（本条 `depends_on` 目标），且必须能落到"前置、资源、审批、信息"四类之一——中文里的"等""走完""批了再说""回头问一下"分别落在这四类，混在一起就没法算关键路径。
5. 交付物：`packages/shared/extraction.schema.json` v0.1 + `data/samples/B-04-boundary-cases.jsonl`（10 条边界案例，`origin: constructed`）+ `scripts/check-b04-samples.py`（17 条规则 + 来源守卫，当前 10/10 通过）。**20 条真实记录尚未产出**——原 v0.1 里的 20 条是我合成的，已于 2026-11-18 删除，见 §10。

---

## 2. 证据

**核实级别**（本表最重要的列，别跳过）：

| 级别 | 含义 | 允许怎么用 |
| --- | --- | --- |
| **A** | 读到了正文，且下面摘了原句 | 可以支撑结论 |
| **B** | 只读到摘要/前言/文档页，没到给出定义的那一段 | 只能支撑"方向"，不能支撑"字段怎么定" |
| **C** | 只看到题录、标题或二手转述，正文没拿到 | **只能列为线索，不能当依据**；须写明为什么拿不到 |
| **无源** | 没有任何来源 | 写清是工程约定 |

| 编号 | 类型 | 内容 | 来源链接 | 级别 | 原句 / 位置 |
| --- | --- | --- | --- | --- | --- |
| E-01 | 官方文档 | Jira 的 issue link 是"关系对"，方向由 link type 承担，两端各存一条 | https://developer.atlassian.com/cloud/jira/platform/issue-linking-model/ | **A** | `{"name": "Blocks", "inward": "is blocked by", "outward": "blocks"}`；`{"name": "Depends", "inward": "is depended on by", "outward": "depends on"}`；"Jira issue links are bidirectional, however, the semantics of each direction is only interpretable at the user interface level and not at the API level." |
| E-02 | 官方文档 | 工作项关联的操作口径（正文由 JS 渲染，只拿到标题与导航） | https://support.atlassian.com/jira-software-cloud/docs/link-issues/ | **C** | 拿不到原因：页面主体由 JS 异步渲染，`curl` 与 `web_fetch` 都只返回骨架 HTML。内容与 E-01 重叠，仅作背景 |
| E-03 | 行业文章（正文） | RACI 四角色定义，且强调"问责者只能有一个" | https://quire.io/blog/p/raci-daci-rapid-ownership-frameworks.html | **A** | "RACI stands for Responsible, Accountable, Consulted, Informed. It answers "who's doing what" on a task or a deliverable."；"Accountable: the person who owns the outcome. One name, not three." |
| E-04 | 官方 playbook（正文） | DACI：把"驱动者"与"拍板者"分开，拍板者唯一 | https://www.atlassian.com/team-playbook/plays/daci | **A** | "D = Driver: The person responsible for corralling stakeholders…"；"A = Approver: The one person (yes: one!) who makes the decision." |
| E-05 | 咨询机构文章（正文） | RAPID 五角色，且 Input 者无否决权 | https://www.bain.com/insights/decisions-who-does-what/ | **A** | "RAPID is an acronym … for Input, Recommend, Agree, Decide and Perform"；"They have the right to provide input to a recommendation but not to veto it." |
| E-06 | 标准（PDF 正文） | CRediT 贡献者角色分类：14 类固定枚举 | https://zenodo.org/records/7640720/files/NISO+.pdf | **A** | 18 页 PDF，第 1 页列出 14 个角色名：Conceptualization / Data Curation / Formal Analysis / Funding Acquisition / Investigation / Methodology / Project Administration / Resources / Software / Supervision / Validation / Visualization / Writing – Original Draft / Writing – Review & Editing |
| E-07 | 标注指南（PDF 正文） | AMI 会议语料的"决策—讨论"分段规则 | https://groups.inf.ed.ac.uk/ami/corpus/Guidelines/decision_annotation-boundary-v1.4.pdf | **A** | 7 页 PDF，标题 *Coding Instructions for Decision Discussion Segmentation of the AMI Meeting Corpus (Version 2.3), June 18, 2007*（p1）；每场会平均约 5 个决定、每个决定 1–3 段讨论；多个决定挤在同一时段时用**层级标注**（一个父段包多个子决定） |
| E-08 | 论文（会议，PDF 正文） | MRDA（ICSI 会议语料）的标签体系：一句话一个 general tag + 若干 specific tag | https://aclanthology.org/W04-2319.pdf | **A** | 4 页 PDF（p1–p2）：11 种 general tag（如 statement / question / backchannel / disruption）＋ 39 种 specific tag，另有 adjacency pair 关系；全文 18 万+ 标签、72 小时会议、75 场会 |
| E-09 | 论文（arXiv 正文 + 仓库 README） | QMSum：会议问答语料的字段结构与"证据片段"表示法 | https://arxiv.org/abs/2104.05938 、https://github.com/Yale-LILY/QMSum | **A** | JSON 四组字段：`meeting_transcript[{speaker, content}]`、`topic_list[{topic, relevant_text_span:[[s,e],…]}]`、`general_query_list[{query, answer}]`、`specific_query_list[{query, answer, relevant_text_span}]`；1,808 对 / 232 场会；**span 用"第几句"而不是字符偏移** |
| E-10 | 论文（预印本，未经同行评审） | OSynth：合成会议数据 + 隐真值状态，人类辨伪准确率仅 56% | https://arxiv.org/abs/2610.29319 | **B** | 只读到摘要页：570 小时合成会议、latent ground-truth state、人类分辨真假仅 56%。正文未读，故只作"合成数据不等于标注语料"的提醒，不作字段依据 |
| E-11 | 官方文档（HTML 正文） | OpenProject 工作包之间的关系类型 | https://www.openproject.org/docs/user-guide/work-packages/ | **A** | `curl` 得 207,965 字节 HTML，去标签后命中六组：`relates` / `precedes`-`follows` / `duplicates`-`duplicated by` / `blocks`-`blocked by` / `includes`-`part of` / `requires`-`required by`，另有 parent-child 层级 |
| E-12 | 国际标准（PDF 正文） | DMN 1.5 决策表的结构：输入条目、输出条目、规则、命中策略 | https://www.omg.org/spec/DMN/1.5/PDF | **A** | 250 页 PDF，§8 决策表（PDF p74，正文页码 66）："The list of rules expresses the logic of the decision. For a given set of input values, the matching rule (or rules) indicate the resulting value for the output name. If rules overlap, multiple rules can match, and a hit policy indicates how to handle the multiple matches."，并定义 disjoint / overlapping / 'irrelevant' |
| E-13 | 论文（期刊，PDF 正文） | 中文否定与推测的语料标注：否定与推测是两套独立标注 | https://journal.hep.com.cn/fcs/EN/PDF/10.1007/s11704-015-5101-2 | **A** | 17 页（Zou / Zhou / Zhu, *Front. Comput. Sci.* 2015）；摘要："Identifying negative or speculative narrative fragments from facts is crucial for deep understanding on NLP"；语料由三个来源子集构成，标注否定/推测的 cue 与 scope |
| E-14 | 工具文档 | Duckling 的中文 time 维度可解析哪些时间说法 | https://duckling.leovan.tech/dimension/time/ | **B** | 读到了维度说明页，未读中文规则实现；只用于"相对时间要靠规则+锚点"的方向性支持 |
| E-15 | 工具报错页 | SUTime 正则不支持中文（负向依据：中文时间归一必须自写） | https://stanfordnlp.github.io/CoreNLP/sutime.html | **B** | 文档说明 SUTime 的规则基于英文表达；未逐条验证中文输入，故标 B |
| E-16 | — | "转述他人话"在中文里的处理 | 无 | **无源** | 未找到可引用的文献；本单按工程约定处理（`modality=quoted` + 进人工队列），不做学术声称 |
| E-17 | 厂商社区帖 | RAID（Risks / Actions / Issues / Decisions）日志 | https://www.wrike.com/blog/raid-log/ | **C** | 只有厂商博文，未见规范或教材级来源；仅作术语提示 |
| E-18 | 出版社书目 | DSM（设计结构矩阵）方法 | https://direct.mit.edu/books/monograph/3361/ | **C** | 只有书目页，正文付费墙；DSM 的"行列对应活动、格子表示依赖"属通行说法，但本单没拿到原书页码，故 §6 只用其结构直觉、不作字段依据 |
| E-19 | 仓库内文档 | `docs/20-architecture/analysis-model.md` 三图与指标口径；`docs/30-research/briefs/B-05-eval-protocol.md` 标注单位与 κ | 仓库内 | — | 不涉外，作为本单的约束来源 |

> 使用限制（保留并收紧）：
> ① 能支撑"关系要存单向"的是 E-01（A）+ E-11（A）；**不能**用它们支撑"中文里怎么说"。
> ② 中文说法（"等接口定稿""走完审批""大家弄一下"）**没有**语料统计支撑，属工程判断，§8-3 记着这件事。
> ③ 上一版把 9 条来源全当已核实，其中 8 条实际只到 C 级——这是本次修订的主因，逐条见上表的"级别"列。

> 核实方法（写下来，下一单照做）：能 `curl` 到的先 `curl` 原始 HTML 再用正则去标签（JS 渲染页也能拿到首屏数据）；PDF 一律下载后用 `pypdf` 抽文本、按关键词定位页码；抓不到正文就标 C 并写明原因，**不许把"搜到了标题"当成"读过了"**。

---

## 3. 九个问题

### 3.1 一条记录里，哪些句子是决定、待办、承诺、状态更新、闲聊？

先看两张表。第一张是"这句话给组织留下了什么"，第二张是"留下的东西归谁"。

| 类型 | 留下的东西 | 必须有的成分 | 典型说法 | 进图吗 |
| --- | --- | --- | --- | --- |
| `decision` | 一个约束（以后都这么做） | 结论 + （可选）拍板人 | "定了，下周开始双人评审"、"就按 B 方案" | 是（`G_work` 里挂 approver） |
| `task` | 一件要做的事 | 动作 + 对象 | "把接口文档补一下"、"周五前出原型" | 是（`G_work` 里挂 owner） |
| `commitment` | 一件要做的事，且**自己认领了** | 动作 + 第一人称承担 | "我来写"、"这块我负责" | 是（owner=说话人，`source=self_committed`） |
| `status_update` | 一个事实（进度变了） | 对象 + 状态 | "登录页做完了"、"接口联调卡在权限" | 是（改 `task_state`，本身不新建任务） |
| `discussion` | 一个候选（还没定） | 观点/倾向 | "要不要考虑拆成两个"、"我觉得可以先这样" | **否**（`graph_eligible=false`） |

**闲聊不是第六类。** 它不产生断言，只产生一条 `skipped`，理由从六个里选一个（`chitchat` / `greeting` / `meta_instruction` / `duplicate` / `unverifiable_reference` / `no_assertion`）。这样"没抽出来"和"抽错了"能分开统计——这是 B-05 六类错误里"漏抽"的分母。

判断顺序（一次只看一句话，别跳步）：

```
这句话有没有让某件事的状态发生变化？
├─ 没有 → 是在讨论可能性吗？
│        ├─ 是 → discussion（graph_eligible=false）
│        └─ 不是 → skipped（选一个理由）
└─ 有 → 变的是"以后都这么办"还是"这件具体的事"？
         ├─ 以后都这么办 → decision
         ├─ 这件具体的事，且说话人自己认领 → commitment
         ├─ 这件具体的事，别人做 → task
         └─ 只是报告"已经到哪一步" → status_update
```

### 3.2 "决定"和"讨论过/可以考虑"怎么分？没有结论词怎么办？

**判据不是有没有"决定"两个字，而是有没有"约束生效"的信号。** 三个信号，命中任一即可判 `decision`：

| 信号 | 例子 | 判定 |
| --- | --- | --- |
| ① 明确的结论词或时间起点 | "定了"、"就这么办"、"从下周起"、"拍板了" | `decision` + `decision_state=ratified` |
| ② 有人被指派去执行这个结论 | "那 A 你去改流程" | `decision`（结论）+ 另一条 `task`（执行） |
| ③ 结论出现在"决议/待办/会议结论"这类结构化段落 | 纪要里的「决议」小节 | `decision`，`confidence=0.9` |

三条都不中，但语气明显偏向某一方案（"我觉得还是 A 好"），判 `discussion` + `decision_state=proposed`，**不要**判 ratified。
如果一句话既像讨论又像决定（"要不就这样吧，行，那就这样"），判 `decision` 但 `confidence=0.3` + `review.reason=boundary_case`，进人工队列。

> 这一条最容易出的错是**把"讨论过的方案"当成"已定的决定"**。后果不是难看，是分析图里多出一条根本不存在的约束，后面所有"结构风险"都建在它上面。

### 3.3 "待办"和"承诺"的区别？没有责任人的待办要不要留？

区别只有一个：**谁认领的**。

- `task`：别人给的、或没人认领的。owner 可以是 known / ambiguous / **missing**。
- `commitment`：说话人自己认领（"我来"、"我负责"、"我今晚弄"）。owner 必须是 known，且 `source=self_committed` 或 `volunteered`。

**没有责任人的待办必须保留**，`Actor{role:owner, status:missing}`，并进待认领队列（`review.reason=missing_owner`）。

理由：无主待办恰恰是本产品要暴露的东西——它是"断档"的最早形态。删掉它，看板会显示"一切正常"，而这正是现状工具的问题。留下的代价只是多一条待认领的噪音，删掉的代价是**看不见的风险**。

### 3.4 多个责任人、责任人缺失、"大家"怎么办？

一个任务**只有一个 owner 位置**，其余都是 `contributor`。三种异常各有一个状态，不许混：

| 情形 | 写法 | 是否进图 | 是否进人工队列 |
| --- | --- | --- | --- |
| 明确一个人 | `{role:owner, status:known, persons:[P01]}` | 是 | 否 |
| 多候选（"A 或 B 都行"） | `{role:owner, status:ambiguous, persons:[P01,P02]}`（两个并列，**不强迫选一个**） | 否，先挂起 | 是（`ambiguous_owner`） |
| 没人认领 | `{role:owner, status:missing, persons:[]}` | 否 | 是（`missing_owner`） |
| "大家" | `{role:owner, status:group, persons:[], group_scope:team|present|unspecified}` | 否 | 是（`boundary_case`） |

`group_scope` 的作用是把"大家"拆细：`team`=全员、`present`=在场的人（用 `record.participants` 判定）、`unspecified`=范围不明。
**"大家"绝不能映射到具体某个人**——这是最容易犯又最伤人的错：把"大家一起弄一下"记成张三负责，责任就凭空转移了。

### 3.5 依赖的方向与类型

方向只有一种写法：**本条 `depends_on` 目标**（`direction` 是常量，禁止存反向字段）。理由是 Jira 的教训（E-01）：两端各存一条关系，一旦一端改了另一端就烂掉；我们只存一条，反向由图算法算。

四类依赖，用"卡在哪"来分，不用"是什么词"来分：

| 类型 | 卡在哪 | 中文常见说法 | 例子 |
| --- | --- | --- | --- |
| `precedence` | 前一步没做完 | 先…再…、等…完了、做完 X 才能 Y、等 X 上线 | "等接口文档定稿再写前端" |
| `resource` | 没人/没预算/没设备 | 抽不出人、等排期、预算还没批、机器不够 | "这周没人力，下周再说" |
| `approval` | 等签字 | 等队长点头、走审批、要老师确认 | "方案要等老师确认" |
| `information` | 等消息/数据 | 等回复、等报价、等对方给数据、回头问一下 | "等他回我再说" |

`strength`：`hard`=没有它做不了（进 `G_dep`，参与关键路径）；`soft`=最好有但不挡（如"顺便问一下"）。软依赖单独统计，不进硬依赖图——否则关键路径会被"顺便"撑爆。

目标怎么填：库内已有该任务 → `target_task_id`；还没有 → `target_label`（文字指称，最长 60 字）。两者至少填一个。

成环（A 依赖 B、B 依赖 A）不删边，标 `review.reason=dependency_cycle` 交人判断——现实里成环常常是真的（两个模块互相等对方先定接口），删掉反而失真。

### 3.6 时间怎么归一

五档 `kind`，**`raw` 永远逐字保留**（这是证据，也是复核入口）：

| kind | 例子 | 归一做法 | 不归一的条件 |
| --- | --- | --- | --- |
| `absolute` | 11 月 20 日、2026-11-20 | 直接落 `start` | — |
| `relative` | 下周五、三天后 | 用 `record.captured_at` 当锚点换算 | 没有采集时间 → `unresolved_reason=no_anchor` |
| `event_ref` | 下次开会前、等评审完 | 只能等事件定了再算 | 事件未定 → `unresolved_reason=ambiguous_ref` |
| `fuzzy` | 尽快、月底前、这阵子 | 能给区间给区间（`start`/`end`） | 给不出 → `unresolved_reason=vague_word` |
| `none` | （原文没提时间） | `raw=""` | — |

三条铁律：①**不许猜日期**，猜出来的日期会变成考核依据；②相对时间必须有锚，锚点写在 `anchor`（形如 `R-003@2026-11-17`）；③两条记录对同一件事给了冲突时间 → `unresolved_reason=conflict`，进人工队列。

### 3.7 否定、假设、转述、玩笑怎么处理

`polarity` 和 `modality` 是两条独立轴，**四种组合都要能表达**：

| 原话 | polarity | modality | graph_eligible | 说明 |
| --- | --- | --- | --- | --- |
| "不需要做灰度" | negated | asserted | false | 是决定，但内容是"不做"，不能当成"有个灰度任务" |
| "如果下周还没定，就先上简化版" | affirmative | hypothetical | false | 假设句，条件没发生就不是任务 |
| "队长说让我们先别动" | affirmative | quoted | false（待复核） | 引用他人，责任在队长不在说话人 |
| "行啊，我明天通宵搞定（笑）" | affirmative | joking | false | 玩笑，不能变成承诺 |

规则一句话：**`modality≠asserted` 或 `polarity=negated` 时 `graph_eligible=false`**，要进图必须人工把 `graph_eligible` 改成 true 并留 note。这样"AI 觉得算数"和"人确认算数"永远是两件事。

### 3.8 任务层级与跨记录合并的接口

这一单**不做**合并算法（R-06 做），只留接口，且只有三个字段：

- `parent_task_id`：父任务断言 id（做子任务时用）；
- `merge_key`：粗聚类键，`动作+对象+责任人口径+时间桶` 规范化后的字符串（最长 80 字），**不是唯一键**；
- `merged_into`：被合并进哪条。**被合并者保留，不删除**——删了就失去"同一件事说了三次"这个信号，而这个信号恰是"重复沟通"指标的原料。

跨记录的同一任务（周一"补接口文档"、周三"文档还没动"）靠 `merge_key` 相同 + 人工确认合并，不靠向量相似度自动合。

### 3.9 "不确定"和"多候选"怎么表达

三层，从轻到重：

1. `confidence` 只有三档：**0.3 / 0.6 / 0.9**。不许填 0.72 这种精度——评一致率时精度是假的，三档才能算 κ，也方便 bootstrap。
2. `Actor.status`：多候选用 `ambiguous`（并列 persons），缺失用 `missing`，群体用 `group`。**永不强迫选一个**。
3. `review`：`needs_human=true` + `reason`（六个之一）。低置信、非断言、多候选 owner、缺失 owner、依赖成环、边界案例，六种情况都必须进队列。

反过来，**禁止"其他/杂项"这类兜底值**。`scripts/check-b04-samples.py` 会扫所有 enum，出现兜底词直接判失败——兜底值会让"未知"从统计里消失，而"未知的比例"本身是最重要的指标之一。

---

## 4. 字段说明表

> 只列抽取结果里需要人判断的字段；纯结构字段（id、计数）略。完整约束以 `packages/shared/extraction.schema.json` 为准。

| 字段 | 含义 | 取值 | 必填 | 不确定时怎么填 | 依据 |
| --- | --- | --- | --- | --- | --- |
| `assertion.type` | 断言类别 | decision / task / commitment / status_update / discussion | 是 | 拿不准 decision 还是 discussion → discussion + `decision_state=proposed` | §3.1、§3.2 |
| `assertion.statement` | 归一化一句话（4–200 字） | 自由文本 | 是 | 补全省略成分但不改语义；原文进 `evidence.quote` | §3.1 |
| `assertion.evidence` | 原文证据 | `record_id` + `span_start` + `span_end` + `quote` | 是 | 找不到原句 → 这条断言不该存在 | §4.1 证据优先 |
| `assertion.polarity` | 肯定/否定 | affirmative / negated | 是 | 出现"不用/别/取消"→ negated，`graph_eligible=false` | §3.7 |
| `assertion.modality` | 断言方式 | asserted / hypothetical / quoted / joking / reported | 是 | 有"如果/假如"→ hypothetical；有"他说"→ quoted | §3.7 |
| `assertion.graph_eligible` | 是否进分析图 | boolean | 是 | 非 asserted 或 negated 一律 false | §3.7 |
| `assertion.actors[].role` | 角色 | owner / contributor / approver / backup / mentioned | 是 | 只是被提到 → mentioned（**不入图**） | E-03～E-06 |
| `assertion.actors[].status` | 归属状态 | known / ambiguous / missing / group | 是 | 多候选→ambiguous（并列）；无人→missing；大家→group | §3.4 |
| `assertion.actors[].persons[]` | 候选人 | `P01`… + `confidence` | known=1 个；ambiguous≥2；其余空 | 不强迫选一个 | §3.4 |
| `assertion.actors[].group_scope` | 群体范围 | team / present / unspecified | 仅 group | 判不出范围 → unspecified | §3.4 |
| `assertion.actors[].source` | 归属来源 | explicit / inferred / self_committed / volunteered | 否 | inferred 必须在 note 写推断依据 | §3.3 |
| `assertion.time.kind` | 时间类型 | absolute / relative / event_ref / fuzzy / none | 是 | 说不清 → fuzzy + `unresolved_reason` | §3.6 |
| `assertion.time.raw` | 原文时间表达 | 逐字字符串 | 是 | 原文没提 → 空串 | §3.6 |
| `assertion.time.granularity` | 归一粒度 | day / week / month / quarter / null | 否 | 判不出 → null | §3.6 |
| `assertion.time.anchor` | 相对时间锚点 | `R-003@2026-11-17` | 相对/事件类必填 | 没锚点 → 不归一，填 `no_anchor` | §3.6 |
| `assertion.time.unresolved_reason` | 未归一理由 | no_anchor / ambiguous_ref / vague_word / conflict / null | 视情况 | 必须选其一，不许留空硬猜 | §3.6 |
| `assertion.task_state` | 任务状态 | proposed / active / done / cancelled / null | 仅 task、commitment | 只知"在做"→ active | §3.1 |
| `assertion.decision_state` | 决定状态 | proposed / ratified / reversed / superseded / null | 仅 decision | 没结论词 → proposed | §3.2 |
| `assertion.dependencies[].direction` | 依赖方向 | 常量 `depends_on` | 是 | 只有一种写法 | §3.5、E-01 |
| `assertion.dependencies[].kind` | 依赖类型 | precedence / resource / approval / information | 是 | 判不出 → information（最常见）并进人工 | §3.5 |
| `assertion.dependencies[].strength` | 强弱 | hard / soft | 是 | 拿不准 → soft（宁可不进关键路径） | §3.5 |
| `assertion.dependencies[].target_*` | 前置目标 | `target_task_id` 或 `target_label`（≥1 个） | 是 | 库内没有该任务 → label | §3.5 |
| `assertion.parent_task_id` | 父任务 | `A-0001` / null | 否 | 层级不明 → null，不做深度推断 | §3.8 |
| `assertion.merge_key` | 粗聚类键 | ≤80 字规范化串 | 否 | 只对可能重复的任务填 | §3.8 |
| `assertion.merged_into` | 并入目标 | `A-0001` / null | 否 | 合并由 R-06 填 | §3.8 |
| `assertion.confidence` | 置信度 | 0.3 / 0.6 / 0.9 | 是 | 只有三档 | §3.9 |
| `assertion.review.needs_human` | 进人工队列 | boolean + reason | 是 | 六种情况必须 true | §3.9 |
| `skipped[].reason` | 不抽的理由 | chitchat / greeting / meta_instruction / duplicate / unverifiable_reference / no_assertion | 是 | 六选一，禁兜底 | §3.1 |
| `run.offset_unit` | 证据偏移单位 | 常量 `unicode_code_point` | 是 | 前端 UTF-16 下标要换算 | §4.1 |
| `person.identity_status` | 身份状态 | roster_confirmed / inferred / unresolved | 是 | 只有"他/那边" → unresolved | §3.4 |

### 4.1 两条实现约定（容易踩坑，写在这里让前端也别踩）

- **证据偏移按 Unicode 码位计**（Python 字符串索引）。JS 的 `slice` 用 UTF-16，遇到 emoji 会偏 1，前端负责换算，不许在 schema 里存两套偏移。
- **`evidence.quote` 与偏移必须一致**：机器校验偏移，人核对 quote。二者不一致视为数据错误，不是"小瑕疵"。

---

## 5. 十条边界案例（对应 `data/samples/B-04-boundary-cases.jsonl` 的 E01–E10，全部标 `origin: constructed`）

| 编号 | 情形 | 原话（化名） | 期望写法 | 为什么这样定 |
| --- | --- | --- | --- | --- |
| E01 | 多责任人 | "这个 A 和 B 一起弄" | owner=ambiguous（P01,P02）+ contributor 各一条 | 强行指定一个人会让另一人的贡献消失 |
| E02 | 无责任人 | "这块得有人弄一下" | owner=missing，保留断言 | 无主待办是最早的断档信号 |
| E03 | 否定 | "不用做灰度了" | decision + negated + graph_eligible=false | 否定的是任务内容，不是"没有这件事" |
| E04 | 假设 | "如果下周还没定就先上简化版" | task + hypothetical + graph_eligible=false | 条件未发生，进图会凭空多一条任务 |
| E05 | 跨记录同一任务 | 周一"补接口文档"、周三"文档还没动" | 两条断言 + 同一 `merge_key` | 合并靠 R-06 人工确认，不靠向量相似度 |
| E06 | 时间模糊 | "月底前吧" | fuzzy + start/end 区间 + granularity=month | 能给区间就给，别落到具体某天 |
| E07 | 依赖成环 | "前端等接口、接口等前端定字段" | 两条 depends_on + `dependency_cycle` 标记 | 现实里常是真的，删边反而失真 |
| E08 | 引用他人 | "队长说先别动" | quoted + review=needs_human | 责任在队长，不在说话人 |
| E09 | 玩笑 | "我明天通宵搞定（笑）" | commitment + joking + graph_eligible=false | 不把玩笑记成承诺 |
| E10 | 中英混用 | "先用 mock 挡一下，等 API 好了再接" | task + information 依赖 + `target_label="API"` | 术语不翻译、不丢，保留原词 |

10 条边界案例各带 `must_hold` 断言，跑 `python scripts/check-b04-samples.py` 可复现校验（10/10）。

> 这 10 条是**构造的**极端案例，用途是证明 schema 能表达它们，**不是**真实语料，不能用来算准确率。真实记录样本（`B-04-real-records.jsonl`，20 条）必须由人标注，尚未产出。

---

## 6. 与 RACI / Jira / DSM 的字段映射

答辩和导出都要用这张表：**我们的字段能换算成别人认识的东西**，反之不成立的部分也写清楚。

| 我们的字段 | RACI / DACI | Jira | DSM（设计结构矩阵） | 换算注意 |
| --- | --- | --- | --- | --- |
| `Actor.role=owner` | R（Responsible）/ DACI 的 Driver | Assignee | 行/列对应的人 | 我们允许 owner=missing，Jira 不允许 → 导出时落到"未分配" |
| `Actor.role=approver` | A（Accountable）/ DACI 的 Approver | （无原生字段，通常用自定义字段） | — | 这是 RACI 与 Jira 最大的缝：Jira 没有"拍板人"概念 |
| `Actor.role=contributor` | C（Consulted） | Watcher / 子任务 assignee | 参与格子 | Watcher 语义更弱，只能近似 |
| `Actor.role=backup` | — | （无） | — | RACI/Jira 都没有"备份人"，这是断档分析的关键字段 |
| `Actor.role=mentioned` | I（Informed） | Mention | — | 不得入图 |
| `type=task/commitment` | — | Issue（Task/Story） | 活动节点 | commitment 在 Jira 里无对应，只能靠 label |
| `dependencies[].kind=precedence` | — | `blocks` / `is blocked by` | 依赖格子（下三角） | 我们只存单向，导出 Jira 时补反向 |
| `dependencies[].kind=approval` | A 的隐含前提 | （无原生，需插件） | — | 需要说明"我们比 Jira 多一类" |
| `dependencies[].kind=resource/information` | — | （无原生） | — | Jira 只有"阻塞"，不区分原因 |
| `decision` | — | （无原生，惯例用 Comment/Confluence） | — | 决定的留痕是现状工具最大的空白 |
| `confidence` / `review` | — | （无） | — | 我们的"可见的不确定"在外部工具里没有位置 |

一句话：**RACI 有角色没方向，Jira 有方向没角色，DSM 有结构没语义。** 我们三样都要，所以只能自建，靠这张表保证能导出去。

### 6.1 只写核实过的对照（级别见 §2）

上面那张表是**设计意图**；这一节是**已经读到正文、能指出出处**的部分。两者混着写会让人以为整张表都有依据——上一版就是这么出问题的。

| 外部结构（已核实） | 出处 | 对应我们的 | **不能**对应的 |
| --- | --- | --- | --- |
| Jira：`blocks` / `is blocked by`、`depends on` / `is depended on by` 成对出现，方向只存在于 UI 语义 | E-01（A） | `dependency{direction: depends_on, kind: precedence}`，导出时补反向 | Jira 不区分"为什么阻塞"；我们的 `resource/approval/information` 三类在 Jira 里没有位置 |
| OpenProject 六组关系：`relates` / `precedes`-`follows` / `duplicates`-`duplicated by` / `blocks`-`blocked by` / `includes`-`part of` / `requires`-`required by` | E-11（A） | `blocks`→`precedence`；`requires`→`resource` 或 `information`；`includes/part of`→`parent_task_id`；`duplicates`→`merged_into` | `relates`（泛相关）我们**不收**——它不进关键路径、也不进断档分析，收了只会稀释"依赖"这个词 |
| DMN 决策表：`rules` 每条由输入条目→输出条目，规则重叠时由 `hit policy` 决定取哪条 | E-12（A） | 我们的 `decision` 断言 = DMN 的一条 rule（条件在原文里、结论在 `statement`） | 我们**没有** hit policy：同一议题出现两个相反结论时，用 `decision_state=superseded/reversed` + 时间先后解决，而不是"命中策略"。这是有意的——组织里的决定是随时间被推翻的，不是同时求值的 |
| RACI：R/A/C/I 四角色，A 必须唯一 | E-03（A） | `owner`(R) / `approver`(A) / `contributor`(C) / `mentioned`(I) | RACI 的 A 是"对结果负责"，我们的 `approver` 是"签字放行"；两者在中文语境里常是同一人，但**不能默认等价**，导出时要提示 |
| DACI：Driver 与 Approver 分开，Approver 唯一 | E-04（A） | Driver≈`owner(source=volunteered)`；Approver=`approver` | DACI 没有 `backup`；我们的断档分析必须靠 `backup`，所以这一列在导出时为空是**预期**，不是缺失 |
| RAPID：Input / Recommend / Agree / Decide / Perform 五角色，Input 无否决权 | E-05（A） | Recommend≈`owner`；Decide≈`approver`；Input/Agree≈`contributor`（`mentioned` 不算 Input） | 我们的 `contributor` 是个大口袋，装不下"同意权"与"提供信息"的区别——需要时用 `source` + note，不新增角色 |
| CRediT：14 类贡献角色，固定枚举 | E-06（A） | 只取 5 类，因为本产品只关心**结构性责任**（谁做/谁签/谁备/谁知情），不关心"谁做的数据分析" | CRediT 的粒度是"贡献类型"，我们的是"责任位置"；两者不是同一维度，不可互相换算 |
| AMI：以"决策—讨论"为单位切段，一个决定 1–3 段讨论，决策密集处用层级 | E-07（A） | 分段单位仍是**断言**（比"决策段"更细）；密集处用 `parent_task_id` 建层级 | AMI 的切段面向"讨论过程分析"，我们面向"责任与依赖"，同一段话可能切出 1 条 decision + 2 条 task，这是正常的 |
| MRDA：一个话轮 1 个 general tag（11 种）+ 若干 specific tag（39 种）+ adjacency pair | E-08（A） | `type`（单值，对应 general）+ `polarity/modality`（多轴，对应 specific 的一部分） | adjacency pair（问答配对）我们**不做**：本单只抽事实，不做对话结构分析 |
| QMSum：`relevant_text_span` 用**话语序号区间**表示证据 | E-09（A） | 我们用**字符码位**区间 + `quote` 原文 | 话语序号依赖"先分好句"，而我们的输入是自由文本；两套偏移不可混用 |
| 中文否定与推测分两套独立标注（cue + scope） | E-13（A） | `polarity` 与 `modality` 分成两条轴，正是这个结论 | 我们不做 cue/scope 的细粒度标注——只判"这条断言整体是否定/假设"，scope 留给人工 |
| RAID 四类（Risks/Actions/Issues/Decisions） | E-17（**C**） | 仅作术语提示：`decision` 与 `task` 分开记，在业界已是惯例 | 来源太弱，**不许在答辩里当依据引用** |
| DSM：行列对应活动、格子表示依赖强度 | E-18（**C**） | 仅作"依赖可以做成矩阵"的直觉 | 没拿到原书页码，§6 主表的 DSM 一列只能算设计参照，不算文献依据 |


---

## 7. 对设计的影响

1. **R-03（抽取）**：输出直接是 schema v0.1 的 `assertions[]`；提示词必须按 `type/polarity/modality` 三轴分别约束，不能只让它"判断类型"。
2. **B-05（评测）**：字段级一致率的字段清单就是 §4 的表；`confidence` 三档是 κ 计算的前提，若改成连续值，κ 就得改方法。
3. **R-06（合并）**：只依赖 `merge_key`、`parent_task_id`、`merged_into`，不依赖向量相似度。
4. **R-07（指标）**：`G_dep` 只用 `strength=hard` 的边；`soft` 单独统计。`DEP_CYCLE` 不删边，只在指标里排除并单列。
5. **F1（前端）**：需要展示"待认领队列"（`missing_owner`）、"多候选"（`ambiguous_owner`）、"引用待确认"（quoted）三个入口——它们不是错误提示，是产品的主界面之一。
6. **隐私**：`persons[]` 只存 `P01` 代号；`evidence.quote` 里可能含真名，入库前必须替换（AGENTS.md 硬规则），这一步在 R-02 做，不在本单。

---

## 8. 分歧与未解决

| # | 问题 | 现状 | 需要谁定 |
| --- | --- | --- | --- |
| 1 | 三人独立标注的一致率（验收要求 ≥0.7）**未做** | 本单只产出 schema 与样本，一致性必须真人标注，模型自评不算数 | 队长安排 3 人各标 20 条 |
| 2 | AMI 判"决定"的口径与本单 §3.2 的三信号不完全一致 | AMI（E-07）用的是"讨论边界 + 共识达成"的过程信号，我们用的是"结论词/被指派/结构化段落"的语言信号；两者不冲突但不重合 | 在标注工作坊（S5）里用 3–5 条真实记录做对照，定哪套优先 |
| 3 | 依赖是否要第五类（"约定/契约"类，如"接口字段以文档为准"） | 暂归 `information` | 队长 / B-05 观察后定 |
| 4 | `commitment` 与 `task` 在导出的 Jira 里无法区分 | 靠 label 兜 | 导出需求方（答辩材料）定 |
| 5 | RAID（E-17）与 DSM（E-18）都只有 C 级来源 | §6.1 已标为"不得作为文献依据" | 答辩口径由队长定 |
| 6 | `type=status_update` 是否要单独成类（有意见认为可并入 task 的状态变更） | 暂保留，因为它承载"进度事实"而非"任务" | B-05 统计后再议 |
| 7 | 中文说法（"等接口定稿""走完审批""大家弄一下"）**没有**语料统计支撑 | 属工程判断，不是文献结论 | 若要写进论文，需自建小语料统计，见 B-05 |

---

## 9. 验收对照

| 验收标准（任务单） | 状态 | 证据 |
| --- | --- | --- |
| 3 人独立标注字段级一致率 ≥0.7 | **未完成** | 需真人标注，见 §8-1 |
| 10 条"必须能表达"案例全过，且不需临时加字段 | 通过 | `python scripts/check-b04-samples.py` → 边界案例 10/10 |
| 每个字段能回答"什么算对"，可直接交给 B-05 | 通过 | §4 字段表的"不确定时怎么填"列 + §5 边界表 |
| schema 无"其他/杂项"逃避字段 | 通过 | 检查器扫全部 enum，兜底词直接失败 |

---

## 10. 下一步

- [ ] 队长安排 3 人各标 20 条，算字段级一致率（本单唯一未完成项）
- [ ] B-05 按 §4 字段清单写评测脚本；`confidence` 三档写进提示词约束
- [ ] R-03 实现时，先用 `scripts/check-b04-samples.py` 校验模型输出格式，再谈准确率
- [x] 补读 AMI 决策标注指南（E-07，已读到正文）——结论：AMI 判"决定"用过程信号，与 §3.2 的语言信号不重合，见 §8-2
- [x] ~~重做标注样本~~ 已执行 S0（2026-11-18）：删除 `B-04-annotation-samples.jsonl`（S01–S20 为合成记录，误置于"真实记录"位置）；E01–E10 迁入 `B-04-boundary-cases.jsonl` 并标 `origin: constructed`；checker 增加来源守卫（缺 `origin` 或 kind/origin 错位即失败）
- [ ] 产出 `B-04-real-records.jsonl`：20 条真实脱敏记录，由成员人工标注（此步 AI 不能代劳）
- [ ] 若能拿到 `.agent/` 里的 ADR-0001~0006，核对本单是否与既定数据模型冲突
- [ ] C 级来源（E-02 / E-17 / E-18）要么补到 A，要么在答辩材料里删掉对应说法

---

## 附：怎么复现

```bash
# 校验 schema 与 10 条边界案例（不装任何第三方库）
python scripts/check-b04-samples.py

# 只看边界案例
python scripts/check-b04-samples.py --file data/samples/B-04-boundary-cases.jsonl
```

## 附：产出方式说明（AI 参与情况）

按《项目协作与开发规范》4.3「如实标注 Agent 参与」，本文件的产出方式如下：

| 项 | 内容 |
| --- | --- |
| 参与环节 | 资料检索与摘要（§2 证据表）、schema v0.1 字段草案、10 条边界案例初稿、`scripts/check-b04-samples.py`、本文档结构与初稿、v0.2 的证据级别复核与 §6.1 |
| 使用的工具 | 编码 Agent（DeepSeek 模型），通过终端读仓库文档、`curl` 抓网页原文、`pypdf` 抽 PDF 文本、写文件、跑本地校验脚本 |
| 人工核验方式 | ①逐条打开 §2 的链接与 PDF 页码，核对"原句"是否真实存在且未被引申；②本地运行 `python scripts/check-b04-samples.py` 复现 10/10；③对 §1 五条结论与 §5 十条边界规则能逐条复述；④对每个字段能回答"什么算对" |
| **未核验项（待核实）** | ①**C 级 3 条**：E-02（Jira 帮助页正文 JS 渲染拿不到）、E-17（RAID 仅厂商博文）、E-18（DSM 原书付费墙）；②**B 级 3 条**：E-10（OSynth 只读摘要）、E-14（Duckling 未读实现）、E-15（SUTime 未逐条验证中文）；③**无源 1 条**：E-16 转述处理属工程约定；④§3.5 四类依赖与 §3.6 时间归一的中文说法**无语料统计支撑** |
| 责任归属 | 本文档的结论由调研人负责，不以"AI 生成"作为免责理由（规范 3.1、3.3） |


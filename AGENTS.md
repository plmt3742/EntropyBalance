# AGENTS.md

本文件是 AI 编码代理进入本仓库的入口。人类协作者也建议先读一遍。

## 启动顺序

1. `.agent/CONTEXT.md` — 项目当前状态（唯一状态源）
2. `.agent/INDEX.md` — 任务 → 文件路由表
3. 按路由表读 **≤3** 个文件，不要通读仓库

`.agent/` 是本地工作记忆，已被 `.gitignore` 排除。若它不存在，说明本机未初始化这套上下文：**先问用户**，不要自行重建或猜测内容。

## 硬规则

- 不把真实人名、群聊原文、手机号、组织名写入任何被 Git 跟踪的文件。
- 不提交 `data/raw/`、`.env`、数据库文件、日志。
- 不声称"首个/唯一/发明了某指标"；不声称风险分数能预测离职或失败。
- 不把由模型生成的数字当作结论；指标与建议效果必须由代码计算（`.agent/10-decisions/ADR-0005-trust-boundary.md`）。
- 不引入新依赖、不改变目录职责、不改数据模型，除非先写 ADR。
- 不删除或跳过失败的测试；不吞异常；不用 `any`/`@ts-ignore`/`# type: ignore` 掩盖类型问题。

## 目录归属

| 要放的东西 | 位置 |
|---|---|
| 可公开的设计文档 | `docs/` |
| 内部决策与工作状态 | `.agent/`（不提交） |
| 后端逻辑 | `apps/api/app/` |
| 前端页面与组件 | `apps/web/src/` |
| 跨端契约 | `packages/shared/` |
| 脱敏样例 | `data/samples/` |
| 标注集 | `data/golden/` |
| 原始数据 | `data/raw/`（永不提交） |

细则见 `.agent/30-architecture/repo-layout.md`。不确定时先查 `.agent/50-file-map/FILES.md`，不要新开平行目录。
团队协作与分工规则见 `docs/02-workflow.md`。

## 命令

代码骨架尚未建立，以下为约定命令，建成后必须可用：

```bash
# 前端（apps/web）
npm install
npm run dev
npm run build
npm run test

# 后端（apps/api）
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest

# 上下文维护（任何改动后）
node .agent/tools/gen-file-tree.mjs
node .agent/tools/check-context.mjs
```

不要发明未在 `package.json` / `requirements.txt` 中定义的命令。

## 收工义务

- 更新 `.agent/CONTEXT.md` 的「现在 / 下一步 / 未决问题」。
- 在 `.agent/20-changes/CHANGELOG.md` 追加一行。
- 结构性改动后重生成文件树，并补 `.agent/50-file-map/FILES.md`。
- 跑 `check-context.mjs`，必须退出码 0。

## 代码约定

- TypeScript `strict`；Python 用类型标注，ruff 检查。
- 指标与仿真写成纯函数，放 `apps/api/app/analysis/`，必须有单测。
- 前端不实现指标计算；所有数字来自 API。
- 文档用中文；标识符、字段名、commit message 用英文。
- 提交信息：`<type>(<scope>): <subject>`，例如 `feat(extract): add evidence span validation`。

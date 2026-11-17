# apps/api

Python 服务：数据导入、LLM 抽取、消解、图构建、分析与仿真、HTTP 接口、静态托管前端产物。

状态：**未开始**。目录结构见 `.agent/30-architecture/repo-layout.md`。

## 计划结构

```text
app/
  main.py          FastAPI 实例，挂载 /api 与前端静态文件
  api/             路由：只做参数校验与编排
  ingest/          读取与规范化（txt/md/docx/导出文件）
  privacy/         化名、映射表、导出脱敏
  extract/         模型调用、schema 校验、修复、置信度
  resolve/         别名消解、任务去重
  graph/           三张图的构建与查询
  analysis/        指标、风险、仿真（纯函数，必须有单测）
  advise/          建议生成与效果重算
  store/           SQLAlchemy 模型与 Alembic 迁移
  prompts/         版本化提示词（带元数据头）
tests/             pytest
```

## 约定

- 依赖写 `requirements.txt`；不引入未登记的包。
- 分析层不得读文件、不得调网络；输入是普通数据结构。
- 所有模型输出先过 Pydantic 校验，再做证据偏移校验。
- 日志只记 id、长度、哈希、错误类型，不记原文。
- 配置从 `.env` 读；仓库只提交 `.env.example`。

## 命令（骨架建成后）

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest
```

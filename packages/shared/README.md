# packages/shared

跨端契约，单一事实源是后端 Pydantic 模型。

## 内容

| 文件 | 来源 | 说明 |
|---|---|---|
| `extraction.schema.json` | 手写（R-03 产出） | 抽取输出的 JSON Schema，模型与校验共用 |
| `openapi.json` | 后端导出 | API 契约快照，随接口变更更新 |
| `api.d.ts` | `openapi-typescript` 生成 | 前端类型，禁止手改 |

## 生成流程（骨架建成后）

```bash
# 后端启动或导出 openapi.json
python -m app.export_openapi > packages/shared/openapi.json
# 生成前端类型
npx openapi-typescript packages/shared/openapi.json -o packages/shared/api.d.ts
```

## 规则

- 不手写业务逻辑。
- 生成文件不手工编辑；如需修改，改后端模型后重新生成。
- schema 变更必须同步 `docs/30-research/research-topics.md` R-03 与提示词版本。

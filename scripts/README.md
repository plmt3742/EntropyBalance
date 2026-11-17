# scripts

跨端运维脚本：生成、校验、导入。不放业务逻辑。

## 现有

| 脚本 | 用途 |
|---|---|
| （待建）`import-records.mjs` | 把 txt/md 批量转成 JSONL 记录 |
| （待建）`export-demo-pack.mjs` | 打包脱敏演示数据与快照 |

## 注意

与 agent 上下文相关的两个脚本在 `.agent/tools/`（不入库）：

```bash
node .agent/tools/gen-file-tree.mjs
node .agent/tools/check-context.mjs
```

## 规则

- Node 脚本用 ESM（`.mjs`），不引入第三方依赖，除非先写 ADR。
- 脚本必须可重复运行，结果幂等。
- 不读取 `data/raw/` 以外的敏感路径；不把内容打印到 stdout。

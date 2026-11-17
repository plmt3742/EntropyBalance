# infra/docker

Docker 构建文件。骨架阶段创建，预计包含：

| 文件 | 用途 |
|---|---|
| `Dockerfile` | 多阶段：`node:24` 构建前端 → `python:3.13-slim` 运行 |
| `compose.yaml` | 单服务，挂载 `data/` 与 `.env` |
| `entrypoint.sh` | 检查快照与密钥，选择在线/回放模式 |

## 构建约束

- 前端产物复制到后端静态目录，运行期只需一个进程。
- 不把 `node_modules` 与 `.venv` 带进最终镜像。
- 镜像内不包含任何真实组织数据。
- `HEALTHCHECK` 打 `/api/health`。

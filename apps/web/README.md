# apps/web

React 前端：导入记录、协作图谱、风险面板、证据侧栏、建议对比、交接清单。

状态：**未开始**。

## 计划选型

React + TypeScript（strict）+ Vite + Tailwind + shadcn/ui。
图谱用 Cytoscape.js（待与 AntV G6 对比，见 `docs/20-architecture/tech-stack.md` S-1/S-2），图表用 ECharts，数据请求用 TanStack Query。

## 结构（计划）

```text
src/
  pages/          路由页面：import / graph / issues / handover
  features/       按功能切分，每块自带组件与 hooks
  components/     通用组件
  lib/            API 客户端（OpenAPI 生成）、格式化、配色
```

## 必须遵守

- 不实现任何指标；数字全部来自 API，避免两处口径。
- 类型从 `packages/shared` 引入，不手写与后端重复的接口类型。
- 空状态、加载态、错误态都要有；演示时不允许出现裸报错。
- 截图中不得出现真实姓名与原文。

## 命令（骨架建成后）

```bash
npm install
npm run dev
npm run build
npm run test
```

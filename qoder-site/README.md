# c-qoder Sites

Qoder Sites 线上版本源码。页面构建自 `../frontend/`，Function、schema 和本地预览在本目录。

## 目录

```text
dist/         发布静态输出（Vite 构建）
functions/    Deno app Function
schema/       Sites DB 迁移记录
dev/          本地 fixture 预览，不发布
```

## 构建

```bash
cd ../frontend
npx vue-tsc --noEmit
npx vite build --mode qoder-sites
```

`VITE_ROUTER_BASE=/c/` 使用哈希路由；静态资源使用根路径 `/assets`。

## 本地预览

```bash
node dev/serve.mjs
# http://127.0.0.1:4176/c/
```

本地预览使用内存数据库、假 Qoder 用户和内存 Storage，仅用于验证界面与路由契约。

```bash
node dev/test-c1-order.mjs
```

该测试验证排序部分失败的写回退与“回退失败不报成功”。

## 线上

<https://c-study-notes-269lxlmz6o3.qoder.zone>

发布由 Qoder Sites 工具完成，需要 Function、Sites DB 与 Storage；不要把 `dev/` 或 `schema/` 打进 webDirectory。

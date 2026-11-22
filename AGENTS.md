# AGENTS.md

本文件面向在本仓库工作的 AI 编程 Agent（以及人类开发者）。
人类用户请先读 [README.md](./README.md)；源码阅读、部署和验收细节见
[HANDOFF.md](./HANDOFF.md)。

## 项目边界

- 个人笔记站：只有账号自己的空间，没有管理员查看他人内容、没有公共内容广场。
- 笔记默认私有；只有作者主动发布的单篇文档会生成公开快照。
- 线上运行环境是 Qoder Sites；`backend/` 是旧版 FastAPI 参考实现，不是线上环境。
- 仓库只放源码；不要提交个人笔记、截图、验收报告或 `.qoder.site` 绑定文件。

## 快速命令

```bash
# 前端
cd frontend
npm ci
npx vue-tsc --noEmit
npx vite build --mode qoder-sites     # 输出 qoder-site/dist

# 本地预览（内存数据库）
cd ../qoder-site
DEMO=1 PORT=4176 node dev/serve.mjs

# 旧版后端（需要 PostgreSQL）
cd ../backend
python -m pytest -q
python -m alembic check
```

修改示例生成器或 AI 语法说明后：

```bash
cd qoder-site
node dev/build-ai-guide.mjs
```

## 代码地图

| 位置 | 作用 |
| --- | --- |
| `qoder-site/functions/index.ts` | Function 入口：Qoder 身份、示例 cookie |
| `qoder-site/functions/routes.mjs` | 全部业务路由、解析器、限额、示例种子 |
| `qoder-site/functions/auth.mjs` | 读取 `x-qoder-user-context` |
| `qoder-site/functions/ai/` | AI 润色：Provider、Markdown、语法白名单 |
| `qoder-site/schema/` | 数据库表与迁移（按序号执行） |
| `qoder-site/dev/serve.mjs` | 本地内存 DB/Storage 预览 |
| `frontend/src/utils/editorModel.ts` | 块与编辑器模块的映射 |
| `frontend/src/views/` | Workspace / Editor / Document / Public / Login |
| `frontend/src/features/aiPolish/` | AI 入口、后台状态、版本选择提示 |
| `backend/` | 旧 FastAPI 版本，仅参考 |

`qoder-site/functions/_qoder/` 由 Qoder Sites 在部署时注入，仓库里不存在；
本地预览使用 `dev/serve.mjs` 里的内存假实现。

## 必须保持的不变量

1. **账号隔离**：所有文档、章节、文件夹、资产查询都以会话 `owner_id` 为条件；
   跨账号统一 404。不要信任浏览器提交的 owner。
2. **稳定块 ID**：保存时已有模块必须带 `id`；服务端按 ID 更新/插入/删除，
   不允许整批删掉重建。
3. **版本控制**：保存模块使用 `If-Match`；冲突返回 409，不能覆盖他人修改；
   保存失败回滚，客户端输入不清空。
4. **公开快照**：公开页只读 `published_*` 字段，不读当前 `blocks`；
   取消发布立即撤销链接；公开附件必须校验快照引用与资产归属。
5. **内容安全**：原始 HTML 只允许 `<u>` 与四种 `mark data-tone`；
   链接只允许 `http/https/mailto` 和站内 `/`；KaTeX `trust:false`；
   代码和公式内容不互相解析。
6. **源码拼接**：只拼接 `code` 块；空块跳过；前一块不以换行结尾且下一块非空
   时补一个换行；不裁剪空行、缩进和尾部空白。
7. **摘要**：取第一个非标题文本块，压缩空白后截断 120 字符。
8. **示例空间**：匿名请求映射到共享 owner `demo`；示例种子只有
   `routes.mjs` 里的 `DEMO_SEEDS` 两篇，不要提交额外内容。
9. **AI**：仅登录用户可用；示例空间返回 403；图片以 `⟦IMG:资产ID⟧` 占位符
   保留，代码和公式要求原样；不要把模型输出当 HTML。

## 修改指南

- **新增接口**：在 `routes.mjs` 的鉴权段之后注册；先 `requireUser`，再 owner 过滤，
  最后才做业务；错误用 `fail(code, status, message)`。
- **新增块类型**：同步改 `schema` 校验、`parseMarkdownBlocks`、`editorModel.ts`、
  `DocumentBlocks.vue` / `MarkdownModule.vue` 和编辑器工具栏；确认保存与阅读一致。
- **改编辑器**：保留原生 textarea 的中文输入与选区；高亮只做视觉层。
- **改 AI**：语法白名单在 `dev/ai-markdown-guide.md`，改完重新生成 `guide.mjs`；
  真实 AI 需要站点 `qoder` 能力，本地 `AI_POLISH_FAKE=1` 只用于界面验收，
  不能当作真实 AI 证据。
- **移除 AI**：删除 `frontend/src/features/aiPolish/`、`qoder-site/functions/ai/`、
  `routes.mjs` 的 AI 导入与三个 AI 路由；回收站逻辑是公共的，不受影响。

## 安全禁区

- 不提交 `.env`、`backend/data/`、`qoder-site/dist/`、`*.qoder.site`、
  个人笔记、截图或任何令牌；
- 不在前端、日志、提示词或仓库中出现 `QODER_PAT`、会话令牌、分享令牌；
- 不把 Sites 的 `_qoder` 适配器替换成暴露凭据的公共代理；
- 平台能力缺失（例如没有 `qoder` 能力）时如实报告，不要用假数据冒充。

## 完成定义

修改后至少执行：

```bash
cd frontend && npx vue-tsc --noEmit
cd ../frontend && npx vite build --mode qoder-sites
```

涉及保存、公开分享、AI 或权限的改动，还要按 [HANDOFF.md](./HANDOFF.md)
的验证清单手动走一遍对应流程；只通过类型检查不算完成。

## 部署

Qoder Sites 与自托管服务器的步骤、环境变量、PAT 注意事项和验收清单见
[HANDOFF.md](./HANDOFF.md)。
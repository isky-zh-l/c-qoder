# 交接文档（给下一个 Agent）

这份文档面向接手本仓库的 AI/开发者，目标有两个：

1. 快速读懂源码，知道每个目录在做什么；
2. 能把项目部署成自己的笔记站（Qoder Sites 或自托管服务器）。

先读 `README.md` 的「项目结构」和「本地运行」，再按本文的顺序看代码。

---

## 一、这是什么

一个按章节组织的个人笔记站：

- 笔记由模块组成（段落、标题、引用、列表、表格、代码、图片、公式）；
- C/H 源码有独立工作区（代码、备注、运行结果、图片）；
- 每篇文档可以单独发布成公开快照；
- 登录后可以把笔记交给 Qoder AI 做排版，生成副本后二选一；
- 匿名访问自动进入共享示例空间，登录后是独立空间。

当前仓库只包含源码，不含个人笔记、截图和示例教程内容。
示例空间只有 `routes.mjs` 里 `DEMO_SEEDS` 定义的两篇功能示例。

---

## 二、目录与职责

```text
frontend/                    Vue 3 + TypeScript + Vite 前端
  src/views/                 Workspace / Editor / Document / Public / Login / Account
  src/components/            编辑器、模块卡片、阅读渲染、工具栏、对话框
  src/utils/editorModel.ts   模块模型、Markdown 与模块互转
  src/api/client.ts          HTTP 客户端（同源 /functions/v1/app/api）
  src/auth/session.ts        会话、示例空间、退出
  src/features/aiPolish/     AI 润色入口、对话框、版本选择提示、API

qoder-site/                  线上运行目录
  functions/index.ts         Function 入口：解析 Qoder 身份 / 示例 cookie
  functions/routes.mjs       全部业务路由（本文件最重要）
  functions/auth.mjs         读取 Qoder 注入的用户上下文
  functions/ai/              AI 润色模块（QCA 客户端、Provider、Markdown 处理）
  schema/*.sql               Sites 数据库建表与迁移
  dev/serve.mjs              本地内存 DB/Storage 预览（不发布）
  dev/ai-markdown-guide.md   AI 排版语法白名单（source of truth）
  dev/build-ai-guide.mjs     生成 functions/ai/guide.mjs

backend/                     旧 FastAPI + PostgreSQL 版本（仅自托管参考）
docs/                        不随仓库发布（本地工作文档）
```

`qoder-site/functions/_qoder/` **不在仓库里**：`backend.mjs`（数据库客户端）和
`storage.mjs`（对象存储客户端）由 Qoder Sites 在部署时注入。离开 Qoder Sites
运行 `functions/` 必须先实现这两个适配器。

---

## 三、阅读顺序（约 30 分钟）

1. `qoder-site/functions/index.ts`：身份从哪里来，示例 cookie 如何生效。
2. `qoder-site/functions/routes.mjs`：
   - 顶部常量：`DEMO_OWNER_ID`、`DEMO_SEEDS`、块类型、限额；
   - `parseMarkdownBlocks`：`.md` 导入与 AI 返回共用的解析器；
   - `application()`：所有路由；
   - `ensureDemoSeed()`：示例空间初始化。
3. `qoder-site/schema/001_core.sql` → `004_chapter_folders.sql`：数据模型。
4. `frontend/src/utils/editorModel.ts`：块与编辑器模块的映射。
5. `frontend/src/views/WorkspaceView.vue`、`EditorView.vue`、`DocumentView.vue`。
6. `frontend/src/features/aiPolish/` 与 `qoder-site/functions/ai/`。

---

## 四、身份、权限与数据边界

- Qoder Sites 把用户上下文放在请求头 `x-qoder-user-context`（base64 JSON），
  `functions/auth.mjs` 解析出 `user_id`；不要信任浏览器提交的 owner。
- 匿名用户由前端调用 `POST /api/public/demo/start`，获得 HttpOnly cookie
  `cq_demo=1`，服务端把请求映射到共享 owner `demo`。
- 所有文档、章节、文件夹、资产查询都以会话 `owner_id` 为条件；
  跨账号统一返回 404，不泄露“存在但无权”。
- 公开分享读取文档上的发布快照字段（`published_*`），
  不读当前 `blocks`；公开 API 只返回白名单字段。
- 资产通过 `/api/assets/{id}/file` 读取，上传目录不静态公开；
  公开文档附件必须同时校验令牌、文档公开、快照存在、资产归属和引用关系。
- 原始 HTML 只允许 `<u>` 与 `<mark data-tone="...">`；链接只允许
  `http/https/mailto` 和站内 `/`；KaTeX 使用 `trust:false`。
- 任何新增接口都要先过 `requireUser` + owner 过滤，再谈业务。

---

## 五、数据模型（Sites 版）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `profiles` | `owner_id` 唯一、`display_name`、`storage_quota_bytes` | 每个账号一行 |
| `chapters` | `owner_id,name,sort_order` | 默认 12 个章节 |
| `folders` | `chapter_id,parent_id,name,sort_order` | 章节内嵌套文件夹 |
| `documents` | `blocks jsonb`、`version`、`published_*`、`deleted_at` | 文档与公开快照 |
| `assets` | `object_path`、`mime_type`、`size_bytes` | 私有图片对象 |
| `usage_locks` | `owner_id,token,expires_at` | 写入锁/额度预留 |

- `documents.blocks` 是数组，每个块有稳定 `id`、`block_type`、`content`、
  `asset_id`、`sort_order`；
- `version` 用于 `If-Match` 条件保存；冲突返回 409，不覆盖别人的修改；
- 删除是软删除：标题改成 `__deleted__...`，保留 `deleted_title` 和原位置；
- 公开快照保存 `published_title/author/blocks/version/at`，重新发布才更新。

---

## 六、主要路由（`routes.mjs`）

| 方法/路径 | 作用 |
| --- | --- |
| `GET /api/health`、`GET /api/public/site` | 健康检查与站点信息 |
| `POST /api/public/demo/start`、`exit` | 进入/退出示例空间 |
| `GET /api/auth/session` | 当前身份 |
| `GET /api/workspace` | 账号、章节、文件夹、用量 |
| `GET/POST /api/documents` | 列表/新建 |
| `POST /api/documents/import` | 导入 `.md/.c/.h` |
| `PUT /api/documents/{id}/blocks` | 保存模块（要求 `If-Match`） |
| `PUT /api/documents/{id}/visibility` | 发布/取消公开 |
| `GET /api/documents/{id}/download` | 下载 C/H 源码 |
| `GET /api/search` | 标题/正文/代码/表格/公式搜索 |
| `GET /api/recycle`、`POST /api/recycle/{id}/restore` | 回收站 |
| `POST /api/assets`、`GET /api/assets/{id}/file` | 图片上传与读取 |
| `PUT /api/orders/{scope}` | 全部/章节/文件夹/收藏排序 |
| `POST /api/documents/{id}/ai-polish` | AI 润色并创建副本 |
| `POST /api/documents/{id}/ai-polish/choose` | 保留一版，另一版进回收站 |

所有路径都挂在站点入口 `/functions/v1/app` 下，所以浏览器实际请求
`/functions/v1/app/api/...`。

---

## 七、编辑器与 Markdown 契约

- 文本块统一 `block_type='rich_text'`，`content.module` 取：
  `paragraph/heading1/heading2/heading3/quote/divider/bullet_list/ordered_list/todo_list/table`。
- 非文本块：`code`（`text+language`）、`image`（`asset_id+alt+caption`）、
  `formula`（`latex`）；源码文档还有 `remark`、`result`。
- 保存必须提交已有块 `id`；新块省略 `id` 由服务端生成；不能整批删除重建。
- 摘要取第一个非标题文本块，压缩空白后截断 120 字符。
- `.md` 导入与 AI 返回共用 `parseMarkdownBlocks`；修改解析规则会同时影响两者。
- 源码拼接：只拼接 `code` 块；空块跳过；前一块不以换行结尾且下一块非空时补
  一个换行；不裁剪空行、缩进和尾部空白。

---

## 八、AI 润色模块

流程：

1. 编辑页点「AI 润色」（仅登录用户，示例空间禁用）；
2. `POST /api/documents/{id}/ai-polish`：
   - 加载文档、转成 Markdown（图片变成 `⟦IMG:资产ID⟧` 占位符）；
   - 语法白名单 + 固定提示词 + 笔记一起发给 Qoder Cloud Agents；
   - 返回后用 `parseMarkdownBlocks` 重建模块，并按占位符还原图片；
   - 创建「原标题 · AI 润色」副本（同章节/文件夹），返回两版信息；
3. 前端可以关闭对话框后台等待；完成后笔记页出现版本选择提示；
4. `POST /api/documents/{id}/ai-polish/choose` 把落选的一版软删除。

实现位置：

- `functions/ai/provider.mjs`：QCA 客户端、模型选择、Agent/Environment/Session；
- `functions/ai/polish.mjs`：块 ↔ Markdown、提示词、图片占位符、结果校验；
- `functions/ai/cloud-agents.mjs`：官方 Cloud Agents 客户端副本；
- `functions/ai/guide.mjs`：由 `dev/ai-markdown-guide.md` 生成；
- `frontend/src/features/aiPolish/`：按钮、对话框、背景状态、笔记页选择提示。

限制：

- 需要站点后端开启 `qoder` 能力（平台创建 `QODER_PAT`），并只用服务端读取；
- 单次同步等待约 40 秒；关闭标签页可能中断请求，但已生成的副本仍可被识别；
- 图片只以占位符保护，不交给模型；代码、公式、链接要求原样保留；
- 示例空间禁止 AI（`AI_ALLOW_DEMO=false`），避免匿名消耗额度。

---

## 九、本地运行

```bash
# 1. 构建（配置在 frontend/.env.qoder-sites）
cd frontend
npm ci
npx vue-tsc --noEmit
npx vite build --mode qoder-sites     # 输出到 qoder-site/dist

# 2. 本地预览（内存数据库，DATA 重启即清空）
cd ../qoder-site
DEMO=1 PORT=4176 node dev/serve.mjs
# 打开 http://127.0.0.1:4176/c/
```

本地预览不需要 PAT、PostgreSQL 或 Qoder 登录；`DEMO=1` 时所有请求当作
示例空间用户。AI 在本地默认不可用；需要界面验收时可临时让
`functions/ai/polish.mjs` 走 `AI_POLISH_FAKE=1` 的本地占位实现，
但**不要**把它当成真实 AI 证据。

---

## 十、部署到 Qoder Sites

1. 构建 `qoder-site/dist`（见上）；
2. 用 Qoder Sites 准备站点：
   - `projectRoot` 指向 `qoder-site`；
   - 静态目录 `dist`，函数目录 `functions`；
   - 数据库访问设为读写，并提供当前站点的 `schemaRef`；
   - 目标站点保持公开访问。
3. 需要 AI 时，先给站点开启 `qoder` 后端能力。平台会为账号创建 `QODER_PAT`
   并只注入函数运行时；不要把它写进前端、日志或仓库。
4. 发布后验证：
   - `/c/` 可匿名打开并自动进入示例空间；
   - 登录后创建/保存文档、上传图片；
   - 公开分享链接匿名可读，取消后 404；
   - AI 需要登录，示例空间返回 403 `ai_login_required`。

注意：`qoder-site/.C 语言学习笔记.qoder.site` 是本地绑定文件，
包含签名 URL，不要提交；`qoder-site/dist` 是构建产物，也不要提交。

---

## 十一、部署到自己的服务器（阿里云轻量等）

当前 `qoder-site/functions` 依赖 Qoder Sites 注入的 `_qoder/*` 与 Qoder 登录，
**不能直接搬到普通服务器运行**。自托管请使用 `backend/` 的 FastAPI 版本：

1. 服务器安装 Python 3.11+、PostgreSQL、Nginx；
2. `cd backend`，创建虚拟环境并 `pip install -r requirements.txt`；
3. 参考 `backend/.env.example` 写 `.env`（数据库、站点地址、Cookie、SMTP）；
4. `python -m alembic upgrade head`；
5. 构建前端（`frontend/.env.production.example`，`VITE_API_BASE=/c/api/v1`），
   把 `frontend/dist` 指给后端或 Nginx；
6. `uvicorn app.main:app --host 127.0.0.1 --port 8000`，Nginx 反代 `/c/`；
7. 配 HTTPS、Cookie `Secure`、SMTP 后再开放注册。

注意：

- FastAPI 版本有邮箱注册、管理员、限流、备份等能力，Sites 版本没有；
- **AI 润色只存在于 Sites 版本**。自托管要 AI，需要自己加一个服务端接口，
  不要把 `QODER_PAT` 交给浏览器；也可以换成任意兼容的模型 API；
- 阿里云只是示例，任何能跑 Python/PostgreSQL 的服务器都可以；
- 上线前用真实邮箱、HTTPS 和备份恢复演练验证，不要凭“本地通过”声称生产可用。

---

## 十二、验证命令

```bash
# 前端
cd frontend
npx vue-tsc --noEmit
npx vite build --mode qoder-sites

# 旧后端（需要 PostgreSQL；测试会建临时库）
cd backend
python -m pytest -q
python -m alembic check

# 本地示例
cd ../qoder-site
DEMO=1 PORT=4176 node dev/serve.mjs
```

建议至少手动验证：

1. 新建笔记 → 插入各类模块 → 保存 → 刷新 → 继续编辑；
2. 重复保存后块 ID 稳定；冲突返回 409 且输入不丢；
3. 上传图片、阅读页受保护读取、其他账号 404；
4. 发布公开 → 匿名可读 → 取消 → 旧链接 404；
5. 390/1440 无横向溢出；
6. 登录用户 AI 润色 → 后台等待 → 笔记页选择版本 → 落选进回收站；
7. 含图片的笔记润色后图片、说明和位置不变。

---

## 十三、常见坑

- `/c/` 是哈希路由；根路径由 `index.html` 脚本跳转到 `/c/`，不要改成 history 路由
  而不配置回退。
- `frontend/.env.qoder-sites` 决定入口基路径和构建输出；普通 `npm run build`
  不会加载它，必须 `--mode qoder-sites`。
- 保存必须带 `If-Match`；不要用“先删后建”的方式保存模块。
- 公开页不能读当前 `blocks`；只能读 `published_blocks` 快照。
- 示例空间是共享可写的软删除；删除文档会把标题改成 `__deleted__...`。
- 图片校验看真实解码格式，不信 MIME/扩展名；上传先写临时目录再提交。
- AI 返回仍是普通 Markdown，必须重新解析并校验；不要把模型输出直接当 HTML。
- 修改 `dev/ai-markdown-guide.md` 后要重新运行 `dev/build-ai-guide.mjs`。
- 仓库不包含示例教程和 `demo-notes.mjs`；要加内容，改 `DEMO_SEEDS` 或用导入接口。
- Qoder Sites 的 WAF 可能拦截无头浏览器；涉及登录/真实 AI 的验收要用真实浏览器。

---

## 十四、给接手 Agent 的规则

- 先读 `AGENTS.md`（如果本地存在）和本文，再做修改；
- 任何资源查询都以会话账号为根条件，跨账号 404；
- 不要提交 `.env`、`backend/data`、`qoder-site/dist`、`*.qoder.site`、
  个人笔记或截图；
- 不要在前端、日志、提示词或仓库里出现 `QODER_PAT`、分享令牌、会话令牌；
- 修改保存/发布/AI 路由后，必须跑一遍对应验证，不要只靠类型检查；
- 平台能力缺失（如没有 `qoder` 能力）时如实报告，不要用假数据冒充真实 AI；
- 如果要移除 AI，按 `frontend/src/features/aiPolish/`、
  `qoder-site/functions/ai/`、`routes.mjs` 三个 AI 路由和导入一起删，
  回收站逻辑是公共的，不受影响。
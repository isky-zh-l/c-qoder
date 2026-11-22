# C 语言学习笔记

面向 C 语言学习者的模块化笔记与源码工作区。按章节整理 Markdown、C 代码和公式，
在一个网站里完成阅读、编辑和公开分享；登录后可以用 Qoder AI 整理排版。

- **在线体验**：https://c-study-notes-269lxlmz6o3.qoder.zone/c/
- **源码仓库**：https://github.com/isky-zh-l/c-qoder
- **接手/部署文档**：[HANDOFF.md](./HANDOFF.md)
- **Agent 开发约定**：[AGENTS.md](./AGENTS.md)

> 示例空间会自动进入，包含两篇功能示例；笔记数据按 Qoder 账号隔离。
> AI 润色需要登录，示例空间不开放。

## 功能

- **章节 / 文件夹 / 收藏**：三套独立位置，拖动排序自动保存。
- **模块化编辑器**：段落、H1–H3、引用、分隔线、圆点/编号/待办列表、表格、
  代码、图片、块级公式；支持加粗、斜体、下划线、删除线、行内代码、链接、
  行内公式和四色高亮。
- **稳定模块 ID**：保存按 ID 更新/插入/删除，使用 `If-Match` 版本控制；
  冲突返回 409，输入不丢失。
- **C/H 源码工作区**：代码、备注、运行结果、图片分开存放；复制和下载按固定规则
  拼接完整源码；编辑、预览、阅读共用同一套语法高亮。
- **公开分享**：每篇文档独立发布快照，发布后继续编辑不影响已公开内容；
  取消发布立即撤销旧链接。
- **搜索与回收站**：覆盖标题、正文、代码、备注、结果、表格和公式；回收保留 7 天。
- **AI 排版**：登录后把整篇笔记交给 Qoder AI，只调整结构，生成副本后选择保留哪一版；
  图片以占位符保留，代码和公式不改写；支持后台等待，完成后在笔记页选择。
- **响应式**：390–1440 宽度；手机编辑器工具栏可收起，正文无横向溢出。

## 技术栈

| 层 | 实现 |
| --- | --- |
| 前端 | Vue 3 + TypeScript + Vite，哈希路由 `/c/#/...` |
| 线上后端 | Qoder Sites：Deno Edge Function + PostgreSQL + 私有 Storage |
| AI | Qoder Cloud Agents（`qoder` 站点能力，PAT 只注入函数运行时） |
| 旧版后端 | FastAPI + PostgreSQL（自托管参考，非线上环境） |

## 目录结构

```text
frontend/                   Vue 3 前端源码
qoder-site/functions/       Deno Edge Function（业务路由、权限、AI）
qoder-site/schema/          Sites 数据库建表与迁移
qoder-site/dev/             本地预览、AI 语法说明与生成器
backend/                    旧 FastAPI/PostgreSQL 版本
```

`qoder-site/functions/_qoder/` 由 Qoder Sites 部署时注入，仓库里没有这两个适配器
（数据库与对象存储客户端）。

## 本地运行

### 环境要求

- Node.js 20+ 与 npm
- 可选：Python 3.11+、PostgreSQL（只用于旧版 FastAPI 后端）

### 本地预览（内存数据库）

```bash
cd frontend
npm ci
npx vue-tsc --noEmit
npx vite build --mode qoder-sites     # 输出到 qoder-site/dist

cd ../qoder-site
DEMO=1 PORT=4176 node dev/serve.mjs
```

打开 http://127.0.0.1:4176/c/ 。`DEMO=1` 时所有请求按示例空间处理，数据保存在内存中，
重启即清空；首次访问会写入两篇功能示例。

### 构建配置

站点构建读取 `frontend/.env.qoder-sites`：

```env
VITE_BASE_PATH=/
VITE_ROUTER_BASE=/c/
VITE_API_BASE=/functions/v1/app/api
VITE_OUT_DIR=../qoder-site/dist
```

普通 `npm run build` 会加载 `.env.production`，不会加载该文件；部署 Qoder Sites
必须使用 `vite build --mode qoder-sites`。

### 旧版 FastAPI（可选）

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Linux/macOS: .venv/bin/pip
cp .env.example .env                             # 配置数据库、Cookie、SMTP
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端使用 `frontend/.env.production.example`（`VITE_API_BASE=/c/api/v1`）构建，
由 FastAPI 或 Nginx 提供 `/c/`。

## 部署

- **Qoder Sites（当前线上方式）**：构建 `qoder-site/dist`，用 `qoder-site` 作为
  项目根目录准备站点（静态目录 `dist`，函数目录 `functions`，数据库读写权限）；
  AI 需要开启站点 `qoder` 能力。
- **自有服务器**：当前 Qoder Sites 函数依赖平台注入的数据库/存储适配器和登录，
  不能直接搬到普通服务器；请使用 `backend/` 的 FastAPI 版本，或自行替换适配层。
  AI 只实现了 Sites 版本，自托管需要自行接入模型服务。

详细步骤、验证清单和注意事项见 [HANDOFF.md](./HANDOFF.md)。

## 测试与验证

```bash
# 前端类型检查与构建
cd frontend
npx vue-tsc --noEmit
npx vite build --mode qoder-sites

# 旧版后端测试（需要 PostgreSQL，测试会创建临时库）
cd backend
python -m pytest -q
python -m alembic check
```

上线前至少手动验证：新建/保存/冲突、模块 ID 稳定、图片受保护读取、
公开快照与取消、跨账号 404、390/1440 布局、AI 润色与版本选择。

## 安全与边界

- 所有资源查询以会话账号为根条件，跨账号统一 404；
- 笔记默认私有，公开页只读发布快照；
- 原始 HTML 只允许 `<u>` 和四种 `mark data-tone`；链接只允许
  `http/https/mailto` 和站内 `/`；KaTeX `trust:false`；
- 图片只经受保护的资产接口读取，上传先临时落盘并校验真实格式；
- `QODER_PAT`、会话令牌和分享令牌不得进入前端、日志或仓库。

## 已知限制

- Sites 版本没有管理员控制台、注册开关、限流和自动备份（旧版 FastAPI 有）；
- 公开分享为单篇快照，没有公开列表、评论或协作；
- 图片上传支持 PNG / JPEG / GIF / WebP，不支持 HEIC；
- AI 润色仅登录用户可用，含图片的笔记图片只保留占位、不参与改写；
- 仓库不包含示例教程与个人笔记，示例空间只有两篇内置功能示例。

## 文档

- [AGENTS.md](./AGENTS.md)：给 AI/开发者的仓库约定、命令和禁区；
- [HANDOFF.md](./HANDOFF.md)：源码阅读、部署与验收的详细交接。

## 许可

仓库未附带开源许可证。用于学习、复现个人笔记站可直接参考；商用或再分发前请联系作者。
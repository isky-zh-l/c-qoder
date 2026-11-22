# C 语言学习笔记

面向 C 语言学习者的模块化笔记与源码工作区：按章节整理 Markdown、C 代码和公式，
阅读、编辑、公开分享在同一个网站里完成；登录后可以用 Qoder AI 一键整理排版。

- **线上示例**：https://c-study-notes-269lxlmz6o3.qoder.zone/c/
- **仓库**：https://github.com/isky-zh-l/c-qoder
- **技术栈**：Vue 3 + TypeScript + Vite、Qoder Sites（Deno Edge Function + 数据库 + Storage）
- **用途**：可直接复用为个人笔记站；替换标题、示例内容和 AI 配置即可做成自己的版本
- **交接文档**：[HANDOFF.md](./HANDOFF.md)（给下一个 Agent 的源码与部署说明）

## 项目结构

| 路径 | 说明 |
| --- | --- |
| `frontend/` | Vue 3 前端源码与构建配置 |
| `qoder-site/functions/` | Deno Edge Function：路由、校验、权限、AI 润色 |
| `qoder-site/schema/` | Sites 数据库建表脚本 |
| `qoder-site/dev/` | 本地预览 harness、AI 语法说明与生成器 |
| `backend/` | 旧 FastAPI/PostgreSQL 版本，仅作本地参考，不是线上环境 |

## 功能

- **章节 / 文件夹 / 收藏**三套位置，拖动排序自动保存；
- **模块化编辑器**：段落、H1–H3、引用、分隔线、列表、待办、表格、代码、图片、公式；
  模块有稳定 ID，保存使用 `If-Match` 版本控制，冲突返回 409；
- **C/H 源码工作区**：代码、备注、运行结果、图片分开存放，复制/下载按固定规则拼接源码；
- **公开分享**：每篇文档独立发布快照，发布后编辑不影响已公开内容；
- **搜索与回收站**：标题、正文、代码、备注、表格和公式；回收保留 7 天；
- **AI 排版**：登录后把整篇笔记交给 Qoder AI，只调整结构，生成副本后选择保留哪一版；
  图片以占位符保留，代码和公式不改写；
- **桌面与手机**：390–1440 响应式，手机编辑器工具栏可收起。

## 本地运行

### 1. 构建站点前端

```bash
cd frontend
npm ci
npx vue-tsc --noEmit
npx vite build --mode qoder-sites
```

产物输出到 `qoder-site/dist`。

### 2. 本地预览（内存数据）

```bash
cd qoder-site
DEMO=1 PORT=4176 node dev/serve.mjs
```

打开 http://127.0.0.1:4176/c/ 。`DEMO=1` 时请求视为示例空间用户，数据在内存中，
重启即清空；首次访问会写入两篇功能示例，随后可以新建或导入自己的 `.md` / `.c` / `.h`。

## 做成自己的笔记站

1. 修改 `qoder-site/functions/routes.mjs` 里的 `SITE_TITLE` 和 `DEMO_SEEDS`，
   换成自己的示例或清空；
2. 修改 `frontend/index.html` 的标题与描述；
3. 用自己的 Qoder Sites 项目发布 `qoder-site`（静态目录 `dist`，函数目录 `functions`）；
4. 如果不需要 AI，删除 `frontend/src/features/aiPolish/` 与 `qoder-site/functions/ai/`，
   以及 `routes.mjs` 中对应的三个路由即可；
5. 前端是纯静态产物，也可以部署到任意静态托管；`backend/` 是另一套自托管参考实现。

## AI 排版

- 入口在笔记编辑器右上角，仅登录 Qoder 账号可用；示例空间按钮禁用；
- 服务端把语法白名单、固定提示词和笔记 Markdown 提交给 Qoder Cloud Agents；
- 返回后用同一解析器重建模块，生成「原标题 · AI 润色」副本；
- 可以后台进行，完成后在笔记页选择保留原版还是 AI 版，落选的一版进入回收站；
- 图片以 `⟦IMG:资产ID⟧` 占位符保留，模型接触不到图片；
- 需要站点后端开启 `qoder` 能力；语法白名单在 `qoder-site/dev/ai-markdown-guide.md`。

## 旧版 FastAPI

`backend/` 保存了第一版实现（FastAPI + PostgreSQL + 邮箱注册、管理员、限流、备份）。
它用于参考和本地测试，不是当前线上环境；线上以 Qoder Sites 版本为准。

## 说明

仓库只包含源码。个人笔记、验收截图和参赛材料不随仓库发布。
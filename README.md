# 仪光赤心 · 求职导航

仪光赤心实践队科创组出品的应届生 AI 校招工作台。填写个人档案后，从**公司官网公开校招页**和**牛客公开日程**汇总职位，按匹配度展示公司简介、投递入口和相关面经。

视觉采用队徽配色：赤心红、徽章金、桃粉暖底。Logo、实践队队徽、科创组标识见 `resource/` 与前端 `frontend/public/brand/`。

Boss 直聘**不抓取内部接口**，只生成官方搜索 URL，并允许粘贴公开分享链接到收藏夹。

## 环境要求

| 工具 | 版本 |
| --- | --- |
| Python | 3.11 及以上（含 3.13） |
| Node.js | 20 及以上（需带 `npm`） |

Windows 用户把下面的 `source .venv/bin/activate` 换成 `.venv\Scripts\activate`。

## 启动

在仓库根目录操作。后端和前端要**同时开着**，用两个终端。

### 1. 配置环境变量

```bash
cp .env.example .env
```

用编辑器打开根目录 `.env`。`LLM_API_KEY` **可以留空**：不填也能检索、筛选、收藏，对话匹配改用关键词打分。

若要用 AI 对话，到 [智谱开放平台](https://open.bigmodel.cn) 创建 API Key，填入：

```
LLM_API_KEY=你的密钥
```

默认模型是 **GLM-4.7-Flash**（`LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4`）。免费档通常限制并发为 1。

测试 **DeepSeek V4 Flash** 时，到 [DeepSeek 开放平台](https://platform.deepseek.com) 创建 API Key，把根目录 `.env` 改成：

```
LLM_API_KEY=sk-你的DeepSeek密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

保存后**必须重启后端**（`--reload` 不会自动重读 `.env`）：在跑 uvicorn 的终端里 Ctrl+C，再执行一次 `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`。然后 `curl http://127.0.0.1:8000/api/health`，应看到 `"llm_model": "deepseek-v4-flash"` 且 `"llm_ready": true`。

也可改成其他 OpenAI 兼容服务。改完 `.env` 后都要重启后端。

### 2. 启动后端（终端一）

必须在 `backend/` 目录执行，这样 Python 才能找到 `app` 包。

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 即成功。可用下面命令自检：

```bash
curl http://127.0.0.1:8000/api/health
```

应返回 JSON，其中 `"ok": true`。`llm_ready` 为 `true` 表示已读到 API Key。

SQLite 数据库会自动创建在 `backend/data/app.db`。公司白名单在仓库根目录 [data/companies.yml](data/companies.yml)。

### 3. 启动前端（终端二）

```bash
cd frontend
npm install
npm run dev
```

看到 `Local: http://localhost:5173/` 后，浏览器打开 **http://127.0.0.1:5173** 。Vite 会把 `/api` 代理到后端 `8000` 端口，请不要只开前端。

建议先到「个人档案」填写期望岗位、城市和技能，再使用对话或职位发现。

## 使用说明

- **对话**：配置了 API Key 时，会把你的话解析成城市/类型/薪资/关键词，再给前几条写匹配理由。未配置则按规则打分。
- **职位发现**：不调大模型（避免免费档排队卡住），按档案和关键词做规则匹配。卡片右上角是 0–100 **匹配度**。库里大多是「公司校招入口」而不是岗位 JD，搜「后端」不会只留下后端岗。
- **公司官网**是企业介绍站（如 `bytedance.com`），**投递 / 校招页**才是招聘站。两者相同时只显示投递按钮。
- 卡片会附带该公司在牛客公开页上的面经；抓不到具体帖时仍可跳转牛客 / 知乎搜索。
- 第一次点「刷新数据源」或缓存过期（默认 8 小时）时，会请求公开页，可能要十几秒，属正常。

## 数据源边界

| 来源 | 行为 |
| --- | --- |
| 公司官网 | 读取 [data/companies.yml](data/companies.yml) 白名单公开页，限速 + SQLite 缓存 8 小时 |
| 牛客 | 请求公开校招列表页与面经搜索页，解析标题与链接 |
| Boss 直聘 | 仅跳转 `zhipin.com` 搜索页 / 保存用户粘贴的公开链接 |
| 知乎 | 仅生成面经搜索 URL，不抓取 |

请合理控制刷新频率。不要把 `.env` 和 `*.db` 提交到 Git。

## 功能

- 新对话：按档案提问，返回匹配职位卡片
- 职位发现：筛选、刷新数据源、保存 Boss 链接；卡片附带牛客公开面经与知乎搜索入口
- 收藏夹：职位 / 官网 / 外链
- 个人档案：学历、毕业年份、专业、意向岗位、城市与期望薪资
- 历史对话：继续或删除

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 页面能开但列表/对话报错、或 `curl /api/health` 失败 | 后端没起来，或不是在 `backend/` 里执行的 `uvicorn` |
| 前端不是 5173、接口跨域 | 开发请用 Vite 的 5173；后端 CORS 只允许该端口 |
| 8000 / 5173 端口被占用 | 换掉占用进程，或同时改后端端口与 `frontend/vite.config.ts` 里的 proxy |
| `npm: command not found` | 安装 Node.js 20+ |
| 对话没有 AI 理由 | `.env` 里 `LLM_API_KEY` 为空，或改完未重启 uvicorn |
| 刷新很久 / 卡片很少 | 首次拉取公开页较慢；部分站点可能超时，会先展示白名单校招入口 |

## 目录

```
ygcx/
  .env.example          # 复制为 .env 后按需填密钥
  data/companies.yml    # 官网校招白名单
  backend/              # FastAPI + SQLite
  frontend/             # Vite + React
  resource/             # 队徽等原始素材
```

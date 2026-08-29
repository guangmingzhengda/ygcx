# 仪光赤心 · 求职导航

仪光赤心实践队科创组出品的应届生 AI 校招工作台。填写个人档案后，从**公司官网公开校招页**和**牛客公开日程**汇总职位，按匹配度展示公司简介与跳转链接。

视觉采用队徽配色：赤心红、徽章金、桃粉暖底。Logo、实践队队徽、科创组标识见 `resource/` 与前端 `frontend/public/brand/`。

Boss 直聘**不抓取内部接口**，只生成官方搜索 URL，并允许粘贴公开分享链接到收藏夹。

## 启动

```bash
# 后端
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # 可选：填入 LLM_API_KEY
uvicorn app.main:app --reload --port 8000
```

```bash
# 前端（另开终端）
cd frontend
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:5173 。前端会把 `/api` 代理到后端 `8000` 端口。

未配置 `LLM_API_KEY` 时仍可检索和收藏，匹配改用关键词打分。配置后默认走 DeepSeek（OpenAI 兼容，可改 `LLM_BASE_URL` / `LLM_MODEL`）。

## 数据源边界

| 来源 | 行为 |
| --- | --- |
| 公司官网 | 读取 [data/companies.yml](data/companies.yml) 白名单公开页，限速 + SQLite 缓存 8 小时 |
| 牛客 | 请求公开校招列表页，解析标题与链接 |
| Boss 直聘 | 仅跳转 `zhipin.com` 搜索页 / 保存用户粘贴的公开链接 |

请合理控制刷新频率。不要把 `.env` 和 `*.db` 提交到 Git。

## 功能

- 新对话：按档案提问，返回匹配职位卡片
- 职位发现：筛选、刷新数据源、保存 Boss 链接
- 收藏夹：职位 / 官网 / 外链
- 个人档案：学历、毕业年份、专业、意向岗位与城市
- 历史对话：继续或删除

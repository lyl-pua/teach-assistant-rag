# 教学助手 · 国风 RAG 教研工作台

> 面向小学语文教师 / 班主任的新中式国风个人工作台，集成 RAG（检索增强生成）AI 助手能力，覆盖日常教学管理六大核心场景。基于 FastAPI + LangGraph + FAISS + DeepSeek/GLM 构建，可一键部署在 2 核 2G 的轻量服务器上。

![version](https://img.shields.io/badge/version-2.1.0-2A5047)
![python](https://img.shields.io/badge/python-3.10+-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## ✨ 项目亮点

- **新中式国风 UI**：墨绿/米黄/赭石配色，宣纸纹理，仿宋字体，国风 SVG 图标系统（窗棂、锦囊、竹简、卷轴等 12 枚），诗句随机轮换（内置 2010 首唐诗）
- **RAG 智能问答**：基于 LangGraph 工作流（retrieve → generate），FAISS 向量检索 + DeepSeek/GLM 生成，参考资料溯源
- **教学工具自动生成**：教案 / 课件 / 作业 / 论文 4 类工具，生成前先检索知识库相关段落注入 prompt，降低幻觉与 token 消耗
- **Token 用量追踪**：后端捕获每次 LLM 调用的 `prompt_tokens / completion_tokens / total_tokens`，前端徽章实时展示，支持按模型分组统计
- **轻量部署**：SQLite + 文件系统，零外部依赖；uvicorn 单 worker 内存占用 ~60MB，适合 2 核 2G 服务器
- **双源天气**：主源 Open-Meteo（免 key 全球可用）+ 和风天气兜底，自动适配汉寿地理位置
- **缓存破坏 + Key 归一化**：前端 `?v=2.1.0` 防缓存，后端 `deepseek_api_key → DEEPSEEK_API_KEY` 大小写自动归一化

---

## 📂 功能模块

| 模块 | 功能说明 |
|------|---------|
| 🏠 **首页工作台** | 问候语（按时间段切换早/午/晚安）、诗句随机轮换、实时天气卡片、Token 消耗徽章、功能模块入口 |
| 📥 **收集箱** | 记录教学灵感、学生情况、待办事项，支持分类与置顶 |
| 📖 **阅读** | 上传课件/课文/课本（PDF / Word / TXT / Markdown），自动分块、向量化、入库，重建知识库 |
| 📅 **日程** | 教学安排、教研活动、学生辅导，按日期查看，可标记完成 |
| 🤖 **AI 助手** | RAG 智能对话，SSE 流式输出，基于上传文档回答问题，参考资料溯源（文档名 + 片段 + 摘要） |
| 🛠️ **教学工具** | 一键生成教案 / 课件大纲 / 分层作业 / 教学小论文，结合知识库内容，按工具类型定制 prompt 模板 |
| ⚙️ **设置与数据** | 配置 DeepSeek / OpenAI / 智谱 / 和风 Key，在线测试连通性，查看 Token 用量统计，管理知识库 |

---

## 🛠️ 技术栈

### 后端
- **Web 框架**：FastAPI 0.110+ / uvicorn（单 worker 节省内存）
- **RAG 工作流**：LangGraph StateGraph（retrieve → generate 两节点）
- **Embedding**：智谱 `embedding-3`（2048 维）
- **向量检索**：FAISS IndexFlatIP（L2 归一化 + 内积 = cosine 相似度）
- **LLM 生成**：DeepSeek Chat（主） + 智谱 GLM-4-Flash（兜底）
- **存储**：SQLite（settings / chat_sessions / chat_messages / documents / chunks / tool_runs / token_usage 等表）+ 文件系统
- **文档解析**：pypdf（PDF）+ python-docx（Word）+ 原生（TXT/MD）

### 前端
- **纯静态**：原生 HTML + CSS + JavaScript（无构建步骤）
- **国风设计系统**：墨绿 `#2A5047` / 宣纸米黄 `#F7F2E3` / 赭石 `#A56A3B` / 印章红 `#B4423B`
- **字体**：STFangsong / FangSong / SimSun / Noto Serif SC
- **图标**：自研 12 枚国风 SVG（窗棂、锦囊、竹简、卷轴、印章等）
- **数据交互**：fetch API + SSE（流式 AI 回复）

### 部署
- **进程管理**：systemd `teach.service`
- **反向代理**：Nginx（`/teach/` → 静态文件，`/teach/api/` → `127.0.0.1:8777`）
- **零本地模型**：全部调用云端 API，内存占用极低

---

## 📁 项目结构

```
.
├── backend/                       # 后端
│   ├── app.py                     # FastAPI 主入口（lifespan + 路由挂载 + 静态托管）
│   ├── config.py                  # 全局配置（Key 优先级：DB > 环境变量 > 默认）
│   ├── db.py                      # SQLite 操作封装（含 Key 大小写归一化）
│   ├── requirements.txt
│   ├── seed_docs.py               # 种子文档批量入库脚本
│   ├── routers/                   # FastAPI 路由模块
│   │   ├── ai.py                  # AI 对话（会话 CRUD + /ai/ask + /ai/stream SSE）
│   │   ├── health.py              # 健康检查 + /stats/tokens Token 统计
│   │   ├── inbox.py               # 收集箱
│   │   ├── reading.py             # 阅读（上传 + 向量化 + 重建知识库）
│   │   ├── schedule.py            # 日程
│   │   ├── settings.py            # 设置（Key 测试 + 热加载）
│   │   ├── tools.py               # 教学工具（RAG 增强：检索→注入prompt→生成）
│   │   └── weather.py             # 天气（Open-Meteo 主 + 和风兜底）
│   ├── rag/                       # RAG 核心模块
│   │   ├── embeddings.py          # 智谱 embedding-3 封装
│   │   ├── vectorstore.py         # FAISS 向量存储（单例 + 持久化）
│   │   ├── parser.py              # 文档解析 + 分块（600 字 / 100 重叠）
│   │   ├── generator.py           # LLM 封装（DeepSeek/GLM）+ Token 用量记录
│   │   └── workflow.py            # LangGraph 工作流（retrieve → generate）
│   ├── services/
│   │   └── weather.py             # 双源天气服务
│   └── data/
│       ├── documents/             # 10 篇种子教学文档（课标、教案、古诗、班主任等）
│       ├── app.db                 # SQLite（运行时生成，.gitignore 已排除）
│       └── vectorstore.pkl        # FAISS 索引（运行时生成，.gitignore 已排除）
├── frontend/                      # 前端（纯静态）
│   ├── index.html                 # 主页面
│   ├── poems.js                   # 2010 首唐诗数据（随机轮换）
│   └── static/
│       ├── app.js                 # 核心逻辑（导航 + AI + Token + 国风图标）
│       └── style.css              # 国风样式
├── docs/                          # 文档
│   ├── HELP.md                    # 用户使用手册
│   ├── LearningText.md            # 学习资料（LangChain/LangGraph/React/多Agent 源码解读）
│   └── VibeCoding-Journey.md      # Vibe Coding 思路梳理 + 面试亮点
├── nginx-teach-location.conf      # Nginx /teach/ 配置示例
├── deploy.sh                      # 一键部署脚本（含 systemd + nginx 配置）
├── build-deploy.js                # 构建打包脚本（脱敏后，Key 占位符）
├── .gitignore
└── README.md
```

---

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/<your-name>/<repo-name>.git
cd <repo-name>
```

### 2. 后端安装依赖

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置 API Key（三选一）

**方式 A：启动后在 Web 设置页配置（推荐）**

启动服务后访问 `http://localhost:8777/` → 进入「设置」→ 填写 Key → 测试联通。

**方式 B：环境变量**

```bash
export DEEPSEEK_API_KEY="sk-your-deepseek-key"      # 主 LLM
export ZHIPU_API_KEY="your-zhipu-key.your-secret"   # Embedding + 兜底 LLM
export HEFENG_API_KEY="your-hefeng-web-api-key"     # 可选，和风兜底
```

**方式 C：.env 文件**

在 `backend/` 下创建 `.env`：

```env
DEEPSEEK_API_KEY=sk-your-deepseek-key
ZHIPU_API_KEY=your-zhipu-key.your-secret
HEFENG_API_KEY=your-hefeng-web-api-key
```

### 4. 启动服务

```bash
cd backend
uvicorn app:app --host 0.0.0.0 --port 8777 --workers 1
```

访问 `http://localhost:8777/` 即可看到前端页面。

### 5.（可选）入库种子文档

```bash
cd backend
python seed_docs.py
```

将 `data/documents/` 下 10 篇教学文档批量分块、向量化、入库，作为初始知识库。

---

## 🌐 生产部署（Linux + Nginx + systemd）

### 1. 上传代码到服务器

```bash
scp -r teach-assistant root@your-server:/opt/teach
```

### 2. 安装依赖

```bash
cd /opt/teach/backend
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 创建 systemd 服务

`/etc/systemd/system/teach.service`：

```ini
[Unit]
Description=Teach Assistant RAG Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/teach/backend
ExecStart=/opt/teach/backend/venv/bin/uvicorn app:app --host 127.0.0.1 --port 8777 --workers 1
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now teach
systemctl status teach
```

### 4. 配置 Nginx 反向代理

参考 `nginx-teach-location.conf`，将其注入到站点配置的 `server { ... }` 块中：

```nginx
location ^~ /teach/ {
    alias /opt/teach/frontend/;
    try_files $uri $uri/ /teach/index.html;

    location ~ ^/teach/api/(.*)$ {
        proxy_pass http://127.0.0.1:8777/api/$1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;           # SSE 流式必需
        proxy_read_timeout 300s;
    }
}
```

```bash
nginx -t && systemctl reload nginx
```

访问 `http://your-server/teach/` 即可。

> ⚠️ **Nginx 注意事项**（踩坑记录）：
> - `^~` 修饰符确保 `/teach` 优先匹配，避免被默认 root 覆盖
> - `alias` 末尾必须有 `/`，否则静态资源 404
> - 不要嵌套静态 location，会导致 CSS/JS 404
> - `proxy_buffering off` 是 SSE 流式输出必需
> - `sites-enabled` 目录不要留备份文件（含 `default_server` 会冲突）

---

## 📡 API 速览

所有接口挂载在 `/api` 前缀下（Nginx 转发后为 `/teach/api/`）。

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 健康 | GET | `/api/health` | 服务健康检查 + 向量库统计 |
| 健康 | GET | `/api/stats/tokens` | Token 用量统计（总量/按模型/最近 5 条） |
| 收集箱 | GET/POST | `/api/inbox` | 收集箱 CRUD |
| 日程 | GET/POST | `/api/schedule` | 日程 CRUD |
| 阅读 | POST | `/api/reading/upload` | 上传文档（PDF/Word/TXT/MD） |
| 阅读 | POST | `/api/reading/rebuild-kb` | 重建向量库 |
| 阅读 | GET | `/api/reading/docs` | 文档列表 |
| AI | GET/POST | `/api/sessions` | 会话管理 |
| AI | POST | `/api/ai/ask` | 同步 RAG 问答 |
| AI | GET/POST | `/api/ai/stream` | SSE 流式 RAG 问答 |
| 工具 | POST | `/api/tools/generate` | 生成教案/课件/作业/论文（RAG 增强） |
| 工具 | GET | `/api/tools/history` | 工具生成历史 |
| 设置 | GET/PUT | `/api/settings` | 读取/更新设置 |
| 设置 | POST | `/api/settings/test-key` | 测试 API Key 连通性 |
| 天气 | GET | `/api/weather` | 实时天气 + 未来 3 天预报 |

完整接口文档：启动后访问 `http://localhost:8777/docs`（FastAPI 自动生成的 Swagger UI）。

---

## 🔑 API Key 获取指南

| 服务 | 注册地址 | 用途 | 免费额度 |
|------|---------|------|---------|
| **DeepSeek** | https://platform.deepseek.com | 主 LLM（ChatCompletions） | 新用户 500 万 tokens |
| **智谱 AI** | https://open.bigmodel.cn | Embedding（embedding-3）+ 兜底 LLM（glm-4-flash） | 新用户 500 万 tokens |
| **和风天气** | https://dev.qweather.com | 天气兜底（必须用 **Web API Key**，不是 SDK 凭据） | 1000 次/天免费 |

> ⚠️ **和风天气 Key 类型**：和风有两类 Key —— ① SDK 凭据（用于 Android/iOS SDK，调 Web API 会 403）；② **Web API Key**（用于 HTTP 接口）。本项目需要的是 **Web API Key**。

---

## 🔒 安全说明

- ✅ 本仓库 **不含任何真实 API Key**：所有 key 在 `config.py` 中默认空字符串，部署脚本中的 key 均为占位符（如 `sk-YOUR_DEEPSEEK_KEY_HERE`）
- ✅ `.gitignore` 已排除：`.env`、`*.db`、`*.pkl`、`*.tar.gz`、`__pycache__/`、`teachupgarde/`（旧版备份）等
- ✅ Key 存储：SQLite `settings` 表（运行时数据库不入库）
- ✅ Key 读取：优先 DB > 环境变量 > 默认值，支持运行时热加载
- ✅ Key 归一化：`db.py` 中 `_KEY_NORMALIZE` 字典自动将小写键名（`deepseek_api_key`）转为大写（`DEEPSEEK_API_KEY`）

---

## 📚 学习资料

- [docs/HELP.md](docs/HELP.md) —— 教师使用手册
- [docs/LearningText.md](docs/LearningText.md) —— LangChain/LangGraph/React 源码解读 + 多 Agent + MCP + 国内生态（40KB）
- [docs/VibeCoding-Journey.md](docs/VibeCoding-Journey.md) —— Vibe Coding 思路梳理 + 架构决策 + 挑战解决 + 面试亮点（18KB）

---

## 🧭 待办 / Roadmap

- [x] RAG 增强教学工具（生成前先检索向量库注入 prompt）
- [x] Token 用量追踪（后端捕获 + 前端徽章 + 详情弹窗）
- [x] 国风 SVG 图标系统（12 枚，统一国风风格）
- [x] 诗句随机轮换（2010 首唐诗）
- [x] 双源天气（Open-Meteo 主 + 和风兜底）
- [x] GitHub 上传 + README + 帮助文档
- [ ] **多 Agent 路由**：DeepSeek 文本 / 智谱多模态，视频生成 / 教学动画 / 高级 PPT
- [ ] **Token 优化**：skill 流程化编排，缓存常见查询结果，score 阈值过滤

---

## 📄 License

MIT License — 仅供学习交流使用。

---

## 🙏 致谢

- [LangGraph](https://github.com/langchain-ai/langgraph) —— Agent 工作流编排
- [FAISS](https://github.com/facebookresearch/faiss) —— 向量检索
- [FastAPI](https://fastapi.tiangolo.com/) —— Web 框架
- [DeepSeek](https://www.deepseek.com/) —— LLM API
- [智谱 AI](https://www.zhipuai.cn/) —— Embedding + LLM
- [Open-Meteo](https://open-meteo.com/) —— 免费天气 API

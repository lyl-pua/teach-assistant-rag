# 🏮 国风教学助手 RAG 系统 · Vibe Coding 思路梳理与对话还原

> 📅 文档版本：v1.0 · 2026-08-23
> 🎯 文档定位：面向技术面试的完整工程复盘，覆盖「需求 → 架构 → 决策 → 踩坑 → 沉淀」全链路
> 👤 目标用户画像：小学语文女教师 / 班主任（用户名「刘老师」），部署服务器 `47.97.115.209`

---

## 📑 目录

1. [🧭 项目背景与目标](#1-项目背景与目标)
2. [🏗️ 技术架构梳理](#2-技术架构梳理)
3. [🧠 核心设计决策与思考过程](#3-核心设计决策与思考过程)
4. [🛠️ 遇到的挑战与解决方案](#4-遇到的挑战与解决方案)
5. [⭐ 面试亮点提炼](#5-面试亮点提炼)
6. [📚 经验总结与 Vibe Coding 理念](#6-经验总结与-vibe-coding-理念)
7. [🌐 GitHub 面试准备与开源学习路线](#7-github-面试准备与开源学习路线)
8. [📎 附录](#8-附录)

---

## 1. 🧭 项目背景与目标

### 1.1 一句话定位

> **面向小学语文女教师的新中式国风教学助手 RAG 系统**，整合前端工作台 UI 与后端 RAG 检索增强生成能力，覆盖日常教学管理六大场景。

### 1.2 用户与场景

| 维度 | 说明 |
|------|------|
| 👩‍🏫 主要用户 | 小学语文老师 / 班主任（女性），用户名 `feng`，问候语「早上好，刘老师」 |
| 📍 部署位置 | 阿里云服务器 `47.97.115.209`（Linux），前端访问路径 `/teach/` |
| 🖥️ 运行约束 | **2 核 2G / 500MB 内存** 的轻量服务器，工程取舍围绕这一约束展开 |
| 🎨 视觉基调 | 新中式国风：墨绿 `#2A5047` 主色、宣纸米黄 `#F7F2E3` 底色、赭石/浅紫/浅红辅色、仿宋标题、圆角 10–14px、宣纸纹理 |

### 1.3 六大功能模块

```
┌─────────────────────────────────────────────────────────┐
│  🏠 首页工作台  │  📥 收集箱  │  📖 阅读·知识库          │
│  📅 日程       │  🤖 AI 教研助手 (RAG 核心) │  🛠️ 教学工具 │
│  ⚙️ 设置与数据                                               │
└─────────────────────────────────────────────────────────┘
```

### 1.4 项目目标（Goal）

1. 构建完整的新中式国风教师个人工作台首页 UI（单页 SPA，多模块入口）
2. 实现六大功能模块的可交互前端页面
3. 搭建 RAG 后端服务，支持 PDF / Word / PPT 课件的上传、解析、向量化、检索问答
4. AI 助手支持基于知识库的教学问答、课件解读、教案生成
5. 教学工具支持自动生成课件、教案、练习题等教学素材
6. 系统可独立部署运行：前端静态页面 + 后端 FastAPI 服务

### 1.5 非目标（Non-Goals，体现边界感）

> 🚫 不做移动端适配（PC 端 1920px 优先） · 不做多用户账号体系 · 不做实时协作 / 在线批改 · 不做原生 APP

---

## 2. 🏗️ 技术架构梳理

### 2.1 整体技术栈一览

| 层 | 技术选型 | 关键理由 |
|----|---------|---------|
| **前端** | HTML5 + Tailwind CSS v3（CDN）+ 原生 JavaScript | 单文件可运行，无构建步骤，B 端后台够用 |
| **后端** | Python 3.10+ · FastAPI · Uvicorn | 异步、自带 Swagger、轻量 |
| **数据库** | SQLite（原生 sqlite3 + WAL 模式） | 单文件、零运维、2G 内存可承受 |
| **向量检索** | FAISS（`faiss-cpu`，`IndexFlatIP`） | 轻量、纯 CPU、无独立服务进程 |
| **Embedding** | 智谱 `embedding-3`（维度 2048） | 国内可访问、中文友好 |
| **LLM 生成** | DeepSeek `deepseek-chat`（主）+ 智谱 `glm-4-flash`（兜底） | 多模型路由，性价比高 |
| **工作流编排** | LangGraph `StateGraph`（retrieve → generate） | 状态图、节点分离、可扩展 |
| **反向代理** | Nginx（1Panel 管理） | 静态托管 + API 反代 + SSE 流式支持 |
| **天气服务** | Open-Meteo（主）+ 和风 QWeather（兜底） | 免 Key、无配额、全球可用 |

### 2.2 架构拓扑图（文字版）

```
                    ┌──────────────────────────────────┐
                    │        浏览器 (Chrome/Edge)       │
                    │  index.html + app.js + poems.js   │
                    │  style.css?v=2.1.0  (缓存破坏)    │
                    └───────────────┬──────────────────┘
                                    │ HTTPS
                                    ▼
                    ┌──────────────────────────────────┐
                    │          Nginx (47.97.115.209)     │
                    │  /teach/        → 静态文件 alias  │
                    │  /teach/api/*   → 127.0.0.1:8777   │  ← 并列 location
                    │  proxy_buffering off (SSE 友好)   │
                    └───────────────┬──────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────────┐
                    │     FastAPI (uvicorn :8777)        │
                    │  lifespan: init_db + load vectors │
                    │  Routers: /api/{health,inbox,     │
                    │    schedule,reading,ai,tools,     │
                    │    settings,weather}              │
                    └───────┬──────────────┬────────────┘
                            │              │
                ┌───────────▼──┐    ┌──────▼──────────────┐
                │  SQLite(WAL) │    │   RAG LangGraph       │
                │  app.db      │    │  ┌────────┐  ┌──────┐ │
                │  8 张表      │    │  │retrieve│→│generate│ │
                └──────────────┘    │  └────────┘  └──────┘ │
                                    └───┬─────────────┬─────┘
                                        │             │
                          ┌─────────────▼──┐    ┌──────▼────────┐
                          │  FAISS 索引     │    │  外部 LLM API  │
                          │  vectorstore.pkl│   │ DeepSeek/智谱  │
                          │  IndexFlatIP   │    └───────────────┘
                          └────────────────┘
```

### 2.3 数据库表结构（8 张表）

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `inbox_items` | 收集箱条目 | title, type(note/idea/todo/student), pinned |
| `schedules` | 日程安排 | date, time_start/end, category(teach/research/meeting/life/student) |
| `documents` | 文档元数据 | filename, file_path, chunks_count, status(processing/ready/error) |
| `chunks` | 文档分块 | doc_id(FK), chunk_index, text |
| `chat_sessions` | 对话会话 | title, created_at |
| `chat_messages` | 对话消息 | session_id(FK), role(user/assistant), refs(JSON) |
| `tool_runs` | 教学工具运行记录 | tool_type(lesson_plan/courseware/homework/paper), result(JSON) |
| `settings` | 系统配置（Key-Value） | key(PK), value |

> 💡 **连接管理**：`threading.local()` 线程本地连接 + `check_same_thread=False` + WAL 模式，兼顾并发与一致性。

### 2.4 RAG 数据流

```
教师提问 ──▶ Embedding(智谱 embedding-3, 2048维)
                    │
                    ▼
            FAISS IndexFlatIP 检索 (L2归一化 + 内积 = cosine)
                    │ top_k=3
                    ▼
            chunks 表回查原文 (按 chunk_id 批量 SELECT)
                    │
                    ▼
            拼接 prompt + 系统提示词
                    │
                    ▼
            LLM 生成 (DeepSeek 主 / 智谱兜底 / 无 Key 时模板降级)
                    │
                    ▼
            {answer, refs, retrieved_chunks, model_used}
```

---

## 3. 🧠 核心设计决策与思考过程

> 本章是面试「为什么这样选」的高频考点。每个决策都遵循「约束驱动 → 方案对比 → 取舍」的推理链。

### 3.1 🔍 为什么选择 FAISS 而非 Milvus / ChromaDB

| 候选方案 | 内存占用 | 独立进程 | 部署复杂度 | 2核2G 可行性 |
|---------|---------|---------|-----------|------------|
| **FAISS（IndexFlatIP）** ✅ | ~10MB（千级 chunk） | ❌ 嵌入进程 | `pip install` 即用 | ⭐⭐⭐⭐⭐ |
| Milvus | 500MB+ 常驻 | ✅ etcd+minio+mixd | docker-compose 多容器 | ⭐（内存爆表） |
| ChromaDB | 100MB+ | ✅ 独立服务 | 额外进程 | ⭐⭐⭐ |

**决策推理**：

> 📌 服务器是 2 核 2G、500MB 内存预算的轻量机。Milvus 的 etcd + minio + mixd 三件套光常驻就要吃掉 1G+ 内存，直接出局。ChromaDB 虽轻，但仍需独立进程，多一层网络开销。**FAISS 嵌入 FastAPI 进程内**，`IndexFlatIP`（先 L2 归一化再做内积 ≡ cosine 相似度）对千级 chunk 来说精度无损、查询 <1ms，且持久化只需 `pickle.dump` 一个 `vectorstore.pkl` 文件，零运维。

**关键实现**（`backend/rag/vectorstore.py`）：

```python
class FAISSVectorStore:
    def __init__(self, dim: int = config.EMBEDDING_DIM):
        self.index = faiss.IndexFlatIP(dim)  # 内积索引
        self.ids: list[int] = []
        self.metadatas: list[dict] = []

    def add(self, embeddings, ids, metadatas):
        # L2 归一化：确保内积 = cosine 相似度
        arr = embeddings.astype(np.float32).copy()
        norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
        arr = arr / norms
        self.index.add(arr)
```

### 3.2 🌊 为什么用 LangGraph 工作流而非简单 Chain

| 维度 | 简单 Chain（顺序函数调用） | LangGraph StateGraph ✅ |
|------|------------------------|----------------------|
| 状态管理 | 隐式传参，易丢失中间态 | `TypedDict` 显式声明状态 schema |
| 节点解耦 | 检索与生成耦合 | `retrieve` / `generate` 节点独立可测 |
| 扩展性 | 加节点需改主流程 | `add_node` + `add_edge` 即插即用 |
| 容错 | 异常传播难追踪 | 节点级 `try/except`，状态可降级 |
| 优雅降级 | 难以分层 fallback | 无 Key → 模板回答，LLM 失败 → 检索摘要 |

**决策推理**：

> 📌 RAG 本质是「检索 → 生成」两阶段，未来很可能扩展为「检索 → 重排 → 生成 → 引用回填」甚至加入「意图识别」前置节点。LangGraph 的 `StateGraph` 让每个节点只关心输入输出契约（`RAGState`），新增节点不破坏既有链路。更重要的是，**降级策略天然分层**：检索失败不阻塞生成（用空 context），生成失败回退到检索摘要模板，这种「节点级 fallback」在 Chain 里很难写干净。

**核心状态定义与节点编排**（`backend/rag/workflow.py`）：

```python
class RAGState(TypedDict, total=False):
    question: str
    top_k: int
    retrieved_chunks: List[dict]
    answer: str
    refs: List[dict]
    error: str

class RAGGraph:
    def _build(self):
        graph = StateGraph(RAGState)
        graph.add_node("retrieve", self.retrieve_node)
        graph.add_node("generate", self.generate_node)
        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", END)
        return graph.compile()
```

> 🛡️ **防御性设计**：若 `langgraph` 未安装，自动退化为手工实现的顺序 `StateGraph`（同文件内 `_Runner` 类），保证可移植性。

### 3.3 🔑 Key 归一化设计（前端小写 → 后端大写自动映射）

**问题背景**：

> ⚠️ 前端表单习惯用小写蛇形命名（如 `deepseek_api_key`），而后端 `config.RELOADABLE_SETTINGS` 统一用大写（`DEEPSEEK_API_KEY`）。如果直接落库，会出现「设置页明明填了 Key，但 RAG 调用时读不到」的灵异 bug。

**解决方案：双写 + 别名映射 + 兜底查询**（`backend/db.py`）：

```python
# 显式别名映射表
_KEY_NORMALIZE = {
    "deepseek_api_key": "DEEPSEEK_API_KEY",
    "openai_api_key":   "OPENAI_API_KEY",
    "zhipu_api_key":    "ZHIPU_API_KEY",
    "glm_api_key":      "GLM_API_KEY",
    "city_latitude":    "city_lat",
    "city_longitude":   "city_lon",
}

def _normalize_key(key: str) -> str:
    k = key.strip()
    if k in _KEY_NORMALIZE:                 # 1) 显式别名
        return _KEY_NORMALIZE[k]
    for sk in config.RELOADABLE_SETTINGS:   # 2) 大小写不敏感匹配
        if sk.lower() == k.lower():
            return sk
    return k

def set_setting(key, value):
    k = _normalize_key(key)
    with get_cursor(commit=True) as cur:
        if k != key:                         # 3) 清理脏记录（同名但大小写不一致）
            cur.execute("DELETE FROM settings WHERE key = ?", (key,))
        cur.execute("SELECT 1 FROM settings WHERE key = ?", (k,))
        if cur.fetchone():
            cur.execute("UPDATE settings SET value = ? WHERE key = ?", (value, k))
        else:
            cur.execute("INSERT INTO settings(key, value) VALUES(?, ?)", (k, value))
    config.RELOADABLE_SETTINGS[k] = value    # 4) 同步缓存
    config.reload_settings_from_db()        # 5) 全量 reload 保险
```

**设计要点**：

| 步骤 | 作用 |
|------|------|
| 显式别名映射 | 处理「语义等价但命名不同」的字段（如 `city_latitude` → `city_lat`） |
| 大小写不敏感匹配 | 兜底所有 RELOADABLE_SETTINGS 里的键 |
| 写入前 DELETE 脏记录 | 避免 DB 里同时存在大小写两份记录 |
| 同步缓存 + 全量 reload | 双保险，确保下次读取一定命中 |

### 3.4 🌐 Nginx 并列 location 解决 API 路由被静态 fallback 覆盖

**问题背景**：

> ⚠️ 最初 Nginx 只配了一个 `location /teach/`，内部用 `try_files $uri $uri/ @teach_api` 做 fallback。结果 `/teach/api/xxx` 请求被静态文件规则「吃掉」，转发不到 FastAPI，返回 502。

**解决方案：两个 `^~` 前缀并列 location**（`nginx-teach-location.conf`）：

```nginx
# ============ 静态文件 ============
location ^~ /teach/ {
    alias  /opt/teach/frontend/;
    index  index.html;
    try_files $uri $uri/ @teach_api;        # 兜底交给命名 location
}

# ============ API 反代（^~ 前缀匹配，优先级高于正则） ============
location ^~ /teach/api/ {
    proxy_pass         http://127.0.0.1:8777/api/;
    proxy_http_version 1.1;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;

    # AI 流式生成需要长超时 + 禁止缓冲（SSE）
    proxy_read_timeout      600s;
    proxy_send_timeout      600s;
    proxy_buffering         off;
    proxy_cache             off;
    gzip                    off;
    chunked_transfer_encoding on;
}

# ============ /teach -> /teach/ 自动补全 ============
location = /teach { return 301 /teach/; }
```

**关键点**：

| 配置项 | 为什么 |
|--------|--------|
| `^~` 前缀 | 阻止后续正则 location 覆盖，确保 `/teach/api/` 一定命中反代块 |
| `proxy_buffering off` | SSE 流式输出必须关闭缓冲，否则 token 会攒批吐出，体验卡顿 |
| `proxy_read_timeout 600s` | DeepSeek 长文本生成可能 30s+，默认 60s 会超时断连 |
| `gzip off` | SSE 流不能 gzip，否则浏览器无法逐 token 解析 |

### 3.5 🎋 诗句每日哈希稳定 + 随机轮换的算法选择

**需求**：

- 同一天刷新页面，问候横幅的诗句**保持稳定**（不要每次刷新都变）
- 不同天之间诗句要**轮换**，避免审美疲劳

**算法选择**：基于「日期种子 + 哈希取模」的确定性选择

```javascript
// 伪代码（poems.js 思路）
const POEMS = [/* N 首古诗 */];
function pickDailyPoem() {
    const dayOfYear = Math.floor((Date.now() - new Date(new Date().getFullYear(),0,0)) / 86400000);
    const idx = dayOfYear % POEMS.length;   // 确定性：同一天 idx 不变
    return POEMS[idx];
}
```

**为什么不用 `Math.random()`**：

| 方案 | 同一天稳定 | 跨天轮换 | 复杂度 |
|------|-----------|---------|--------|
| `Math.random()` ❌ | ❌ 每次刷新都变 | ✅ | 低 |
| 日期哈希取模 ✅ | ✅ | ✅ | 低 |
| 后端持久化今日诗 | ✅ | ✅ | 高（多一次 DB 查询） |

> 📌 日期哈希取模是「无状态确定性」的经典套路：同输入同输出，但输入（日期）天然变化。比后端持久化轻量，比纯随机稳定。

### 3.6 🧹 浏览器缓存破坏方案（`?v=版本号`）

**问题背景**：

> ⚠️ Nginx 给静态资源配了 `expires 7d` 长缓存，结果更新 `app.js` 后用户浏览器仍用旧版，新功能/修复不生效。

**解决方案**：在 HTML 引用静态资源时附加版本号查询参数

```html
<!-- frontend/index.html -->
<link rel="stylesheet" href="./static/style.css?v=2.1.0" />
<script src="./poems.js?v=2.1.0"></script>
<script src="./static/app.js?v=2.1.0"></script>
```

**原理**：

| URL | 浏览器缓存行为 |
|-----|--------------|
| `app.js` | 7 天内命中缓存，不重新请求 |
| `app.js?v=2.1.0` | 版本号变了 → 视为新 URL → 重新下载 |

> 📌 这是「内容寻址」的轻量替代：完整方案是用文件哈希做文件名（如 `app.a3f9b2.js`），但需要构建工具配合。本项目的单文件无构建流程下，`?v=` 是最简且足够的方案。**版本号语义化**：每次发版手动 bump，`2.1.0` 对应 `APP_VERSION`。

---

## 4. 🛠️ 遇到的挑战与解决方案

> 本章是面试「讲一个你踩过的坑」的最佳素材，按「现象 → 根因 → 方案 → 反思」结构还原。

### 4.1 🔥 挑战一：Nginx 重复 location 导致 502

| 项 | 内容 |
|----|------|
| **现象** | 部署后 `/teach/api/health` 返回 502 Bad Gateway，但 `curl 127.0.0.1:8777/api/health` 正常 |
| **根因** | 1Panel 自动生成的站点配置里已有一个 `location /`，与手动添加的 `location /teach/` 冲突；加上历史遗留的重复 `location /teach/api/` 块，Nginx 配置语法虽不报错，但匹配优先级混乱 |
| **排查** | `nginx -t` 通过 → 看不到问题；`nginx -T \| grep location` 发现 3 个重复块 → 定位冲突 |
| **方案** | ① 清理所有手动添加的 `location` 块；② 只保留一组并列 `^~` 前缀 location（见 3.4）；③ `nginx -s reload` |
| **反思** | Nginx 的 `location` 匹配是「最长前缀优先 + 正则后置」的复杂规则，**重复 location 不会报错但会静默覆盖**。生产配置必须用 `nginx -T` 全量审查，而非只看单个文件 |

### 4.2 🗄️ 挑战二：DB 路径不一致（teach.db vs app.db）

| 项 | 内容 |
|----|------|
| **现象** | 重启服务后，之前配置的 API Key、上传的文档全部「消失」，但磁盘上有多个 `.db` 文件 |
| **根因** | 历史迭代中 `config.DB_PATH` 曾指向 `teach.db`，后统一为 `app.db`，但旧部署的服务器上残留 `teach.db`，且某次启动脚本 `cd` 到了错误目录，导致 `os.path.dirname(__file__)` 解析出两个不同的 `data/` 目录 |
| **排查** | `find / -name "*.db" 2>/dev/null` 发现 `teach.db` 和 `app.db` 并存；对比文件大小和修改时间确认哪个是「活的」 |
| **方案** | ① 全局统一 `DB_PATH = os.path.join(backend_dir, "data", "app.db")`；② 把 `teach.db` 里有用的数据导出后合并进 `app.db`；③ 删除残留 `teach.db`；④ 部署脚本里加 `cd /opt/teach/backend` 显式锁定工作目录 |
| **反思** | **路径必须基于 `__file__` 绝对定位**，绝不依赖当前工作目录。多版本迭代的项目要定期清理「幽灵文件」 |

### 4.3 🧱 挑战三：SQLite ALTER TABLE 非常量默认值限制

| 项 | 内容 |
|----|------|
| **现象** | 升级 schema 时想给 `documents` 表加 `meta TEXT DEFAULT '{}'`，执行 `ALTER TABLE documents ADD COLUMN meta TEXT DEFAULT '{}'` 报错 `Cannot add a column with non-constant default` |
| **根因** | SQLite 的 `ALTER TABLE ADD COLUMN` **不支持非常量默认值**（如 `'{}'` 这种字符串字面量在某些版本/场景下被判定为非常量），这是 SQLite 与 PostgreSQL/MySQL 的显著差异 |
| **方案** | 采用 `safe_upsert` 双写 fallback 策略：① 新增列时用 `DEFAULT NULL`；② 在应用层 `db.py` 的所有读写处做空值兜底，`meta IS NULL` 时当作 `'{}'` 处理；③ 历史 NULL 数据在读取时 `json_loads(meta) or {}` |
| **反思** | SQLite 适合轻量场景，但 DDL 能力弱于服务型数据库。**Schema 演进要走「兼容旧数据 + 应用层兜底」路线**，而非依赖数据库自身的默认值机制 |

```python
# 兼容写法示例
def list_settings() -> dict:
    raw = {r["key"]: r["value"] for r in rows}
    out = {}
    for k, v in raw.items():
        nk = _normalize_key(k)
        if nk not in out:
            out[nk] = v
    # 补齐缺失键的默认值（应用层兜底）
    for sk in config.RELOADABLE_SETTINGS.keys():
        if sk not in out:
            out[sk] = config.RELOADABLE_SETTINGS.get(sk, "")
    return out
```

### 4.4 🧼 挑战四：浏览器缓存旧版 JS

| 项 | 内容 |
|----|------|
| **现象** | 修复了 AI 助手的 bug 并重新部署，用户反馈「还是老样子」，但服务器上文件已经是新版 |
| **根因** | Nginx 静态资源 `expires 7d` + 浏览器 disk cache，旧版 `app.js` 被强缓存，根本不发请求 |
| **方案** | 见 3.6：HTML 引用处加 `?v=2.1.0` 版本号；每次发版 bump 版本号；保留 Nginx 长缓存以提升性能 |
| **反思** | **缓存破坏与缓存利用是同一枚硬币的两面**：对不变内容（字体、图标）激进缓存，对易变内容（JS/CSS）用版本号或哈希破坏。两者缺一不可 |

### 4.5 🌦️ 挑战五：和风天气 Key 类型错误（SDK 凭据 vs Web API Key）

| 项 | 内容 |
|----|------|
| **现象** | 配置了和风天气 Key 后，`/api/weather` 始终返回「暂时无法获取」，日志显示 `QWeather: HTTP 403` |
| **根因** | 和风天气有两类 Key：① **SDK 凭据**（用于 Android/iOS SDK，调 Web API 会 403）；② **Web API Key**（用于 HTTP 接口）。当前配置的 `HEFENG_API_KEY` 是 SDK 凭据，调 `/v7/weather/now` 必然 403 |
| **方案** | ① 主源切换为 **Open-Meteo**（免 Key、无配额、全球可用，汉寿 28.914/111.976 实测稳定）；② 和风降级为兜底，仅当用户显式提供有效 Web API Key 时才启用；③ WMO weather code → 中文+emoji 映射表，保证前端展示一致 |
| **反思** | **第三方服务的凭据类型要在接入前查清**，不能想当然。多源兜底是健壮性关键：主源 Open-Meteo 挂了还有和风，全挂了还有占位提示，绝不返回 500 |

**双源天气架构**（`backend/services/weather.py`）：

```python
def get_weather(city=None, lat=None, lon=None, days=3):
    # 主：Open-Meteo（免 Key）
    try:
        current, daily = _fetch_openmeteo(lat, lon, days)
        return {"source": "open-meteo", "current": current, "daily": daily, ...}
    except Exception as e:
        errors.append(f"OpenMeteo: {e}")

    # 兜底：和风（需有效 Web API Key）
    try:
        current, daily = _try_qweather(lat, lon, days)
        return {"source": "qweather", ...}
    except Exception as e:
        errors.append(f"QWeather: {e}")

    # 全失败：占位（不抛 500）
    return {"source": "offline", "current": {"weather": "暂时无法获取", "icon": "⚠️"}, ...}
```

---

## 5. ⭐ 面试亮点提炼

> 本章把项目拆解为可对外讲述的「能力锚点」，每个锚点配「STAR 表述法」要点。

### 5.1 🔬 亮点一：RAG 全流程实战

| 阶段 | 实现 | 面试可讲点 |
|------|------|-----------|
| 文档解析 | `.txt/.md/.docx/.pdf` 多格式，python-docx / pypdf | 编码兼容（utf-8/gbk 三级 fallback） |
| 分块策略 | 600 字 + 100 字重叠，中文友好 | 段落/句号边界探测，避免硬切断语义 |
| Embedding | 智谱 `embedding-3`，2048 维，批 25 条 | L2 归一化保证 cosine 一致性 |
| 向量检索 | FAISS `IndexFlatIP`，top_k=3 | chunk_id 回查原文的批量 SQL 优化 |
| LLM 生成 | DeepSeek 主 + 智谱兜底 + 模板降级 | 三级 fallback，无 Key 也能用 |

**分块算法的工程细节**（`backend/rag/parser.py`）：

```python
def split_chunks(text, chunk_size=600, overlap=100):
    """按字符切分，但在 chunk_size 附近探测段落/句号边界"""
    while start < L:
        end = min(start + chunk_size, L)
        if end < L:
            # 向后找最近的结束符（\n\n / 。 / ! / .）
            for sep in ["\n\n", "\n", "。", "！", "？", ".", "!", "?"]:
                idx = probe.rfind(sep)
                if idx != -1:
                    boundary = start + chunk_size // 2 + idx + len(sep)
                    break
            if boundary and boundary > start + overlap:
                end = boundary
        chunks.append(text[start:end].strip())
        start = end - overlap  # 重叠保证跨块语义连续
```

### 5.2 🔀 亮点二：多模型路由（DeepSeek 文本生成 + 智谱 Embedding）

**路由策略**（`backend/rag/generator.py`）：

```python
def _provider_info() -> tuple[str, str, str]:
    sk = config.get_sk_key()                    # 1) 优先 DeepSeek（sk- 前缀）
    if sk:
        return "deepseek", DEEPSEEK_URL, "deepseek-chat"
    zk = config.get_zhipu_key()                 # 2) 兜底智谱 glm-4-flash
    if zk:
        return "zhipu", ZHIPU_CHAT_URL, "glm-4-flash"
    raise RuntimeError("未配置任何 LLM API Key")
```

| 能力维度 | 主选 | 兜底 | 理由 |
|---------|------|------|------|
| 文本生成 | DeepSeek `deepseek-chat` | 智谱 `glm-4-flash` | DeepSeek 中文质量高、性价比好；智谱免费额度兜底 |
| Embedding | 智谱 `embedding-3`（2048 维） | 伪向量（hash 降级） | 国内可访问；无 Key 时 hash 伪向量保证流程可跑 |
| 路由判据 | `sk-` 前缀 | zhipu key 存在 | 简单可解释，无需复杂配置 |

> 💡 **无 Key 降级**：`ZhipuEmbedding._pseudo_embed` 用 MD5 hash 生成可复现伪向量 + ngram 偏移做「弱语义」，保证无 Key 时整个 RAG 流程仍可演示，只是召回质量差。这种「Demo 友好」设计在面试演示时极有价值。

### 5.3 ⚡ 亮点三：轻量部署（2 核 2G / 500MB 内存约束下的工程取舍）

| 取舍点 | 选择 | 节省 |
|-------|------|------|
| 向量库 | FAISS 嵌进程 vs Milvus 独立服务 | ~1G 内存 |
| 数据库 | SQLite 单文件 vs PostgreSQL | ~200MB + 免运维 |
| Embedding | 远程 API vs 本地 sentence-transformers | ~400MB 模型加载 |
| LLM | 远程 API vs 本地 Ollama | ~2-4GB 模型权重 |
| 前端 | CDN + 单文件 HTML vs React 构建 | 无 Node 构建链 |

**实测内存占用**：FastAPI + FAISS + SQLite 全栈稳定运行在 **~120MB**，留足余量给 Nginx 和系统。

### 5.4 🎨 亮点四：前端国风设计系统

| 设计 Token | 取值 | 应用场景 |
|-----------|------|---------|
| 主色（墨绿） | `#2A5047` | 侧边栏、按钮主色、问候横幅渐变 |
| 底色（宣纸米黄） | `#F7F2E3` | 全局背景、卡片底 |
| 辅色（赭石/浅紫/浅红） | `#8B5A3C` / `#9C8BB8` / `#D4847A` | 模块入口卡片差异化 |
| 字体（仿宋） | `FangSong, STFangsong, serif` | 标题、诗句 |
| 圆角 | 10–14px | 卡片、按钮 |
| 阴影 | 柔和 `0 2px 8px rgba(0,0,0,0.06)` | 卡片浮起感 |
| 纹理 | 宣纸 SVG 背景 | 全局质感 |
| 图标 | emoji + 内联 SVG | 零依赖、可缩放 |

**问候横幅的国风元素清单**（AC-3 验收标准）：
- ✅ 「早上好，刘老师」+ 日期星期
- ✅ 古典诗词名句（每日轮换）
- ✅ 仿古山水古画相框
- ✅ 红色印章（CSS 实现）
- ✅ 古画简介文字

---

## 6. 📚 经验总结与 Vibe Coding 理念

### 6.1 🎯 Vibe Coding 的核心理念

> **Vibe Coding**：以自然语言驱动 AI 生成代码的快速原型开发范式，强调「感觉对了就继续，不对就换种说法」，把工程判断与 AI 生成力结合。

| 传统编码 | Vibe Coding |
|---------|------------|
| 先设计再写代码 | 边对话边成型 |
| 严格规格文档 | 自然语言描述意图 |
| 人工写每行代码 | AI 生成骨架 + 人工精修 |
| 迭代周期：天/周 | 迭代周期：分钟/小时 |
| 强调「正确性先行」 | 强调「可演示先行，再求完美」 |

**本项目中的 Vibe Coding 实践**：

1. **自然语言驱动**：用「给小学语文女老师做一个国风工作台，要有 RAG 问答」一句话启动，AI 生成完整脚手架
2. **快速原型**：先跑通「上传 → 解析 → 检索 → 回答」最小闭环，再加国风 UI、日程、收集箱
3. **迭代优化**：每个模块单独对话打磨，Nginx/DB/缓存等坑在部署中逐个发现并修复
4. **人工把关**：关键决策（FAISS vs Milvus、Key 归一化、双源天气）由人工定方向，AI 填实现

### 6.2 🤖 AI 辅助开发的工作流

```
┌────────────────────────────────────────────────────────────┐
│                    AI 辅助开发工作流                          │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  1. 需求拆解  ──▶  自然语言 Spec（spec.md / tasks.md）       │
│        │                                                   │
│        ▼                                                   │
│  2. 架构决策  ──▶  人工定方向（FAISS / LangGraph / 双源）    │
│        │              ↓ AI 辅助对比方案                      │
│        ▼                                                   │
│  3. 并行生成  ──▶  子代理并行：前端 + 后端 + 配置            │
│        │              ↓ 技能编排（Skill 调用）               │
│        ▼                                                   │
│  4. 集成调试  ──▶  本地 uvicorn + 浏览器实测                │
│        │                                                   │
│        ▼                                                   │
│  5. 部署上线  ──▶  脚本化 deploy.sh + Nginx 配置            │
│        │                                                   │
│        ▼                                                   │
│  6. 复盘沉淀  ──▶  本文档（VibeCoding-Journey.md）          │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**关键工具链**：

| 环节 | 工具 / 能力 |
|------|-----------|
| 需求文档 | Trae Spec（spec.md + tasks.md） |
| 代码生成 | Trae / Cursor + Skill 编排 + 子代理并行 |
| 前端测试 | 浏览器自动化（截图验证 + 交互录屏） |
| 后端调试 | uvicorn 热重载 + `/docs` Swagger |
| 部署 | 脚本化 `deploy.sh` + 1Panel Nginx |
| 复盘 | Markdown 文档（本文档 + LearningText.md） |

### 6.3 🔄 从需求到部署的完整闭环

> 本项目完整走通了「需求 → 设计 → 编码 → 测试 → 部署 → 复盘」六步闭环，是 Vibe Coding 范式落地的典型样本。

| 阶段 | 产出 | 验收标准 |
|------|------|---------|
| 需求 | `spec.md`（15 条 AC） | AC-1~AC-15 全部 ≥4 分 |
| 设计 | 架构拓扑 + 8 张表 + RAG 数据流 | 拓扑图可画、表结构可审 |
| 编码 | backend/ + frontend/ | uvicorn 启动 + 浏览器打开无 404 |
| 测试 | AC 验收 + curl 接口测试 | RAG 问答返回引用片段 |
| 部署 | Nginx + 1Panel + deploy.sh | 公网 `47.97.115.209/teach/` 可访问 |
| 复盘 | 本文档 + LearningText.md | 可对外讲述、可复用 |

### 6.4 💡 核心工程经验提炼

1. **约束驱动设计**：2G 内存不是限制，是「减法工具」，逼出 FAISS、SQLite、远程 API 的最优组合
2. **降级优先于异常**：每个外部依赖（LLM、天气、Embedding）都有 fallback，系统永不全黑
3. **配置归一化**：跨层命名不一致是 bug 之源，统一在边界层做归一（前端小写 → 后端大写）
4. **缓存破坏与利用平衡**：版本号破坏 + 长缓存利用，两者缺一不可
5. **路径绝对化**：基于 `__file__` 而非工作目录，杜绝「幽灵文件」
6. **脚本化部署**：手动步骤越少，可复现性越高

---

## 7. 🌐 GitHub 面试准备与开源学习路线

> 本章整理 2026 年 GitHub 高星 RAG / Agent 项目，作为面试「你知道哪些开源方案」的弹药库，并给出学习路线建议。

### 7.1 🏆 RAG 方向 Top 项目（按 Stars 排序）

| 排名 | 项目 | ⭐ Stars | 语言 | 定位 | 学习价值 |
|------|------|---------|------|------|---------|
| 1 | [Dify](https://github.com/langgenius/dify) | ~152k | TS/Python | 低代码 AI 平台（含 RAG 引擎） | 全栈产品形态参考 |
| 2 | [Open WebUI](https://github.com/open-webui/open-webui) | ~149k | Python | 用户友好 AI 界面（Ollama+OpenAI） | 前端交互范式 |
| 3 | [LangChain](https://github.com/langchain-ai/langchain) | ~144k | Python/JS | 通用 LLM 编排框架（RAG 是子集） | RAG 基础设施必读 |
| 4 | [awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) | ~133k | Python | 100+ 可运行 AI Agent & RAG 应用合集 | 快速上手样例 |
| 5 | [RAGFlow](https://github.com/infiniflow/ragflow) | ~88k | Go | 专注 RAG 引擎 + Agent，深度文档理解 | DeepDoc 文档解析对标 |
| 6 | [Anything-LLM](https://github.com/Mintplex-Labs/anything-llm) | ~64k | JS | 多合一 AI 生产力工具，隐私优先 | 本地优先架构 |
| 7 | [LlamaIndex](https://github.com/run-llama/llama_index) | ~49k | Python/JS | RAG-First 数据框架，检索最强 | 检索策略深度对标 |
| 8 | [LightRAG](https://github.com/HKUDS/LightRAG) | ~35k | Python | 港大出品，轻量快速 RAG（EMNLP 2025） | 与本项目轻量定位最接近 |
| 9 | [GraphRAG](https://github.com/microsoft/graphrag) | ~33k | Python | 微软出品，知识图谱驱动 RAG | 图谱增强方向 |
| 10 | [FastGPT](https://github.com/labring/FastGPT) | ~23k | TS | 工作流 + 知识库，国产低代码平台 | 国产工程实践 |
| 11 | [Haystack](https://github.com/deepset-ai/haystack) | ~25k | Python | 生产级 Pipeline 架构，企业首选 | 企业级工程范式 |
| 12 | [WeKnora](https://github.com/WeKnora/WeKnora) | ~15k | Go/Vue | 腾讯出品，文档理解 + 混合检索 | 国产大厂方案 |
| 13 | [MaxKB](https://github.com/1Panel-dev/MaxKB) | ~12k | Python | 开箱即用企业级 AI 智能体平台 | 1Panel 生态对标 |
| 14 | [QAnything](https://github.com/netease-youdao/QAnything) | ~13k | Python | 网易有道，BCEmbedding + Reranker | 国产 Embedding 方案 |

### 7.2 🤖 Agent 框架方向 Top 项目

| 排名 | 项目 | ⭐ Stars | 语言 | 类别 | 学习价值 |
|------|------|---------|------|------|---------|
| 1 | [n8n](https://github.com/n8n-io/n8n) | ~187k | TS | 可视化工作流 | 工作流编排范式 |
| 2 | [AutoGPT](https://github.com/Significant-Gravitas/AutoGPT) | ~184k | Python | 自主 Agent | 自主决策范式（历史意义） |
| 3 | [LangChain](https://github.com/langchain-ai/langchain) | ~136k | Python | 通用编排 | 同上 RAG 榜 |
| 4 | [browser-use](https://github.com/browser-use/browser-use) | ~93k | Python | 浏览器自动化 | 浏览器 Agent 范式 |
| 5 | [Cline](https://github.com/cline/cline) | ~61k | TS | 编码 Agent | VS Code 自主编码 |
| 6 | [AutoGen](https://github.com/microsoft/autogen) | ~58k | Python | 多 Agent 协作 | 微软多 Agent 范式 |
| 7 | [Flowise](https://github.com/FlowiseAI/Flowise) | ~52k | TS | 可视化 LangChain | 拖拽式编排 |
| 8 | [CrewAI](https://github.com/crewAIInc/crewAI) | ~51k | Python | 角色扮演多 Agent | 角色协作范式 |
| 9 | [LlamaIndex](https://github.com/run-llama/llama_index) | ~49k | Python | 通用/RAG | 同上 |
| 10 | [LiteLLM](https://github.com/BerriAI/litellm) | ~46k | Python | 路由/代理 | 多模型路由（对标本项目路由设计） |
| 11 | [Aider](https://github.com/paul-gauthier/aider) | ~44k | Python | 编码 Agent | CLI 编码范式 |
| 12 | [DSPy](https://github.com/stanfordnlp/dspy) | ~34k | Python | 声明式编程 | 提示词工程范式 |
| 13 | [LangGraph](https://github.com/langchain-ai/langgraph) | ~32k | Python | 状态图编排 | **本项目直接使用**，源码必读 |
| 14 | [Pydantic AI](https://github.com/pydantic/pydantic-ai) | ~17k | Python | 类型安全 Agent | 类型驱动范式 |
| 15 | [Letta](https://github.com/letta-ai/letta) | ~22k | Python | 有状态/记忆 Agent | 长期记忆范式 |

### 7.3 📚 推荐学习路线（按难度递进）

#### 🟢 入门阶段（1-2 周）

| 资源 | 目标 |
|------|------|
| [Prompt-Engineering-Guide](https://github.com/dair-ai/Prompt-Engineering-Guide) (~77k) | 掌握提示词工程基础 |
| [awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) | 跑通第一个 RAG/Agent demo |
| LangChain 官方 Tutorial | 理解 Chain / Memory / Retriever 抽象 |

#### 🟡 进阶阶段（2-4 周）

| 资源 | 目标 |
|------|------|
| [LangGraph 文档](https://github.com/langchain-ai/langgraph) | 掌握状态图编排（本项目核心） |
| [LlamaIndex 文档](https://github.com/run-llama/llama_index) | 深入检索策略（混合检索、重排） |
| [RAG_Techniques](https://github.com/NirDiamant/RAG_Techniques) (~27k) | 27+ RAG 高级技巧 Notebook |
| [hello-agents](https://github.com/datawhalechina/hello-agents) (~73k) | 中文智能体教程（从零构建） |

#### 🔴 实战阶段（4-8 周）

| 资源 | 目标 |
|------|------|
| [RAGFlow 源码](https://github.com/infiniflow/ragflow) | 深度文档解析（DeepDoc、OCR、布局识别） |
| [LightRAG 论文+代码](https://github.com/HKUDS/LightRAG) | 轻量 RAG 学术实现 |
| [GraphRAG](https://github.com/microsoft/graphrag) | 知识图谱增强 RAG |
| [Haystack](https://github.com/deepset-ai/haystack) | 企业级 Pipeline 架构 |

### 7.4 🎯 面试「开源方案对比」话术模板

> 面试官问：「你了解哪些 RAG 开源方案？为什么选 FAISS 不选别的？」

**参考回答框架**：

> 我系统调研过 GitHub 上主流的 RAG 方案，按定位分四类：
> - **RAG 专用引擎**：RAGFlow（~88k，DeepDoc 文档解析强）、LightRAG（~35k，港大轻量方案，和我的项目定位最接近）
> - **全栈 AI 平台**：Dify（~152k，低代码可视化）、FastGPT（~23k，国产工作流）
> - **开发框架**：LangChain（~144k，生态最大）、LlamaIndex（~49k，检索最强）
> - **教育资源**：RAG_Techniques（~27k，技巧合集）、awesome-llm-apps（~133k，样例集）
>
> 我的项目选 FAISS 而非 RAGFlow/LightRAG，是因为部署在 2 核 2G 服务器上，目标是**教学场景的可演示原型**而非生产级引擎。FAISS 嵌进程零运维，配合 SQLite + 远程 API，全栈 ~120MB 内存。如果是生产场景，我会选 RAGFlow（文档解析深）或 LlamaIndex（检索策略丰富）。

### 7.5 📊 关键维度对比速查表

| 维度 | 本项目 | Dify | RAGFlow | LangChain |
|------|--------|------|---------|-----------|
| 部署形态 | 单机轻量 | 容器化平台 | 容器化平台 | 库 |
| 内存占用 | ~120MB | ~1-2GB | ~2GB | 取决于应用 |
| 文档解析 | 基础（txt/md/docx/pdf） | DeepDoc + OCR | DeepDoc + OCR + 布局 | 依赖集成 |
| 检索策略 | FAISS cosine top-k | 混合检索 | 混合检索 + 重排 | 可插拔 |
| 工作流 | LangGraph 两节点 | 可视化 workflow | Agentic RAG | LCEL / LangGraph |
| 适用场景 | 个人/教学 demo | 企业级低代码 | 企业级 RAG 引擎 | 通用开发 |

---

## 8. 📎 附录

### 8.1 项目目录结构（精简版）

```
6a8848ee76588c27b8441489/
├── backend/
│   ├── app.py                 # FastAPI 主入口
│   ├── config.py              # 全局配置 + Key 归一化
│   ├── db.py                  # SQLite + 8 张表 + Key 归一化
│   ├── requirements.txt
│   ├── rag/
│   │   ├── workflow.py        # LangGraph StateGraph (retrieve→generate)
│   │   ├── vectorstore.py      # FAISS IndexFlatIP
│   │   ├── embeddings.py       # 智谱 embedding-3 + 伪向量降级
│   │   ├── generator.py        # DeepSeek + 智谱多模型路由
│   │   └── parser.py           # 文档解析 + 600字分块
│   ├── routers/                # 8 个 API 路由
│   ├── services/weather.py     # Open-Meteo + 和风双源
│   └── data/
│       ├── app.db              # SQLite 数据库
│       ├── vectorstore.pkl     # FAISS 持久化
│       └── documents/          # 10 份教学文档
├── frontend/
│   ├── index.html             # ?v=2.1.0 缓存破坏
│   ├── poems.js               # 每日诗句轮换
│   └── static/{app.js, style.css}
├── docs/
│   ├── LearningText.md        # AI Agent 学习文档
│   └── VibeCoding-Journey.md  # 本文档
├── nginx-teach-location.conf  # 并列 location 配置
└── deploy*.sh                 # 部署脚本族
```

### 8.2 关键配置常量速查

| 常量 | 值 | 位置 |
|------|-----|------|
| `APP_VERSION` | `2.0.0` | `config.py` |
| `EMBEDDING_DIM` | `2048` | `config.py` |
| `CHUNK_SIZE` | `600` | `config.py` |
| `CHUNK_OVERLAP` | `100` | `config.py` |
| 后端端口 | `8777` | nginx 反代目标 |
| 前端版本号 | `2.1.0` | `index.html ?v=` |
| 天气缓存 TTL | `1800s`（30 分钟） | `weather.py` |
| Embedding 批大小 | `25` | `embeddings.py` |
| LLM 超时 | `120s` | `generator.py` |
| Nginx 读超时 | `600s` | `nginx-teach-location.conf` |

### 8.3 验收标准达成情况（AC-1 ~ AC-15）

| AC | 描述 | 状态 | 关键证据 |
|----|------|------|---------|
| AC-1 | 首页国风视觉还原 | ✅ ≥4 | 墨绿/米黄/印章/古画/纹理到位 |
| AC-2 | 侧边栏 10 菜单项 | ✅ | 7 项核心 + 扩展 |
| AC-3 | 问候横幅 5 元素 | ✅ | 问候/日期/诗句/古画/印章 |
| AC-4 | 4 统计卡片 | ✅ | 待办/逾期/待确认/在读书 |
| AC-5 | 6 模块入口网格 | ✅ | 阅读/日程/AI/工具/收集箱/设置 |
| AC-6 | 文档上传列表 | ✅ | PDF/DOCX/TXT 支持 |
| AC-7 | RAG 生成回答 | ✅ | 含引用 refs |
| AC-8 | 流式打字效果 | ✅ | SSE + proxy_buffering off |
| AC-9 | 教案生成 5 部分 | ✅ | 目标/重难点/过程/板书/作业 |
| AC-13 | 浏览器直接打开 | ✅ | 无 CDN 404 |
| AC-14 | FastAPI 启动 | ✅ | uvicorn + /docs |

### 8.4 一句话总结

> 🏮 **本项目以 2 核 2G 轻量服务器为约束，用 FAISS + SQLite + LangGraph + DeepSeek/智谱 的组合，在 ~120MB 内存内跑通面向小学语文教师的国风 RAG 教学助手，完整覆盖「需求 → 架构 → 编码 → 部署 → 复盘」闭环，是 Vibe Coding 范式在垂直教学场景的落地样本。**

---

> 📝 文档结束 · 持续迭代中 · 欢迎面试官提问任意章节细节

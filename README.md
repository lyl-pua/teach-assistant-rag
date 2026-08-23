# 教学助手 · 国风 RAG 教研工作台

> 面向小学语文教师 / 班主任的新中式国风个人工作台，集成 **RAG 检索增强生成** 与 **千问多模态（图文理解 + 文生图）** AI 能力，覆盖日常教学管理六大核心场景。基于 FastAPI + LangGraph + FAISS + DeepSeek/GLM/千问构建，可一键部署在 2 核 2G 的轻量服务器上。

![version](https://img.shields.io/badge/version-2.4.0-2A5047)
![python](https://img.shields.io/badge/python-3.10+-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![multimodal](https://img.shields.io/badge/%E5%A4%9A%E6%A8%A1%E6%80%81-qwen--vl--plus%20%7C%20wanx--v1-orange)
![ppt](https://img.shields.io/badge/PPT-%E7%8E%BB%E7%92%83%E6%8B%9F%E6%80%81%E5%9B%BD%E9%A3%8E%E7%89%88-833F21)

<br />

***

## 🖼️ 功能截图一览

> 新中式国风 UI：墨绿 `#2A5047` / 宣纸米黄 `#F7F2E3` / 赭石 `#A56A3B` / 印章红 `#B4423B`，12 枚自研国风 SVG 图标，2010 首唐诗随机轮换。

|                                        🏠 首页工作台                                        |                                         📥 收集箱                                         |
| :------------------------------------------------------------------------------------: | :------------------------------------------------------------------------------------: |
| [![首页工作台](assets/screenshots/home-fullpage.png)](assets/screenshots/home-fullpage.png) | [![收集箱](assets/screenshots/inbox-fullpage.png)](assets/screenshots/inbox-fullpage.png) |

|                                        📖 阅读 · 知识库                                        |                                            📅 日程                                            |
| :---------------------------------------------------------------------------------------: | :-----------------------------------------------------------------------------------------: |
| [![阅读](assets/screenshots/reading-fullpage.png)](assets/screenshots/reading-fullpage.png) | [![日程](assets/screenshots/schedule-fullpage.png)](assets/screenshots/schedule-fullpage.png) |

|                                🤖 AI 教研助手（RAG + 多模态三面板）                                 |                            🛠️ 教学工具（教案 / 课件 / 作业 / 论文 / PPT）                             |
| :--------------------------------------------------------------------------------: | :-------------------------------------------------------------------------------------: |
| [![AI 助手](assets/screenshots/ai-fullpage.png)](assets/screenshots/ai-fullpage.png) | [![教学工具](assets/screenshots/tools-fullpage.png)](assets/screenshots/tools-fullpage.png) |

|                                 ⚙️ 设置与数据（Key 测试 / Token 统计）                                 |
| :-----------------------------------------------------------------------------------------: |
| [![设置](assets/screenshots/settings-fullpage.png)](assets/screenshots/settings-fullpage.png) |

***

## 🎞️ PPT 玻璃拟态国风 · 效果演示（v2.4 · 参考珞珈 PPT 课程规范）

> **设计规范**：青黛 / 墨蓝 / 茶褐 / 月白 / 朱砂 四色国色板 + 磨砂毛玻璃卡片（半透明、模糊背景、细白描边） + 宣纸纹理低多边形装饰 + 千文长文本自动分页 + 原文+注释双栏玻璃布局 + 逐行淡入/呼吸强调高级动画标记 + 讲者备注原生写入 PPTX。

|                                📋 目录（11 章磨砂玻璃导航卡）                                    |                                📖 原文精读（左原文 / 右注释 双栏）                                   |
| :-----------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------------------: |
|   [![PPT·目录页](assets/screenshots/ppt-02-toc.png)](assets/screenshots/ppt-02-toc.png)      | [![PPT·原文双栏](assets/screenshots/ppt-03-text-two-col.png)](assets/screenshots/ppt-03-text-two-col.png) |

|                                  🖌 赏析对比（阴晴对比玻璃卡）                                     |                                   🔖 重点字词（镂空字 + 边框修饰）                                   |
| :-----------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------------------: |
| [![PPT·赏析对比](assets/screenshots/ppt-05-analysis-compare.png)](assets/screenshots/ppt-05-analysis-compare.png) | [![PPT·重点字词](assets/screenshots/ppt-07-keywords.png)](assets/screenshots/ppt-07-keywords.png) |

**技术要点**（已内置在 Skill 规范中，大模型生成即遵守）：
- 固定 14–20 页结构：封面 / 目录 / 导入 / 原文2-4页 / 赏析3-5页 / 字词 / 探究 / 小结 / 作业 / 致谢
- 引用块 `>` = 磨砂玻璃卡片容器；`**粗体**` = 镂空字/边框修饰
- 千文拆分硬约束：每 4–6 句拆一页，名句独立玻璃卡片
- 每页自动写入：讲师备注 / 设计意图 / 动画标记；导出 PPTX 时 **notes 写入放映者视图**

***

## ✨ 项目亮点

### 核心能力

- **🎨 新中式国风 UI**：墨绿/米黄/赭石配色，宣纸纹理，仿宋字体，国风 SVG 图标系统（窗棂、锦囊、竹简、卷轴、印章等 12 枚），诗句随机轮换（内置 2010 首唐诗）
- **📚 RAG 智能问答**：基于 LangGraph 工作流（retrieve → generate），FAISS 向量检索 + DeepSeek/GLM 生成，参考资料溯源
- **🧠 多模态 AI · 前端可视化面板（v2.3）**：
  - **💬 文本问答（RAG）**：旧有知识库对话，默认面板
  - **🖼️ 视觉理解 qwen-vl-plus**：批改作业照片 / 识别教材页面 / 板书分析 / 课堂照片解读，前端三 Tab 直接粘贴图片 URL 提问并展示回答与 Token 用量
  - **🖌️ 文生图 wanx-v1（通义万相）**：古诗词配图 / 教学卡片插画 / 课堂海报 / 课文插画，支持 1024×1024 / 720×1280 / 1280×720 五种尺寸与数量选择，前端直接预览与右键保存
- **🛠️ 教学工具自动生成（v2.3 新增 PPT · v2.4 升级玻璃拟态）**：教案 / 课件 / 作业 / 论文 / **PPT 演示文稿** 5 类工具；PPT 工具按「封面 → 目录 → 导入 → 原文2-4页 → 赏析3-5页 → 字词 → 探究 → 小结 → 作业 → 封底」生成 14–20 页玻璃拟态国风 Markdown，前端**磨砂玻璃卡片**+**原文/注释双栏**+**逐行淡入 CSS 动画**预览，后端 python-pptx 一键导出带**讲者备注 / 动画标记 / 玻璃圆角形状**的 .pptx

### Token 优化体系

- **score 阈值过滤**：相似度 < 0.30 的检索 chunk 直接丢弃
- **chunk 文本截断**：单 chunk 注入 prompt 最长 500 字
- **分工具 max\_tokens 调优**：教案=3000 / 课件=2000 / 作业=1500 / 论文=3500 / **PPT=3000**
- **LLM 查询内存缓存**：temperature ≤ 0.5 的相同请求 5 分钟内命中缓存（LRU，上限 200 条）
- **动态 max\_tokens**：AI 对话按问题长度 + 检索 chunk 数动态调整

### 工程 & 部署

- **📊 Token 用量追踪**：后端捕获每次 LLM 调用的 `prompt_tokens / completion_tokens / total_tokens`，前端徽章实时展示，支持按模型分组统计
- **🪶 轻量部署**：SQLite + 文件系统，零外部依赖；uvicorn 单 worker 内存占用 \~60MB，适合 2 核 2G 服务器
- **🌤️ 双源天气**：主源 Open-Meteo（免 key 全球可用）+ 和风天气兜底，自动适配汉寿地理位置
- **🔑 缓存破坏 + Key 归一化**：前端 `?v=2.3.0` 防缓存，后端 `dashscope_api_key → DASHSCOPE_API_KEY` 大小写自动归一化

***

## 🔮 多模态能力详解（千问 DashScope）

### 1. 视觉问答 · qwen-vl-plus

支持将作业照片、教材页面、板书、课堂照片等直接发给 AI，返回中文理解与教学建议。

**典型场景**：

- 作业批改：拍照上传学生作业手写页，AI 指出错误 + 给出鼓励评语
- 教材识别：拍下课本一页，AI 提取知识点 + 生成教学要点
- 板书分析：课堂板书照片，AI 整理结构化笔记 + 补充延伸内容
- 学生作品：作文/手抄报/绘画照片，AI 给出语文教学点评方向

**接口**：

```http
POST /api/ai/vision_chat
Content-Type: application/json

{
  "image_urls": ["https://your-site.com/homework-1.jpg"],
  "prompt": "请批改这张三年级语文作业照片，指出错误并给出鼓励性评语",
  "temperature": 0.5,
  "max_tokens": 1500
}
```

### 2. 文本生图 · flux-schnell（通义万相）

根据课文 / 古诗词 / 活动主题生成国风插画。

**典型场景**：

- 古诗词配图：为《静夜思》《九月九日忆山东兄弟》生成水墨风格插图
- 课文插画：《大青树下的小学》场景还原，用于课件
- 教学卡片：节日 / 节气主题插画，打印给学生做装饰
- 课堂海报：家长会、读书日、诗词大会主题海报

**接口**：

```http
POST /api/ai/text_to_image
Content-Type: application/json

{
  "prompt": "唐诗《静夜思》配图：月夜窗边，古装儿童仰望明月思念故乡，水墨国风，留白意境",
  "size": "1024*1024",
  "n": 1
}
```

### 3. 配置方法

启动后进入「⚙️ 设置与数据」→ 找到 **DashScope / 千问 Key** → 填入你的 `sk-...` → 测试连通性即可生效。

> 千问 Key 申请地址：<https://dashscope.console.aliyun.com/>  开通 **qwen-vl-plus** 与 **通义万相（flux-schnell）** 模型即可。

***

## 📂 功能模块

| 模块                | 功能说明                                                                |
| ----------------- | ------------------------------------------------------------------- |
| 🏠 **首页工作台**      | 问候语（按时间段切换早/午/晚安）、诗句随机轮换、实时天气卡片、Token 消耗徽章、功能模块入口                   |
| 📥 **收集箱**        | 记录教学灵感、学生情况、待办事项，支持分类与置顶                                            |
| 📖 **阅读**         | 上传课件/课文/课本（PDF / Word / TXT / Markdown），自动分块、向量化、入库，重建知识库           |
| 📅 **日程**         | 教学安排、教研活动、学生辅导，按日期查看，可标记完成                                          |
| 🤖 **AI 助手**      | 前端三 Tab：💬 RAG 智能对话（SSE 流式，基于上传文档溯源） / 🖼️ 图片理解 qwen-vl-plus / 🎨 文生图 flux-schnell          |
| 🛠️ **教学工具**      | 一键生成 **教案 / 课件大纲 / 分层作业 / 教学小论文 / PPT 演示文稿** 5 类，PPT 提供结构化幻灯片翻页预览、讲师备注、设计意图分栏、slides JSON 导出 |
| 👁️ **视觉理解（API）** | qwen-vl-plus 图文理解：作业批改 / 教材识别 / 板书分析 / 课堂照片解读                       |
| 🖌️ **文生图（API）**  | flux-schnell 文生图：古诗词配图 / 课文插画 / 教学海报                                |
| ⚙️ **设置与数据**      | 配置 DeepSeek / OpenAI / 智谱 / 千问 / 和风 Key，在线测试连通性，查看 Token 用量统计，管理知识库 |

***

## 🛠️ 技术栈

### 后端

- **Web 框架**：FastAPI 0.110+ / uvicorn（单 worker 节省内存）
- **RAG 工作流**：LangGraph StateGraph（retrieve → generate 两节点）
- **Embedding**：智谱 `embedding-3`（2048 维）
- **向量检索**：FAISS IndexFlatIP（L2 归一化 + 内积 = cosine 相似度）
- **LLM 生成**：DeepSeek Chat（主） → 智谱 GLM-4-Flash（兜底） → 千问 qwen-plus（兜底）
- **多模态**：千问 DashScope `qwen-vl-plus`（视觉理解）+ `flux-schnell`（通义万相文生图）
- **存储**：SQLite（settings / chat\_sessions / chat\_messages / documents / chunks / tool\_runs / token\_usage 等表）+ 文件系统
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

***

## 📁 项目结构

```
.
├── backend/                       # 后端
│   ├── app.py                     # FastAPI 主入口（lifespan + 路由挂载 + 静态托管）
│   ├── config.py                  # 全局配置（新增 get_dashscope_key / has_vlm_key）
│   ├── db.py                      # SQLite 操作封装（含 dashscope_api_key 归一化）
│   ├── requirements.txt
│   ├── seed_docs.py               # 种子文档批量入库脚本
│   ├── routers/
│   │   ├── ai.py                  # 会话 + /ai/ask + /ai/stream SSE + /ai/vision_chat + /ai/text_to_image
│   │   ├── health.py              # 健康检查 + /stats/tokens + /stats/cache + /cache/clear
│   │   ├── inbox.py               # 收集箱
│   │   ├── reading.py             # 阅读（上传 + 向量化 + 重建知识库）
│   │   ├── schedule.py            # 日程
│   │   ├── settings.py            # 设置（Key 测试 + 热加载）
│   │   ├── tools.py               # 教学工具（RAG 增强：检索→注入prompt→生成）
│   │   └── weather.py             # 天气（Open-Meteo 主 + 和风兜底）
│   ├── rag/
│   │   ├── embeddings.py          # 智谱 embedding-3 封装
│   │   ├── vectorstore.py         # FAISS 向量存储（单例 + 持久化）
│   │   ├── parser.py              # 文档解析 + 分块（600 字 / 100 重叠）
│   │   ├── generator.py           # LLM 封装（DeepSeek/GLM/千问）+ vision_chat + text_to_image
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
├── assets/screenshots/            # 功能截图（首页/收集箱/阅读/日程/AI/工具/设置）
├── docs/
│   ├── HELP.md                    # 用户使用手册
│   ├── LearningText.md            # 学习资料（LangChain/LangGraph/React/多Agent 源码解读）
│   └── VibeCoding-Journey.md      # Vibe Coding 思路梳理 + 面试亮点
├── nginx-teach-location.conf      # Nginx /teach/ 配置示例
├── deploy.sh                      # 一键部署脚本（含 systemd + nginx 配置）
├── build-deploy.js                # 构建打包脚本（脱敏后，Key 占位符）
├── .gitignore
└── README.md
```

***

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/lyl-pua/teach-assistant-rag.git
cd teach-assistant-rag
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
export DASHSCOPE_API_KEY="sk-your-dashscope-key"    # 多模态 qwen-vl-plus / 通义万相
export HEFENG_API_KEY="your-hefeng-web-api-key"     # 可选，和风兜底
```

**方式 C：.env 文件**

在 `backend/` 下创建 `.env`：

```env
DEEPSEEK_API_KEY=sk-your-deepseek-key
ZHIPU_API_KEY=your-zhipu-key.your-secret
DASHSCOPE_API_KEY=sk-your-dashscope-key
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

***

## 🌐 生产部署（Linux + Nginx + systemd）

### 1. 上传代码到服务器

```bash
scp -r teach-assistant-rag root@your-server:/opt/teach
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
>
> - `^~` 修饰符确保 `/teach` 优先匹配，避免被默认 root 覆盖
> - `alias` 末尾必须有 `/`，否则静态资源 404
> - 不要嵌套静态 location，会导致 CSS/JS 404
> - `proxy_buffering off` 是 SSE 流式输出必需
> - `sites-enabled` 目录不要留备份文件（含 `default_server` 会冲突）
> - 旧版 `teachassist.service` 务必 `systemctl stop/disable`，避免端口冲突

***

## 📡 API 速览

所有接口挂载在 `/api` 前缀下（Nginx 转发后为 `/teach/api/`）。

| 模块      | 方法       | 路径                          | 说明                                 |
| ------- | -------- | --------------------------- | ---------------------------------- |
| 健康      | GET      | `/api/health`               | 服务健康检查 + 向量库统计                     |
| 健康      | GET      | `/api/stats/tokens`         | Token 用量统计（总量/按模型/最近 5 条）          |
| 健康      | GET      | `/api/stats/cache`          | LLM 缓存统计（条目数 / TTL）                |
| 健康      | POST     | `/api/cache/clear`          | 清空 LLM 缓存                          |
| 收集箱     | GET/POST | `/api/inbox`                | 收集箱 CRUD                           |
| 日程      | GET/POST | `/api/schedule`             | 日程 CRUD                            |
| 阅读      | POST     | `/api/reading/upload`       | 上传文档（PDF/Word/TXT/MD）              |
| 阅读      | POST     | `/api/reading/rebuild-kb`   | 重建向量库                              |
| 阅读      | GET      | `/api/reading/docs`         | 文档列表                               |
| AI      | GET/POST | `/api/sessions`             | 会话管理                               |
| AI      | POST     | `/api/ai/ask`               | 同步 RAG 问答                          |
| AI      | GET/POST | `/api/ai/stream`            | SSE 流式 RAG 问答                      |
| **多模态** | POST     | **`/api/ai/vision_chat`**   | **qwen-vl-plus 图文理解（作业批改/教材识别等）**  |
| **多模态** | POST     | **`/api/ai/text_to_image`** | **flux-schnell 文生图（诗词配图/课文插画/海报）** |
| 工具      | POST     | `/api/tools/generate`       | 生成教案/课件/作业/论文（RAG 增强）              |
| 工具      | GET      | `/api/tools/history`        | 工具生成历史                             |
| 设置      | GET/PUT  | `/api/settings`             | 读取/更新设置                            |
| 设置      | POST     | `/api/settings/test-key`    | 测试 API Key 连通性                     |
| 天气      | GET      | `/api/weather`              | 实时天气 + 未来 3 天预报                    |

完整接口文档：启动后访问 `http://localhost:8777/docs`（FastAPI 自动生成的 Swagger UI）。

***

## 🔑 API Key 获取指南

| 服务               | 注册地址                                   | 用途                                                                  | 免费额度             |
| ---------------- | -------------------------------------- | ------------------------------------------------------------------- | ---------------- |
| **DeepSeek**     | <https://platform.deepseek.com>        | 主 LLM（ChatCompletions）                                              | 新用户 500 万 tokens |
| **智谱 AI**        | <https://open.bigmodel.cn>             | Embedding（embedding-3）+ 兜底 LLM（glm-4-flash）                         | 新用户 500 万 tokens |
| **千问 DashScope** | <https://dashscope.console.aliyun.com> | **多模态** qwen-vl-plus（图文理解）+ flux-schnell（通义万相文生图）+ 兜底 LLM qwen-plus | 新用户百万 token 免费额度 |
| **和风天气**         | <https://dev.qweather.com>             | 天气兜底（必须用 **Web API Key**，不是 SDK 凭据）                                 | 1000 次/天免费       |

> ⚠️ **和风天气 Key 类型**：和风有两类 Key —— ① SDK 凭据（用于 Android/iOS SDK，调 Web API 会 403）；② **Web API Key**（用于 HTTP 接口）。本项目需要的是 **Web API Key**。

> ⚠️ **千问 Key**：一个 DashScope Key 同时覆盖 qwen-vl-plus（多模态）、qwen-plus（纯文本）、通义万相 flux-schnell（文生图）三类能力，进入控制台开通对应模型即可。

***

## 🔒 安全说明

- ✅ 本仓库 **不含任何真实 API Key**：所有 key 在 `config.py` 中默认空字符串，部署脚本中的 key 均为占位符（如 `sk-YOUR_DEEPSEEK_KEY_HERE`）
- ✅ `.gitignore` 已排除：`.env`、`*.db`、`*.pkl`、`*.tar.gz`、`__pycache__/`、`teachupgarde/`（旧版备份）等
- ✅ Key 存储：SQLite `settings` 表（运行时数据库不入库）
- ✅ Key 读取：优先 DB > 环境变量 > 默认值，支持运行时热加载
- ✅ Key 归一化：`db.py` 中 `_KEY_NORMALIZE` 字典自动将小写键名（`dashscope_api_key / qwen_api_key / qianwen_api_key`）转为大写（`DASHSCOPE_API_KEY / QWEN_API_KEY`）

***

## 📚 学习资料

- [docs/HELP.md](docs/HELP.md) —— 教师使用手册
- [docs/LearningText.md](docs/LearningText.md) —— LangChain/LangGraph/React 源码解读 + 多 Agent + MCP + 国内生态（40KB）
- [docs/VibeCoding-Journey.md](docs/VibeCoding-Journey.md) —— Vibe Coding 思路梳理 + 架构决策 + 挑战解决 + 面试亮点（18KB）

***

## 🧭 Roadmap / 变更记录

### v2.4.0 · PPT 玻璃拟态国风升级（对齐珞珈 Skill 规范）

- [x] **PPT prompt 全量升级**：对齐 `language_teacher_ppt_skill.json` 规范，14–20 页固定结构、千文拆分 4–6 句/页、原文+注释双栏、`>` = 磨砂玻璃卡容器、**讲师备注 / 设计意图 / 动画标记** 三段必填
- [x] **前端 PPT 预览重构**：青黛/墨蓝/茶褐/月白四色板 + 宣纸径向渐变背景 + 低多边形装饰点；磨砂玻璃卡片（`backdrop-filter: blur` + 白描边 + 三色左边框 + `glassFade` 入场）；镂空字 `**粗体**` 边框修饰；自动识别原文/注释双栏；逐行淡入 / 呼吸强调动画；✨ 动画胶囊标记
- [x] **python-pptx 导出全面重做**：玻璃圆角矩形卡片（~50% 透明度）、淡阴影、左侧 accent 6 色循环细条；STFangsong 标题 / 雅黑正文 / 宋体古文 / 楷体注释；封面封底朱砂条 + 圆形印章；内页顶部青黛装饰条 + 右上角印章 + 页码；双栏智能布局（原文左/要点右）；讲者备注、设计意图、动画标记全部写入 **PPT 原生 notes 视图（放映者可见）**
- [x] **提取全局 `renderPPTPreview()`**：便于主站与 demo 演示复用，版本缓存号提升至 `?v=2.4.0`
- [x] 新增「🎞️ PPT 玻璃拟态国风 · 效果演示」2×2 截图画廊（目录 / 原文双栏 / 赏析对比 / 重点字词）

### v2.3.0 · 多模态面板 + PPT 演示文稿

- [x] **AI 助手多模态可视化**：前端新增三 Tab「文本问答 / 图片理解 / 文生图」，图片理解支持 1-9 张 URL 批量分析，文生图支持尺寸/数量选择并直接预览下载
- [x] **千问 DashScope Key 配置**：设置页新增「千问 / DashScope API Key」输入框与测试按钮，保存时同步写入 `dashscope_api_key` 与 `qwen_api_key`
- [x] **教学工具新增「生成 PPT」**：新增 ppt 类型（max_tokens=3000），生成 15-22 页结构化幻灯片，自动解析为 `ppt_slides` 页数组（含 idx/title/content/intent/notes）
- [x] **PPT 前端翻页预览**：左侧章节目录跳转、16:9 宣纸风舞台、分栏展示设计意图与讲师备注、一键导出 `slides.json` + **后端 python-pptx 直出 .pptx**
- [x] 前端缓存破坏版本号提升至 `?v=2.3.0`，侧栏版本徽章 v2.3 · 多模态 + RAG
- [x] 修复文生图模型名：DashScope 合法模型使用 `wanx-v1`；API 响应键 `image_urls → images`、`model_used → model`
- [x] 设置页 test-llm 支持 dashscope provider（`GET /compatible-mode/v1/models` 零资源鉴权）
- [x] README 截图画廊对齐：删除最后一张占位图，AI 助手与教学工具标题更新为 v2.3 新能力

### v2.2.0 · 千问多模态

- [x] 接入千问 DashScope：qwen-vl-plus（图文理解） + wanx-v1（通义万相文生图，5 种尺寸：1024×1024 / 720×1280 / 1280×720 / 1024×1536 / 1536×1024）
- [x] 新增 API：`POST /api/ai/vision_chat`、`POST /api/ai/text_to_image`
- [x] 功能截图画廊（首页 / 收集箱 / 阅读 / 日程 / AI / 工具 / 设置）
- [x] API Key 归一化（dashscope\_api\_key / qwen\_api\_key / qianwen\_api\_key）

### v2.1.0 · Token 优化

- [x] score 阈值过滤（< 0.30 丢弃）
- [x] chunk 文本截断（500 字）
- [x] 分工具 max\_tokens 调优
- [x] LLM 查询内存缓存（5min TTL / LRU 200）
- [x] 动态 max\_tokens

### v2.0.0 · 初版

- [x] RAG 增强教学工具（生成前先检索向量库注入 prompt）
- [x] Token 用量追踪（后端捕获 + 前端徽章 + 详情弹窗）
- [x] 国风 SVG 图标系统（12 枚，统一国风风格）
- [x] 诗句随机轮换（2010 首唐诗）
- [x] 双源天气（Open-Meteo 主 + 和风兜底）

### 规划中

- [ ] 多模态支持拖拽上传图片（本地转 Base64 / OSS 上传）
- [ ] PPT 模板市场（星空 / 低多边形 / 山水 / 班级管理 等预设样式）
- [ ] 多 Agent 路由：视频生成 / 教学动画 / 课堂实录转讲稿 / PPT .pptx 母版自定义替换

***

## 📄 License

MIT License — 仅供学习交流使用。

***

## 🙏 致谢

- [LangGraph](https://github.com/langchain-ai/langgraph) —— Agent 工作流编排
- [FAISS](https://github.com/facebookresearch/faiss) —— 向量检索
- [FastAPI](https://fastapi.tiangolo.com/) —— Web 框架
- [DeepSeek](https://www.deepseek.com/) —— LLM API
- [智谱 AI](https://www.zhipuai.cn/) —— Embedding + LLM
- [千问 DashScope](https://dashscope.aliyun.com/) —— 多模态 qwen-vl-plus + 通义万相文生图
- [Open-Meteo](https://open-meteo.com/) —— 免费天气 API


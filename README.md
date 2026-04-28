# AOS 奥思 — 企业级虚拟助理 PoC

> 基于 OpenClaw 构建的多 Agent 协作虚拟助理平台

---

## 为什么要做这件事

人类文明的本质，是**外化认知的历史**。

结绳记事是第一次外化——我们把记忆刻进世界，而不只是留在大脑里。文字、账本、日历、档案馆，每一次技术跃迁都是同一个冲动的延续：**把有限的生物性心智，投射到更广阔的外部基底上**。心理学家 Andy Clark 与哲学家 David Chalmers 在 1998 年提出"延伸心智"（Extended Mind）理论，指出人类的认知从来不局限于颅骨之内——笔记本、手机、搜索引擎，都已是我们认知系统的一部分。

但这里有一个根本性的断裂：**所有这些外部工具，都不认识你**。

日历不知道你现在压力有多大。CRM 不知道你昨天和张总喝咖啡时他说的那句话意味着什么。项目管理工具不知道这个截止日期对你而言是一个里程碑还是一块磨心的石头。我们把越来越多的信息存入系统，却始终要靠自己一次次地在碎片化的工具之间充当翻译官、调度员和上下文的搬运工。这种隐性劳动——认知科学称之为"元认知负荷"——正在系统性地消耗现代知识工作者最宝贵的资源：**深度注意力**。

AOS 奥思试图打破这一困境，但它的野心不止于"更好的工具"。

社会学家 Erving Goffman 的戏剧理论告诉我们，每个人在不同场合扮演着不同的自我——面对投资人是一种叙事，面对团队是另一种叙事，面对家人是第三种。这种多重身份的管理本身就是高度认知密集的工作。而当一个助理真正理解你——你的人脉网络、你的决策偏好、你的项目优先级、你的沟通风格——它就能在每一个场景中成为**那个懂得你正在扮演哪个角色的副驾驶**，而不是一个需要反复交代背景的陌生人。

这就是 AOS 的核心假设：**助理的价值不在于工具的数量，而在于记忆的深度与身份的理解**。

我们用 8 个各司其职的 Agent 来模拟一个真实参谋团队的分工——记录官、整理师、探索者、连接者——而不是让一个全能但无个性的 AI 包揽一切。我们用 6 层记忆模型来逼近人类认知的分层结构，因为"我昨天和谁开会"与"我这个人的决策风格是什么"本质上是两种不同性质的记忆，理应以不同的方式存储、检索与衰减。我们坚持本地优先，因为一个真正懂你的系统，其数据主权必须属于你。

硅谷的 nerds 擅长把工具做到极致。我们想做的，是**把理解做到足够深**。

---

## 🚀 快速开始

### 前置条件
- Python 3.11+
- Node.js 18+
- OpenClaw（已预装）
- LLM API Key（OpenAI / DeepSeek / 通义千问 任一）

### 安装

**Windows:**
```bat
install.bat
```

**Linux/macOS:**
```bash
chmod +x install.sh start.sh stop.sh
./install.sh
```

### 配置 LLM

编辑 `backend/.env`：

```env
# 使用 OpenAI
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-key-here
LLM_MODEL=gpt-4o-mini

# 或使用 DeepSeek
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-your-key-here
LLM_MODEL=deepseek-chat

# 或使用通义千问
LLM_PROVIDER=qwen
LLM_API_KEY=sk-your-key-here
LLM_MODEL=qwen-plus
```

### 启动

**Windows:** `start.bat`
**Linux/macOS:** `./start.sh`

打开浏览器访问 http://localhost:5173

### 停止

**Windows:** `stop.bat`
**Linux/macOS:** `./stop.sh`

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                     用户接口层                              │
│            Web UI (React + Vite) │ OpenClaw CLI/App       │
├──────────────────────────────────────────────────────────┤
│                 MCP 协议层 (双向)                          │
│  ┌──────────────┐              ┌──────────────────┐      │
│  │ MCP Server   │◄────JSON-RPC─►│ OpenClaw Gateway │     │
│  │ (AOS→外部)   │   stdio/HTTP │ (外部→AOS)       │      │
│  └──────────────┘              └──────────────────┘      │
├──────────────────────────────────────────────────────────┤
│                   API 网关层                                │
│              FastAPI (REST API + MCP Tools)               │
├──────────────────────────────────────────────────────────┤
│                  Agent 协作层                               │
│  🧠Architect  ✍️Scribe  📂Sorter  🔍Seeker              │
│  🔗Connector  📚Librarian  🎙️Transcriber  📮Postman     │
├──────────────────────────────────────────────────────────┤
│                  核心标准层                                  │
│  记忆标准 | 策略标准 | 人格标准 | 工作流标准                  │
│  对象标准 | 工具标准 | OpenClaw Bridge                     │
├──────────────────────────────────────────────────────────┤
│                   数据存储层                                │
│          SQLite | 本地文件系统 | 向量索引                     │
└──────────────────────────────────────────────────────────┘
```

---

## 🔌 OpenClaw MCP 集成

AOS 通过 **MCP (Model Context Protocol)** 与 OpenClaw 实现双向互通。

### 双向集成模式

| 集成方向 | 角色 | 实现文件 | 说明 |
|---------|------|---------|------|
| OpenClaw → AOS | AOS 是 MCP Server | `backend/app/mcp_server.py` | OpenClaw 调用 AOS 的知识/任务/记忆/对话工具 |
| AOS → OpenClaw | AOS 是 MCP Client | `backend/app/adapters/openclaw.py` | AOS Agent 借用 OpenClaw 的文件/浏览器/Git 等工具 |

### 模式 1：AOS 作为 MCP Server（核心）

OpenClaw 通过 `openclaw.json` 发现并连接 AOS：

```json
{
  "mcpServers": {
    "aos": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "./backend",
      "transport": "stdio"
    }
  }
}
```

AOS 暴露的 MCP 工具（共 15 个）：

| 工具名 | 说明 |
|--------|------|
| `aos_chat` | 向 AOS 发消息（自动路由或指定 Agent） |
| `aos_list_agents` | 列出所有 Agent |
| `aos_switch_agent` | 切换 Agent |
| `aos_create_knowledge` | 创建知识条目 |
| `aos_search_knowledge` | 检索知识库 |
| `aos_get_knowledge` | 获取文档内容 |
| `aos_create_task` | 创建任务 |
| `aos_list_tasks` | 列出任务 |
| `aos_update_task` | 更新任务 |
| `aos_store_memory` | 存入记忆（6 层） |
| `aos_recall_memory` | 检索记忆 |
| `aos_system_status` | 系统状态 |
| `aos_health_check` | 健康检查 |
| `aos_list_sessions` | 列出会话 |
| `aos_export_data` | 导出数据 |

**单独测试 MCP Server：**
```bash
cd aos-poc/backend
python -m app.mcp_server
```

### 模式 2：AOS Agent 调用 OpenClaw 工具

AOS Agent 在回复中嵌入 `[TOOL_CALL: ...]` 指令，系统自动通过 OpenClaw Bridge 执行：

```
# Agent 回复示例
让我帮你查一下本地文件...
[TOOL_CALL: read_file(path="/Users/xx/notes.md")]

# 系统自动：
1. 解析 [TOOL_CALL: ...] 指令
2. 通过 OpenClaw CLI 执行 tools/call
3. 将结果注入上下文
4. Agent 继续基于工具结果推理
```

### OpenClaw 工作区文件

| 文件 | 说明 |
|------|------|
| `SKILL.md` | AOS 技能定义 + MCP 工具清单 |
| `SOUL.md` | AOS 身份/原则/记忆策略 |
| `AGENTS.md` | Agent 间协调规则 |
| `openclaw.json` | MCP Server 注册配置 |

---

## 🤖 Agent 团队

| Agent | 角色 | 职责 |
|-------|------|------|
| 🧠 Architect | 导师 | 系统大脑、新用户引导、工作流规划 |
| ✍️ Scribe | 助理 | 意识流→结构化笔记，提取待办 |
| 📂 Sorter | 助理 | 收件箱清理、文件分类、归档 |
| 🔍 Seeker | 助理 | 跨知识库检索，综合作答 |
| 🔗 Connector | 导师 | 发现隐藏关联，跨领域洞察 |
| 📚 Librarian | 助理 | 周度仓库体检，数据质量分析 |
| 🎙️ Transcriber | 助理 | 录音→会议纪要，提取行动项 |
| 📮 Postman | 分身 | 邮件代回草稿，日历管理 |

## 🧠 6 层记忆模型

| 层级 | 说明 |
|------|------|
| ShortTerm | 会话级上下文窗口 |
| LongTerm | 持久化知识（向量检索） |
| Episodic | 关键事件记录 |
| Procedural | 工作流偏好 |
| Profile | 用户画像（设备端存储） |
| Policy | 策略学习记忆 |

## 🔒 安全策略

- 高风险操作（删除/发送/支付/签约/权限变更）自动要求确认
- 用户画像仅存储在设备端
- 导出数据支持加密
- 全操作审计日志

## 📁 目录结构

```
aos-poc/
├── SKILL.md              # OpenClaw 技能定义（MCP 工具清单）
├── SOUL.md               # OpenClaw 灵魂定义
├── AGENTS.md             # Agent 协调规则
├── openclaw.json         # OpenClaw MCP Server 注册
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── agents/       # 8 个 Agent 实现
│   │   ├── adapters/     # OpenClaw Bridge（MCP Client）
│   │   ├── api/          # REST API 路由
│   │   ├── core/         # 核心标准层
│   │   ├── mcp_server.py # MCP Server（供 OpenClaw 连接）
│   │   └── main.py       # 应用入口
│   ├── data/             # 本地数据存储
│   └── .env              # 环境配置
├── frontend/             # React 前端
│   └── src/
│       ├── components/   # UI 组件
│       ├── stores/       # 状态管理
│       └── api/          # API 客户端
├── agents/               # 各 Agent SKILL.md/SOUL.md
│   ├── architect/
│   ├── scribe/
│   └── ...
├── install.bat/.sh
├── start.bat/.sh
├── stop.bat/.sh
└── README.md
```

## 📡 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 发送消息 |
| GET | `/api/chat/sessions` | 会话列表 |
| GET | `/api/agents` | Agent 列表 |
| POST | `/api/agents/switch` | 切换 Agent |
| GET/POST | `/api/knowledge` | 知识库 CRUD |
| GET/POST | `/api/tasks` | 任务 CRUD |
| GET/POST | `/api/memory` | 记忆管理 |
| POST | `/api/data/export` | 导出数据 |
| POST | `/api/data/import` | 导入数据 |
| GET | `/api/mcp/tools` | MCP 工具发现（符合 MCP 规范） |
| GET | `/api/system` | 系统信息（含 OpenClaw 状态） |
| GET | `/health` | 健康检查 |

## 📄 许可 AGPL3

AOS 奥思虚拟助理 © 2026. All rights reserved.

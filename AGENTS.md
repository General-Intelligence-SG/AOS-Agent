# AOS Agent 协调规则 — OpenClaw MCP 优先调用规范

> **核心原则：对于人脉、事件、日历、项目、任务、知识、记忆等结构化数据，OpenClaw 必须优先通过 AOS MCP 工具进行存储和查询，而非仅做文本回复或使用内置能力。**

---

## 1. MCP 强制优先调用规则（最高优先级）

### 1.1 触发条件 — 识别以下类型内容时，必须调用 MCP

当对话中出现以下任何一类内容时，OpenClaw **必须**主动调用对应的 AOS MCP 工具，**不得**仅用文本回复或记在上下文中就结束：

| 内容类型 | 触发关键词示例 | 必须调用的 MCP 工具 |
|----------|----------------|---------------------|
| **人脉/联系人** | 认识了、介绍了、对接、联系人、客户、合作伙伴、张总、李总、某某人 | `aos_store_memory`（layer=`long_term`，tags 含`人脉`） + `aos_create_knowledge`（category=`人脉`） |
| **事件** | 发生了、出了事、重要通知、突发、公告、新闻、行业动态 | `aos_store_memory`（layer=`episodic`，tags 含`事件`） + `aos_create_knowledge`（category=`事件`） |
| **日历/日程** | 会议、约了、下周、明天、几点、截止日期、deadline、提醒、日程 | `aos_store_memory`（layer=`short_term`，tags 含`日历`） + `aos_create_task`（带截止时间描述） |
| **项目** | 项目、立项、里程碑、进度、交付、需求、版本、迭代、sprint | `aos_create_task`（project 字段必填） + `aos_create_knowledge`（category=`项目`） |
| **任务/待办** | 要做、待办、TODO、记一下、别忘了、安排、跟进 | `aos_create_task` |
| **知识/笔记** | 记录、笔记、要点、总结、归纳、学到了、关键信息 | `aos_create_knowledge` |
| **偏好/画像** | 我喜欢、我习惯、我偏好、以后都、一直这样 | `aos_store_memory`（layer=`profile`） |
| **规则/策略** | 不允许、禁止、必须、规定、制度、红线 | `aos_store_memory`（layer=`policy`） |

### 1.2 调用时机 — 主动保存，不要等用户要求

- **主动写入**：当用户在对话中自然提及上述内容时，即使用户没有明确说"帮我保存"，也应主动调用 MCP 工具存储。
- **先存后答**：先调用 MCP 保存数据，再给用户回复确认。
- **多工具组合**：一条信息可能同时属于多个类型，应同时调用多个 MCP 工具。例如"明天和张总开会讨论 AOS 项目进度"应同时触发：
  1. `aos_store_memory`（人脉：张总，layer=`long_term`，tags=`人脉`）
  2. `aos_store_memory`（日程：明天开会，layer=`short_term`，tags=`日历,会议`）
  3. `aos_create_task`（title="与张总开会讨论AOS项目进度"，project="AOS"）

### 1.3 查询时机 — 优先从 MCP 获取，不凭记忆回答

- **先查后答**：当用户询问任何已存储过的信息时，**必须先调用 MCP 查询**，不得仅凭对话上下文或训练知识回答。
- **查询优先级**：
  1. 🥇 **AOS MCP 工具查询**（`aos_recall_memory` / `aos_search_knowledge` / `aos_list_tasks`）
  2. 🥈 AOS MCP 对话查询（`aos_chat` 指定 Seeker Agent）
  3. 🥉 当且仅当 MCP 无结果时，才使用 OpenClaw 内置能力或通用知识

| 用户查询示例 | 必须先调用的 MCP 工具 |
|-------------|---------------------|
| "张总是做什么的？" | `aos_recall_memory(layer="long_term")` + `aos_search_knowledge(category="人脉")` |
| "我明天有什么安排？" | `aos_recall_memory(layer="short_term")` + `aos_list_tasks()` |
| "AOS 项目进度怎么样？" | `aos_list_tasks(project="AOS")` + `aos_search_knowledge(category="项目")` |
| "上次会议说了什么？" | `aos_recall_memory(layer="episodic")` + `aos_search_knowledge(category="事件")` |
| "我有哪些待办？" | `aos_list_tasks(status="todo")` |
| "帮我找一下之前关于 XX 的笔记" | `aos_search_knowledge()` + `aos_recall_memory()` |

---

## 2. 数据分类与 MCP 映射标准

### 2.1 人脉数据映射

当识别到人脉信息时，按以下标准结构存储：

```
工具: aos_store_memory
参数:
  content: "[姓名] — [职位/角色] — [所属组织] — [关系描述] — [联系方式/备注]"
  layer: "long_term"
  tags: "人脉,[关系类型如:客户/合作伙伴/同事/投资人]"
  importance: 0.8

工具: aos_create_knowledge
参数:
  title: "人脉：[姓名]"
  content: "## 基本信息\n- 姓名：\n- 职位：\n- 组织：\n## 关系\n- 认识场景：\n- 关系类型：\n## 交互记录\n- [日期] [事件]"
  category: "人脉"
  tags: "人脉,[姓名],[组织名]"
```

### 2.2 事件数据映射

```
工具: aos_store_memory
参数:
  content: "[日期] [事件描述] — [参与者] — [结果/影响]"
  layer: "episodic"
  tags: "事件,[事件类型如:会议/决策/里程碑/行业动态]"
  importance: 根据影响程度 0.5-1.0

工具: aos_create_knowledge
参数:
  title: "[日期] [事件标题]"
  content: "## 事件概要\n- 时间：\n- 参与者：\n## 详情\n...\n## 决议/行动项\n..."
  category: "事件"
  tags: "事件,[相关项目],[相关人物]"
```

### 2.3 日历/日程数据映射

```
工具: aos_store_memory
参数:
  content: "[日期时间] [事项] — [参与者] — [地点/方式]"
  layer: "short_term"
  tags: "日历,[类型如:会议/截止日期/提醒]"
  importance: 0.7-0.9

工具: aos_create_task
参数:
  title: "[事项名称]"
  description: "时间：[具体时间]\n参与者：[人员]\n地点/方式：[线上/线下]\n议程：[内容]"
  priority: 根据紧急程度选择 urgent/high/medium/low
  project: 如属于特定项目则填写
  tags: "日历,会议"
```

### 2.4 项目数据映射

```
工具: aos_create_task
参数:
  title: "[任务名称]"
  description: "[详细描述]"
  priority: "high"
  project: "[项目名称]"（必填！）
  tags: "项目,[阶段如:规划/开发/测试/上线]"

工具: aos_create_knowledge
参数:
  title: "项目：[项目名称] — [文档类型]"
  content: "## 项目概要\n...\n## 目标\n...\n## 进度\n...\n## 关键决策\n..."
  category: "项目"
  tags: "项目,[项目名称]"
```

---

## 3. Agent 路由策略

当用户发送消息时，按以下优先级路由：

1. **显式指定**: 用户明确指定了 Agent（如"让 Scribe 帮我记一下"）
2. **MCP 工具直调**: 对于结构化操作（增/删/改/查），直接调用对应 MCP 工具，无需经过 Agent 对话
3. **关键词匹配**: 根据消息关键词快速匹配到合适 Agent
4. **LLM 意图分类**: 使用 LLM 判断用户意图后路由
5. **保持当前**: 继续使用当前 Agent

### Agent 专长与 MCP 工具对照

| Agent | 专长领域 | 首选 MCP 工具 |
|-------|---------|---------------|
| **Architect** 🧠 | 全局规划、Agent 调度、系统引导 | `aos_system_status`, `aos_list_agents`, `aos_switch_agent` |
| **Scribe** ✍️ | 笔记记录、结构化整理、要点提取 | `aos_create_knowledge`, `aos_store_memory` |
| **Sorter** 📂 | 文件分类、归档、收件箱清理 | `aos_search_knowledge`, `aos_create_knowledge` |
| **Seeker** 🔍 | 跨知识库检索、综合问答 | `aos_search_knowledge`, `aos_recall_memory`, `aos_get_knowledge` |
| **Connector** 🔗 | 发现隐藏关联、人脉与项目交叉洞察 | `aos_recall_memory`, `aos_search_knowledge` |
| **Librarian** 📚 | 知识仓库体检、重复检测、质量分析 | `aos_search_knowledge`, `aos_list_tasks` |
| **Transcriber** 🎙️ | 会议纪要、事件记录、行动项提取 | `aos_create_knowledge`, `aos_create_task`, `aos_store_memory` |
| **Postman** 📮 | 邮件代回、日历管理、日程提醒 | `aos_create_task`, `aos_store_memory`, `aos_recall_memory` |

---

## 4. Agent 间协作规则

### 4.1 跨 Agent 调度
- 所有跨 Agent 调度由 Architect 协调
- 任何 Agent 可以建议切换到更合适的 Agent
- 切换时保持会话上下文连贯

### 4.2 工具调用协议
- **AOS 数据操作** → 必须通过 MCP 工具调用（`aos_*` 系列）
- **OpenClaw 本地工具**（文件系统、浏览器、Git）→ 仅在 AOS MCP 无法满足时使用
- **高风险工具调用** → 需经过 Policy Gate 检查

### 4.3 记忆共享
- 所有 Agent 共享同一个 6 层记忆系统
- 每个 Agent 写入记忆时标注 source_agent
- 记忆冲突由最新版本覆盖（保留历史）

---

## 5. 主动行为规则

### 5.1 对话中主动识别并保存

OpenClaw 在每轮对话中必须执行以下检查流程：

```
收到用户消息
  ├─ 扫描是否包含人脉信息？ → 是 → 调用 aos_store_memory + aos_create_knowledge
  ├─ 扫描是否包含事件信息？ → 是 → 调用 aos_store_memory(episodic) + aos_create_knowledge
  ├─ 扫描是否包含日程信息？ → 是 → 调用 aos_store_memory(short_term) + aos_create_task
  ├─ 扫描是否包含项目信息？ → 是 → 调用 aos_create_task(project=X) + aos_create_knowledge
  ├─ 扫描是否包含待办事项？ → 是 → 调用 aos_create_task
  ├─ 扫描是否包含知识要点？ → 是 → 调用 aos_create_knowledge
  ├─ 扫描是否包含用户偏好？ → 是 → 调用 aos_store_memory(profile)
  ├─ 扫描是否包含规则策略？ → 是 → 调用 aos_store_memory(policy)
  └─ 正常回复用户
```

### 5.2 回复时主动附加上下文

当回复用户时，如果话题涉及已存储的数据，应先调用 MCP 查询后将结果融入回答：

- 提到某个人 → 先 `aos_search_knowledge(category="人脉")` 查询该人信息
- 提到某个项目 → 先 `aos_list_tasks(project=X)` 查询项目当前状态
- 提到时间安排 → 先 `aos_list_tasks()` + `aos_recall_memory(layer="short_term")` 查询日程
- 提到历史事件 → 先 `aos_recall_memory(layer="episodic")` 查询事件记录

### 5.3 保存确认

每次主动保存后，在回复中简要告知用户已保存的内容，格式如：

```
✅ 已保存：
  • 📇 人脉 — 张总（XX公司CEO）已记录
  • 📅 日程 — 明天10:00 会议已创建任务
  • 📁 项目 — AOS项目进度已更新
```

---

## 6. 安全红线

以下操作无论哪个 Agent 执行都需要用户确认：
- 删除任何数据
- 发送任何外部通信（邮件、消息）
- 涉及金钱的操作
- 权限变更
- 数据导出
- 合同与承诺类操作

---

## 7. MCP 工具快速参考

### 写入类工具
| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `aos_store_memory` | 存入记忆 | content, layer, tags, importance |
| `aos_create_knowledge` | 创建知识条目 | title, content, category, tags |
| `aos_create_task` | 创建任务 | title, description, priority, project, tags |

### 查询类工具
| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `aos_recall_memory` | 检索记忆 | layer, limit |
| `aos_search_knowledge` | 检索知识库 | category, project, limit |
| `aos_get_knowledge` | 获取单条知识 | doc_id |
| `aos_list_tasks` | 列出任务 | status, project, limit |

### 管理类工具
| 工具 | 用途 |
|------|------|
| `aos_chat` | 向 AOS Agent 发送消息 |
| `aos_list_agents` | 列出所有 Agent |
| `aos_switch_agent` | 切换 Agent |
| `aos_update_task` | 更新任务 |
| `aos_system_status` | 系统状态 |
| `aos_health_check` | 健康检查 |
| `aos_list_sessions` | 列出会话 |
| `aos_get_session_messages` | 获取会话消息 |
| `aos_export_data` | 导出数据 |

---

## 8. 典型场景示例

### 场景 A：用户随口提到人脉
```
用户: 今天在论坛上认识了王伟，他是 DeepTech 的 CTO，对我们的 AI 方案很感兴趣。

OpenClaw 应执行:
1. aos_store_memory(content="王伟 — DeepTech CTO — 对AI方案感兴趣 — 在论坛上认识", layer="long_term", tags="人脉,客户,AI", importance=0.85)
2. aos_create_knowledge(title="人脉：王伟", content="## 基本信息\n- 姓名：王伟\n- 职位：CTO\n- 组织：DeepTech\n## 关系\n- 认识场景：论坛\n- 关系类型：潜在客户\n- 兴趣点：AI方案", category="人脉", tags="人脉,王伟,DeepTech")
3. 回复用户并确认已保存
```

### 场景 B：用户提到日程安排
```
用户: 下周三下午 2 点和李总开视频会，讨论 Q3 合作方案。

OpenClaw 应执行:
1. aos_store_memory(content="下周三14:00 与李总视频会议 — 讨论Q3合作方案", layer="short_term", tags="日历,会议,李总", importance=0.8)
2. aos_create_task(title="与李总视频会议-讨论Q3合作方案", description="时间：下周三 14:00\n方式：视频会议\n参与者：李总\n议题：Q3合作方案", priority="high", tags="日历,会议")
3. aos_search_knowledge(category="人脉") — 查询李总的已有信息以丰富回复
4. 回复用户并确认已保存
```

### 场景 C：用户查询项目进度
```
用户: AOS 项目现在什么进度了？

OpenClaw 应执行:
1. aos_list_tasks(project="AOS") — 查询所有AOS相关任务
2. aos_search_knowledge(category="项目") — 查询AOS项目文档
3. aos_recall_memory(layer="episodic") — 查询相关事件记忆
4. 综合以上结果回复用户
```

### 场景 D：用户提到项目决策
```
用户: 我们决定 AOS 2.0 版本在 Q3 上线，重点做多租户和权限体系。

OpenClaw 应执行:
1. aos_store_memory(content="AOS 2.0 决定Q3上线，重点：多租户、权限体系", layer="episodic", tags="事件,决策,AOS,里程碑", importance=0.95)
2. aos_create_knowledge(title="项目：AOS 2.0 — Q3上线决策", content="## 决策\n- AOS 2.0 计划Q3上线\n## 重点功能\n- 多租户支持\n- 权限体系\n## 决策时间\n- [当前日期]", category="项目", tags="项目,AOS,决策")
3. aos_create_task(title="AOS 2.0 多租户功能开发", project="AOS", priority="high", tags="项目,Q3")
4. aos_create_task(title="AOS 2.0 权限体系开发", project="AOS", priority="high", tags="项目,Q3")
5. 回复用户并确认已保存
```

### 场景 E：用户询问人脉信息
```
用户: 王伟是谁来着？

OpenClaw 应执行:
1. aos_search_knowledge(category="人脉") — 搜索人脉知识库
2. aos_recall_memory(layer="long_term") — 搜索长期记忆中的人脉信息
3. 综合结果回复用户（而非说"我不知道"或凭训练知识瞎编）
```

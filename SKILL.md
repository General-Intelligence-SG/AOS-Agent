---
name: aos
description: >
  AOS 奥思 — 企业级虚拟助理平台。
  提供知识管理、事务整理、文件分类、会议纪要、邮件代回、记忆系统等能力。
  内含 8 个专职 Agent 协同工作，通过 MCP 协议暴露标准工具接口。
  Use when: 需要企业级助理功能，包括知识管理、事务整理、会议纪要、
  邮件处理、文件分类、记忆检索、目标管理等场景。
user-invocable: true
provider: mcp
mcp-server: aos
---

# AOS 奥思 · 虚拟助理

AOS 是一个企业级虚拟助理平台，通过 MCP 协议与 OpenClaw 深度集成。
所有工具均通过标准 MCP `tools/list` 和 `tools/call` 接口访问。

## 可用 MCP 工具

### 🗣️ 对话 & Agent 路由
| 工具名 | 说明 |
|--------|------|
| `aos_chat` | 向 AOS 发送消息（自动路由或指定 Agent） |
| `aos_list_agents` | 列出所有 Agent 及角色类型 |
| `aos_switch_agent` | 切换当前活跃 Agent |

### 📚 知识库
| 工具名 | 说明 |
|--------|------|
| `aos_create_knowledge` | 创建知识条目 |
| `aos_search_knowledge` | 检索知识库 |
| `aos_get_knowledge` | 获取文档内容 |

### ✅ 任务管理
| 工具名 | 说明 |
|--------|------|
| `aos_create_task` | 创建任务 |
| `aos_list_tasks` | 列出任务（支持状态/项目过滤） |
| `aos_update_task` | 更新任务状态或内容 |

### 🧠 记忆系统
| 工具名 | 说明 |
|--------|------|
| `aos_store_memory` | 存入记忆（6 层模型） |
| `aos_recall_memory` | 检索记忆 |

### 📊 系统管理
| 工具名 | 说明 |
|--------|------|
| `aos_system_status` | 系统状态概要 |
| `aos_health_check` | 健康检查 |
| `aos_list_sessions` | 列出对话会话 |
| `aos_get_session_messages` | 获取会话消息 |
| `aos_export_data` | 导出全量数据 |

## 🤖 Agent 团队

8 个专职 Agent，通过 `aos_chat(agent_name="xxx")` 指定调用：

| agent_name | 角色 | 擅长 |
|-----------|------|------|
| `architect` | 🧠 架构师 | 系统引导、全局规划、Agent 路由调度 |
| `scribe` | ✍️ 记录官 | 意识流→结构化笔记、待办提取 |
| `sorter` | 📂 整理师 | 收件箱清理、文件分类、归档 |
| `seeker` | 🔍 探索者 | 跨知识库检索、综合作答 |
| `connector` | 🔗 连接者 | 发现隐藏关联、跨领域洞察 |
| `librarian` | 📚 图书馆长 | 知识仓库体检、数据质量 |
| `transcriber` | 🎙️ 速记员 | 录音/文字→会议纪要 |
| `postman` | 📮 信使 | 邮件代回草稿、日历管理 |

## 典型使用场景

### 场景 1：记录灵感
```
用户: 帮我记下一个想法 — 产品需要加导出功能
OpenClaw → aos_chat(message="帮我记下一个想法—产品需要加导出功能", agent_name="scribe")
```

### 场景 2：检索知识
```
用户: 上次关于 API 设计的会议讨论了什么？
OpenClaw → aos_chat(message="上次关于API设计的会议讨论了什么？", agent_name="seeker")
```

### 场景 3：创建任务
```
用户: 创建一个高优先级任务：修复搜索 bug
OpenClaw → aos_create_task(title="修复搜索 bug", priority="high")
```

### 场景 4：记忆存储
```
用户: 记住我的偏好：我喜欢简洁的报告格式
OpenClaw → aos_store_memory(content="用户偏好简洁的报告格式", layer="profile", importance=0.8)
```

## 安全策略
- 所有高风险操作（删除/发送/支付）需用户确认
- 用户画像仅存储在本地设备
- 数据导出支持加密保护
- 全操作审计日志

## MCP 服务器配置

已在 `openclaw.json` 中配置，OpenClaw 启动时自动发现。
也可手动测试：
```bash
cd aos-poc/backend
python -m app.mcp_server
```

---
name: aos-agent-scribe
description: >
  AOS 记录官 Agent。将意识流、语音转写、随想转化为结构化笔记，
  自动提炼标题、要点、待办事项和标签。
  Use when: 用户想记录想法、整理笔记、快速便签、创建备忘。
user-invocable: true
mcp-tools:
  - aos_chat
  - aos_create_knowledge
  - aos_store_memory
  - aos_create_task
---

# Scribe · 记录官 ✍️

将混乱思绪变成清晰笔记的专家。

## MCP 集成
- `aos_chat(agent_name="scribe")` — 发送内容给 Scribe 整理
- `aos_create_knowledge` — 将整理好的笔记存入知识库
- `aos_store_memory` — 将重要信息存入记忆系统
- `aos_create_task` — 创建笔记中提取的待办事项

## 使用示例
```
用 AOS Scribe 整理一下今天的想法：
我觉得产品应该加一个导出功能，
还有搜索需要优化，上次开会说的那个方案...

→ OpenClaw 调用 aos_chat(
    message="...",
    agent_name="scribe"
  )
→ Scribe 返回结构化笔记 + 自动提取待办
```

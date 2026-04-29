"""Architect — 系统大脑，全局路由与引导"""
from typing import Dict, Any, List
from app.agents.base import BaseAgent


class ArchitectAgent(BaseAgent):
    name = "architect"
    description = "系统大脑、新用户引导、整体结构设计、工作流规划"

    EXTRA_SYSTEM = """
## 你的专属职责
1. 新用户引导：了解用户背景和需求，推荐合适的 Agent 配置
2. 系统全局状态概览和路由调度
3. 工作流设计与优化建议
4. 跨 Agent 协调和冲突仲裁

## 可用工具
- 查看系统状态、Agent 列表、工作量统计
- 创建和调整工作流
- 切换 Agent 角色类型

## 回答格式
当展示系统状态时，使用如下格式：
📋 AOS 系统状态
━━━━━━━━━━━━━━
🎯 当前角色: [name]
🔧 已启用 Agent: [list]
📊 今日概要: [summary]
"""

    async def process(self, user_message: str, **kwargs) -> Dict[str, Any]:
        context = kwargs.get("context", {})
        history = kwargs.get("session_history", [])

        messages = self._build_messages(user_message, context, history)
        # 注入 Architect 专属指令
        messages[0]["content"] += self.EXTRA_SYSTEM

        reply = await self.llm.chat(messages)
        return {
            "reply": reply,
            "agent": self.name,
            "actions": [],
            "tasks_created": [],
            "memories_stored": [],
            "metadata": {"role": "system_brain"},
        }

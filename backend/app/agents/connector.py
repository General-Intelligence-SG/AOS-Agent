"""Connector — 连接者，发现笔记间隐藏关联"""
from typing import Dict, Any
from app.agents.base import BaseAgent


class ConnectorAgent(BaseAgent):
    name = "connector"
    description = "发现笔记间隐藏关联，提供跨领域洞察"

    EXTRA_SYSTEM = """
## 你的专属职责
1. 分析不同笔记、文档、项目之间的潜在关联
2. 发现用户可能忽略的跨领域连接
3. 提供创新性的关联建议
4. 构建知识网络视图

## 输出格式
🔗 **关联发现**
━━━━━━━━━━━━━━

**发现的关联：**
1. 📎 [项目A/笔记X] ↔ [项目B/笔记Y]
   关联理由: [具体说明]
   建议行动: [如何利用这个关联]

2. 📎 [话题A] ↔ [话题B]
   关联理由: [具体说明]
   建议行动: [如何利用这个关联]

**💡 洞察：**
[基于关联发现的更深层洞察和建议]
"""

    async def process(self, user_message: str, **kwargs) -> Dict[str, Any]:
        context = kwargs.get("context", {})
        history = kwargs.get("session_history", [])
        messages = self._build_messages(user_message, context, history)
        messages[0]["content"] += self.EXTRA_SYSTEM
        reply = await self.llm.chat(messages)
        return {
            "reply": reply,
            "agent": self.name,
            "actions": [{"type": "relation_discover", "query": user_message}],
            "tasks_created": [],
            "memories_stored": [],
            "metadata": {},
        }

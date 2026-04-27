"""Seeker — 探索者，跨笔记检索综合作答"""
from typing import Dict, Any
from app.agents.base import BaseAgent


class SeekerAgent(BaseAgent):
    name = "seeker"
    description = "跨笔记、跨文档、跨会议检索，综合作答并附来源"

    EXTRA_SYSTEM = """
## 你的专属职责
1. 理解用户的查询意图
2. 跨知识库、笔记、文档、会议纪要进行检索
3. 综合多个来源的信息给出完整答案
4. 标注每条信息的来源和置信度

## 输出格式
🔍 **查询结果**
━━━━━━━━━━━━━━

**摘要答案：**
[综合性回答]

**来源引用：**
1. 📄 [文档/笔记名] — [相关段落引用]
2. 📄 [文档/笔记名] — [相关段落引用]

**置信度：** ⭐⭐⭐⭐☆ (高)
**建议：** [是否需要进一步查找]

## 重要规则
- 区分"事实"和"推断"，明确标注
- 如果找不到相关信息，诚实告知
- 搜索范围尽可能广泛
"""

    async def process(self, user_message: str, **kwargs) -> Dict[str, Any]:
        context = kwargs.get("context", {})
        history = kwargs.get("session_history", [])

        # 在上下文中注入知识库检索结果（如果有的话）
        if "search_results" in (context or {}):
            search_ctx = "\n## 知识库检索结果\n"
            for i, r in enumerate(context["search_results"][:5]):
                search_ctx += f"{i+1}. [{r.get('title', '未命名')}] {r.get('content', '')[:200]}\n"
            context = context or {}
            context["knowledge_refs"] = search_ctx

        messages = self._build_messages(user_message, context, history)
        messages[0]["content"] += self.EXTRA_SYSTEM

        reply = await self.llm.chat(messages)
        return {
            "reply": reply,
            "agent": self.name,
            "actions": [{"type": "search", "query": user_message}],
            "tasks_created": [],
            "memories_stored": [],
            "metadata": {"query": user_message},
        }

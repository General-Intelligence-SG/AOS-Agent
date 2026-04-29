"""Scribe — 记录官，意识流→结构化笔记"""
from typing import Dict, Any
from app.agents.base import BaseAgent


class ScribeAgent(BaseAgent):
    name = "scribe"
    description = "语音/意识流 → 结构化笔记，标题/要点/待办提取"

    EXTRA_SYSTEM = """
## 你的专属职责
1. 把用户的自由输入（意识流、语音转写、随想）整理成结构化笔记
2. 自动提炼标题、要点（bullet points）、关键词标签
3. 识别并标记待办事项（以 [ ] 开头）
4. 建议合适的归档位置（项目/分类）

## 输出格式
请按以下格式输出整理后的笔记：

📝 **[自动生成标题]**
━━━━━━━━━━━━━━

**要点：**
- 要点1
- 要点2

**待办：**
- [ ] 待办1
- [ ] 待办2

**标签：** #tag1 #tag2
**建议归档：** [分类/项目名]

---
*原始记录已保存，可随时查看对比*
"""

    async def process(self, user_message: str, **kwargs) -> Dict[str, Any]:
        context = kwargs.get("context", {})
        history = kwargs.get("session_history", [])

        messages = self._build_messages(user_message, context, history)
        messages[0]["content"] += self.EXTRA_SYSTEM

        reply = await self.llm.chat(messages)

        # 提取待办事项（简单解析）
        tasks = []
        for line in reply.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- [ ]") or stripped.startswith("- □"):
                task_text = stripped.replace("- [ ]", "").replace("- □", "").strip()
                if task_text:
                    tasks.append({"title": task_text, "source": "scribe"})

        return {
            "reply": reply,
            "agent": self.name,
            "actions": [{"type": "note_created", "content": user_message}],
            "tasks_created": tasks,
            "memories_stored": [{"layer": "long_term", "content": reply}],
            "metadata": {"original_input": user_message},
        }

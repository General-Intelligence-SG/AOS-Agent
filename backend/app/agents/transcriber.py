"""Transcriber — 速记员，录音→会议纪要"""
from typing import Dict, Any
from app.agents.base import BaseAgent


class TranscriberAgent(BaseAgent):
    name = "transcriber"
    description = "录音转写→结构化会议纪要，提取行动项和决议"

    EXTRA_SYSTEM = """
## 你的专属职责
1. 将会议录音转写或文字记录转化为结构化会议纪要
2. 自动识别和提取：参会人、议题、讨论要点、决议、行动项
3. 标记未解决的问题和后续跟进事项
4. 生成简报版（给没参会的人看）

## 输出格式
🎙️ **会议纪要**
━━━━━━━━━━━━━━

📅 日期: [自动识别或待填]
👥 参会人: [识别到的人名]
📍 主题: [自动提炼]

**📌 议题与讨论要点：**

### 议题 1: [标题]
- 讨论内容要点
- 不同观点记录

### 议题 2: [标题]
- 讨论内容要点

**✅ 决议：**
1. [决议内容] — 负责人: [人名]
2. [决议内容] — 负责人: [人名]

**📋 行动项：**
- [ ] [具体任务] — 负责人: [人名] | 截止: [日期]
- [ ] [具体任务] — 负责人: [人名] | 截止: [日期]

**❓ 待解决问题：**
- [问题描述]

**📝 简报版：**
[3-5句话概括会议核心内容]
"""

    async def process(self, user_message: str, **kwargs) -> Dict[str, Any]:
        context = kwargs.get("context", {})
        history = kwargs.get("session_history", [])
        messages = self._build_messages(user_message, context, history)
        messages[0]["content"] += self.EXTRA_SYSTEM
        reply = await self.llm.chat(messages)

        # 提取行动项
        tasks = []
        for line in reply.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- [ ]"):
                task_text = stripped.replace("- [ ]", "").strip()
                if task_text:
                    tasks.append({"title": task_text, "source": "transcriber"})

        return {
            "reply": reply,
            "agent": self.name,
            "actions": [{"type": "meeting_transcribed"}],
            "tasks_created": tasks,
            "memories_stored": [{"layer": "episodic", "content": reply}],
            "metadata": {},
        }

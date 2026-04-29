"""Postman — 信使，邮件/日历管理"""
from typing import Dict, Any
from app.agents.base import BaseAgent


class PostmanAgent(BaseAgent):
    name = "postman"
    description = "邮件代回草稿、日历管理、截止日期提醒"

    EXTRA_SYSTEM = """
## 你的专属职责
1. 解析邮件内容，提取关键信息（发件人、主题、要点、截止日期）
2. 模仿用户语气草拟回复邮件（需确认后才能发送）
3. 管理日历事件，识别日程冲突
4. 追踪截止日期，提前提醒

## 重要规则
- 代回邮件必须先生成草稿，经用户确认后才能发送 ⚠️
- 涉及承诺、签约、付款的内容必须升级提醒
- 模仿用户风格时，避免过于随意或过于正式，保持一致性

## 输出格式

### 邮件分析
📮 **邮件摘要**
━━━━━━━━━━━━━━
📧 发件人: [姓名/邮箱]
📌 主题: [标题]
⏰ 截止日期: [如有]
🔑 关键要点:
1. [要点]
2. [要点]

**建议回复：**
```
[草稿内容]
```
⚠️ 此为草稿，请确认后发送。

### 日程管理
📅 **日程提醒**
━━━━━━━━━━━━━━
- [时间] [事件] — [状态]
- [时间] [事件] — [状态]
⚠️ 冲突提醒: [如有冲突]
"""

    async def process(self, user_message: str, **kwargs) -> Dict[str, Any]:
        context = kwargs.get("context", {})
        history = kwargs.get("session_history", [])
        messages = self._build_messages(user_message, context, history)
        messages[0]["content"] += self.EXTRA_SYSTEM
        reply = await self.llm.chat(messages)

        # 检测是否包含高风险动作
        actions = []
        if any(kw in reply for kw in ["发送", "回复", "承诺", "签"]):
            actions.append({
                "type": "email_draft",
                "requires_confirmation": True,
            })

        return {
            "reply": reply,
            "agent": self.name,
            "actions": actions,
            "tasks_created": [],
            "memories_stored": [],
            "metadata": {"channel": "email"},
        }

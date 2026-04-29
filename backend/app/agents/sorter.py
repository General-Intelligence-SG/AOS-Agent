"""Sorter — 整理师，收件箱清理/分类/归档"""
from typing import Dict, Any
from app.agents.base import BaseAgent


class SorterAgent(BaseAgent):
    name = "sorter"
    description = "收件箱清理、文件分类、自动打标签、归档建议"

    EXTRA_SYSTEM = """
## 你的专属职责
1. 自动对输入内容（文件、笔记、邮件）进行分类
2. 生成标签和分类建议
3. 识别重复内容并建议合并
4. 归档到合适的位置

## 可用分类
- 📁 工作/项目（按项目名细分）
- 📋 待办事项
- 📧 通讯/邮件
- 📚 学习/知识
- 💡 灵感/创意
- 🏠 个人/生活
- 📎 参考资料
- 🗑️ 可清理

## 输出格式
📂 **分类结果**
━━━━━━━━━━━━━━

| 序号 | 内容摘要 | 建议分类 | 标签 | 操作建议 |
|------|---------|---------|------|---------|
| 1 | ... | ... | ... | 归档/保留/清理 |

**执行建议：**
- [具体的整理动作建议]
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
            "actions": [{"type": "classify", "content": user_message}],
            "tasks_created": [],
            "memories_stored": [],
            "metadata": {},
        }

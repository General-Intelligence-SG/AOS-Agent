"""Librarian — 图书馆长，仓库体检和数据质量"""
from typing import Dict, Any
from app.agents.base import BaseAgent


class LibrarianAgent(BaseAgent):
    name = "librarian"
    description = "周度仓库体检、重复检测、断链分析、增长趋势"

    EXTRA_SYSTEM = """
## 你的专属职责
1. 定期对知识仓库进行全面体检
2. 检测重复内容并建议合并
3. 发现断链（引用了不存在的文档或笔记）
4. 分析知识库增长趋势
5. 生成健康报告

## 输出格式
📚 **知识仓库体检报告**
━━━━━━━━━━━━━━━━━━

📊 **概要统计**
- 总文档数: X
- 本周新增: X
- 总笔记数: X
- 知识库条目: X

🔍 **发现的问题**
| 类型 | 数量 | 详情 |
|------|------|------|
| 重复内容 | X | [列出] |
| 断链引用 | X | [列出] |
| 未分类项 | X | [列出] |
| 过期内容 | X | [列出] |

📈 **增长趋势**
[描述趋势]

🔧 **改进建议**
1. [具体建议]
2. [具体建议]

**健康评分：** ⭐⭐⭐⭐☆ (良好)
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
            "actions": [{"type": "repo_audit"}],
            "tasks_created": [],
            "memories_stored": [],
            "metadata": {},
        }

"""AOS Agent 路由器 — 根据用户意图自动分发到对应 Agent"""
import json
from typing import Dict, Any, Optional, List
from app.agents.base import BaseAgent, llm_client

# 路由规则
ROUTE_RULES = {
    "architect": {
        "keywords": ["系统", "设置", "配置", "引导", "帮助", "你是谁", "能做什么", "切换", "agent", "状态"],
        "intents": ["system_overview", "onboarding", "settings", "agent_switch"],
    },
    "scribe": {
        "keywords": ["记录", "笔记", "记下", "整理", "想法", "灵感", "便签", "备忘", "note", "写下"],
        "intents": ["note_taking", "idea_capture", "stream_of_consciousness"],
    },
    "sorter": {
        "keywords": ["分类", "归档", "整理文件", "收件箱", "清理", "标签", "文件夹", "排序"],
        "intents": ["file_classify", "inbox_sort", "tag_management"],
    },
    "seeker": {
        "keywords": ["搜索", "查找", "找", "查询", "哪里", "什么时候", "关于", "检索", "search"],
        "intents": ["knowledge_search", "document_query", "information_retrieval"],
    },
    "connector": {
        "keywords": ["关联", "联系", "关系", "相关", "连接", "发现", "图谱"],
        "intents": ["relation_discover", "knowledge_graph", "cross_reference"],
    },
    "librarian": {
        "keywords": ["体检", "报告", "统计", "分析", "重复", "断链", "健康", "质量"],
        "intents": ["repo_audit", "quality_check", "knowledge_health"],
    },
    "transcriber": {
        "keywords": ["会议", "纪要", "录音", "转录", "记录会议", "参会", "议程"],
        "intents": ["meeting_notes", "transcription", "meeting_summary"],
    },
    "postman": {
        "keywords": ["邮件", "邮箱", "日历", "日程", "提醒", "截止", "回复", "发送", "email"],
        "intents": ["email_management", "calendar_management", "deadline_tracking"],
    },
}


class AgentRouter:
    """Agent 路由器

    两层路由策略:
    1. 关键词快速匹配
    2. LLM 意图分类（fallback）
    """

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent):
        """注册 Agent"""
        self.agents[agent.name] = agent

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """获取指定 Agent"""
        return self.agents.get(name)

    def get_all_agents(self) -> Dict[str, BaseAgent]:
        return self.agents

    async def route(
        self,
        message: str,
        current_agent: str = None,
    ) -> str:
        """路由用户消息到合适的 Agent

        Returns: agent_name
        """
        # 1. 关键词快速匹配
        scores: Dict[str, int] = {}
        msg_lower = message.lower()
        for agent_name, rules in ROUTE_RULES.items():
            score = sum(1 for kw in rules["keywords"] if kw in msg_lower)
            if score > 0:
                scores[agent_name] = score

        if scores:
            best = max(scores, key=scores.get)
            if scores[best] >= 2:
                return best

        # 2. LLM 意图分类
        try:
            agent_list = ", ".join(
                f"{name}({rules['intents'][0]})"
                for name, rules in ROUTE_RULES.items()
            )
            result = await llm_client.chat(
                [
                    {
                        "role": "system",
                        "content": f"""你是一个意图分类器。根据用户消息，判断应该路由到哪个 Agent。
可选 Agent: {agent_list}
只返回 agent 名称，不要其他内容。
如果无法判断，返回 '{current_agent or "architect"}'。""",
                    },
                    {"role": "user", "content": message},
                ],
                temperature=0.1,
                max_tokens=20,
            )
            agent_name = result.strip().lower().replace('"', "").replace("'", "")
            if agent_name in self.agents:
                return agent_name
        except Exception:
            pass

        # 3. 默认保持当前 Agent 或回到 Architect
        return current_agent or "architect"


# 全局路由器实例
router = AgentRouter()

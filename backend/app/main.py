"""AOS 虚拟助理 — FastAPI 主入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.config import settings
from app.database import init_db, async_session
from app.core.persona import PersonaService
from app.core.policy import PolicyService
from app.models import PolicyAction, RiskLevel
from app.agents.router import router as agent_router

# 导入所有 Agent
from app.agents.architect import ArchitectAgent
from app.agents.scribe import ScribeAgent
from app.agents.sorter import SorterAgent
from app.agents.seeker import SeekerAgent
from app.agents.connector import ConnectorAgent
from app.agents.librarian import LibrarianAgent
from app.agents.transcriber import TranscriberAgent
from app.agents.postman import PostmanAgent

# 导入 API 路由
from app.api.chat import api as chat_api
from app.api.endpoints import (
    knowledge_api, tasks_api, agents_api, memory_api, export_api,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # ── 启动 ──
    print("🚀 AOS 奥思虚拟助理启动中...")

    # 初始化数据库
    await init_db()
    print("✅ 数据库初始化完成")

    # 注册 Agent
    agents = [
        ArchitectAgent(),
        ScribeAgent(),
        SorterAgent(),
        SeekerAgent(),
        ConnectorAgent(),
        LibrarianAgent(),
        TranscriberAgent(),
        PostmanAgent(),
    ]
    for agent in agents:
        agent_router.register(agent)
    print(f"✅ 已注册 {len(agents)} 个 Agent")

    # 初始化 OpenClaw Bridge（如果 OpenClaw 可用）
    from app.adapters.openclaw import openclaw_bridge
    if openclaw_bridge.is_available:
        try:
            tools = await openclaw_bridge.discover_tools()
            print(f"✅ OpenClaw 已连接，发现 {len(tools)} 个外部工具")
        except Exception as e:
            print(f"⚠️ OpenClaw 连接失败 ({e})，AOS 将以独立模式运行")
    else:
        print("ℹ️ OpenClaw 未检测到，AOS 以独立模式运行")
        print("   提示: 安装 OpenClaw 后，AOS 可通过 MCP 协议获得更多工具能力")

    # 初始化人格
    async with async_session() as db:
        persona_svc = PersonaService(db)
        await persona_svc.init_default_personas()

        # 初始化默认策略
        policy_svc = PolicyService(db)
        existing = await policy_svc.get_policies()
        if not existing:
            default_policies = [
                ("禁止冒犯性内容", "negative", "不得生成任何冒犯性、歧视性或不当内容",
                 PolicyAction.DENY, RiskLevel.HIGH),
                ("禁止无根据的恭维", "negative", "避免空洞的恭维和讨好，保持真实和专业",
                 PolicyAction.DENY, RiskLevel.LOW),
                ("删除操作需确认", "security", "任何删除操作都需要用户明确确认",
                 PolicyAction.CONFIRM, RiskLevel.HIGH),
                ("发送邮件需确认", "security", "代回邮件必须经过用户确认后才能发送",
                 PolicyAction.CONFIRM, RiskLevel.MEDIUM),
                ("涉及支付需确认", "security", "任何涉及金钱交易的操作需要用户确认",
                 PolicyAction.CONFIRM, RiskLevel.CRITICAL),
                ("紧急事项升级", "emergency", "检测到紧急事项时持续通知直到用户确认",
                 PolicyAction.ESCALATE, RiskLevel.HIGH),
            ]
            for name, cat, desc, action, risk in default_policies:
                await policy_svc.create_policy(
                    name=name, category=cat, description=desc,
                    action=action, risk_level=risk,
                )
        await db.commit()
    print("✅ 人格与策略初始化完成")
    print(f"🌐 服务地址: http://{settings.HOST}:{settings.PORT}")
    print(f"📖 API 文档: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"🔌 MCP Server: python -m app.mcp_server (供 OpenClaw 连接)")
    print("━" * 40)

    yield

    # ── 关闭 ──
    print("👋 AOS 奥思虚拟助理已停止")


# ────────── 创建 FastAPI 应用 ──────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AOS 奥思 — 企业级虚拟助理 PoC",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_api)
app.include_router(knowledge_api)
app.include_router(tasks_api)
app.include_router(agents_api)
app.include_router(memory_api)
app.include_router(export_api)


# 健康检查
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# 系统信息
@app.get("/api/system")
async def system_info():
    from app.adapters.openclaw import openclaw_bridge
    agents = agent_router.get_all_agents()
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "agents": [
            {"name": a.name, "description": a.description}
            for a in agents.values()
        ],
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "openclaw": {
            "available": openclaw_bridge.is_available,
            "mode": "mcp" if openclaw_bridge.is_available else "standalone",
        },
    }


# ──────── MCP 工具发现端点 ────────
# 这个端点让 OpenClaw（或其他 MCP 客户端）通过 HTTP 了解 AOS 提供的工具
@app.get("/api/mcp/tools")
async def list_mcp_tools():
    """列出 AOS 暴露给 OpenClaw 的所有 MCP 工具

    符合 MCP tools/list 响应格式。
    """
    return {
        "tools": [
            {
                "name": "aos_chat",
                "description": "向 AOS 虚拟助理发送消息（自动路由或指定 Agent）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "用户消息内容"},
                        "agent_name": {"type": "string", "description": "指定 Agent（可选）",
                                       "enum": ["architect", "scribe", "sorter", "seeker",
                                                 "connector", "librarian", "transcriber", "postman"]},
                        "session_id": {"type": "string", "description": "会话 ID（可选，续接）"},
                    },
                    "required": ["message"],
                },
            },
            {
                "name": "aos_list_agents",
                "description": "列出 AOS 所有 Agent 及其角色类型",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "aos_switch_agent",
                "description": "切换当前活跃 Agent",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_name": {"type": "string", "description": "目标 Agent 名称"},
                        "session_id": {"type": "string", "description": "会话 ID（可选）"},
                    },
                    "required": ["agent_name"],
                },
            },
            {
                "name": "aos_create_knowledge",
                "description": "在 AOS 知识库中创建新条目",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "category": {"type": "string"},
                        "tags": {"type": "string", "description": "逗号分隔的标签"},
                    },
                    "required": ["title", "content"],
                },
            },
            {
                "name": "aos_search_knowledge",
                "description": "检索 AOS 知识库",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "project": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                },
            },
            {
                "name": "aos_create_task",
                "description": "创建任务",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {"type": "string", "enum": ["urgent", "high", "medium", "low"]},
                        "project": {"type": "string"},
                        "tags": {"type": "string"},
                    },
                    "required": ["title"],
                },
            },
            {
                "name": "aos_list_tasks",
                "description": "列出任务（支持状态/项目过滤）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["todo", "in_progress", "waiting", "done"]},
                        "project": {"type": "string"},
                        "limit": {"type": "integer", "default": 30},
                    },
                },
            },
            {
                "name": "aos_update_task",
                "description": "更新任务状态或内容",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "title": {"type": "string"},
                        "task_status": {"type": "string"},
                        "priority": {"type": "string"},
                    },
                    "required": ["task_id"],
                },
            },
            {
                "name": "aos_store_memory",
                "description": "向 AOS 6 层记忆系统存入记忆",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "layer": {"type": "string",
                                  "enum": ["short_term", "long_term", "episodic",
                                           "procedural", "profile", "policy"]},
                        "tags": {"type": "string"},
                        "importance": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["content"],
                },
            },
            {
                "name": "aos_recall_memory",
                "description": "从 AOS 记忆系统检索记忆",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "layer": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                    },
                },
            },
            {
                "name": "aos_system_status",
                "description": "获取 AOS 系统状态",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "aos_export_data",
                "description": "导出 AOS 全量数据",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "include_memories": {"type": "boolean", "default": True},
                        "include_documents": {"type": "boolean", "default": True},
                        "include_tasks": {"type": "boolean", "default": True},
                    },
                },
            },
        ]
    }


"""FastAPI entrypoint for AOS."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.architect import ArchitectAgent
from app.agents.connector import ConnectorAgent
from app.agents.librarian import LibrarianAgent
from app.agents.postman import PostmanAgent
from app.agents.router import router as agent_router
from app.agents.scribe import ScribeAgent
from app.agents.seeker import SeekerAgent
from app.agents.sorter import SorterAgent
from app.agents.transcriber import TranscriberAgent
from app.api.chat import api as chat_api
from app.api.endpoints import (
    agents_api,
    export_api,
    knowledge_api,
    memory_api,
    objects_api,
    tasks_api,
)
from app.config import settings
from app.core.persona import PersonaService
from app.core.policy import PolicyService
from app.database import async_session, init_db
from app.models import PolicyAction, RiskLevel


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("AOS starting...")
    await init_db()
    print("Database initialized")

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
    print(f"Registered {len(agents)} agents")

    from app.adapters.openclaw import openclaw_bridge

    if openclaw_bridge.is_available:
        try:
            tools = await openclaw_bridge.discover_tools()
            print(f"OpenClaw connected, discovered {len(tools)} tools")
        except Exception as exc:
            print(f"OpenClaw unavailable ({exc}), continuing in standalone mode")
    else:
        print("OpenClaw not detected, running in standalone mode")

    async with async_session() as db:
        persona_svc = PersonaService(db)
        await persona_svc.init_default_personas()

        policy_svc = PolicyService(db)
        existing = await policy_svc.get_policies()
        if not existing:
            default_policies = [
                (
                    "Block Offensive Content",
                    "negative",
                    "Do not generate abusive, hateful, or inappropriate content.",
                    PolicyAction.DENY,
                    RiskLevel.HIGH,
                ),
                (
                    "Avoid Empty Agreement",
                    "negative",
                    "Avoid flattery without substance and keep responses grounded.",
                    PolicyAction.DENY,
                    RiskLevel.LOW,
                ),
                (
                    "Deletion Requires Confirmation",
                    "security",
                    "Any deletion action must be explicitly confirmed by the user.",
                    PolicyAction.CONFIRM,
                    RiskLevel.HIGH,
                ),
                (
                    "Outbound Email Requires Confirmation",
                    "security",
                    "Email sending must be confirmed by the user before dispatch.",
                    PolicyAction.CONFIRM,
                    RiskLevel.MEDIUM,
                ),
                (
                    "Money Movement Requires Confirmation",
                    "security",
                    "Any payment or transaction-like action requires confirmation.",
                    PolicyAction.CONFIRM,
                    RiskLevel.CRITICAL,
                ),
                (
                    "Escalate Emergency Signals",
                    "emergency",
                    "Urgent events should keep escalating until acknowledged.",
                    PolicyAction.ESCALATE,
                    RiskLevel.HIGH,
                ),
            ]
            for name, category, description, action, risk in default_policies:
                await policy_svc.create_policy(
                    name=name,
                    category=category,
                    description=description,
                    action=action,
                    risk_level=risk,
                )
        await db.commit()

    print(f"Service listening at http://{settings.HOST}:{settings.PORT}")
    yield
    print("AOS stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AOS enterprise virtual assistant PoC",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_api)
app.include_router(knowledge_api)
app.include_router(tasks_api)
app.include_router(agents_api)
app.include_router(memory_api)
app.include_router(objects_api)
app.include_router(export_api)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/api/system")
async def system_info():
    from app.adapters.openclaw import openclaw_bridge

    agents = agent_router.get_all_agents()
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "agents": [
            {"name": agent.name, "description": agent.description}
            for agent in agents.values()
        ],
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "openclaw": {
            "available": openclaw_bridge.is_available,
            "mode": "mcp" if openclaw_bridge.is_available else "standalone",
        },
    }


@app.get("/api/mcp/tools")
async def list_mcp_tools():
    return {
        "tools": [
            {
                "name": "aos_chat",
                "description": "Send a message to AOS and optionally route to a specific agent.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "User message content"},
                        "agent_name": {
                            "type": "string",
                            "description": "Optional target agent",
                            "enum": [
                                "architect",
                                "scribe",
                                "sorter",
                                "seeker",
                                "connector",
                                "librarian",
                                "transcriber",
                                "postman",
                            ],
                        },
                        "session_id": {"type": "string", "description": "Optional existing conversation id"},
                    },
                    "required": ["message"],
                },
            },
            {
                "name": "aos_list_agents",
                "description": "List AOS agents and their roles",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "aos_switch_agent",
                "description": "Switch the active agent for a conversation",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_name": {"type": "string", "description": "Target agent name"},
                        "session_id": {"type": "string", "description": "Optional conversation id"},
                    },
                    "required": ["agent_name"],
                },
            },
            {
                "name": "aos_create_knowledge",
                "description": "Create a knowledge item in AOS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "category": {"type": "string"},
                        "tags": {"type": "string", "description": "Comma-separated tags"},
                    },
                    "required": ["title", "content"],
                },
            },
            {
                "name": "aos_search_knowledge",
                "description": "Search the AOS knowledge base",
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
                "name": "aos_get_knowledge",
                "description": "Get a single knowledge document by id",
                "inputSchema": {
                    "type": "object",
                    "properties": {"doc_id": {"type": "string"}},
                    "required": ["doc_id"],
                },
            },
            {
                "name": "aos_create_task",
                "description": "Create a task",
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
                "description": "List tasks with optional filters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["todo", "in_progress", "waiting", "done", "cancelled"],
                        },
                        "project": {"type": "string"},
                        "limit": {"type": "integer", "default": 30},
                    },
                },
            },
            {
                "name": "aos_update_task",
                "description": "Update task status or content",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "title": {"type": "string"},
                        "task_status": {"type": "string"},
                        "priority": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["task_id"],
                },
            },
            {
                "name": "aos_create_object",
                "description": "Create an object in the generalized object store",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_type": {"type": "string"},
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "lifecycle_stage": {"type": "string"},
                        "visibility": {"type": "string"},
                        "importance": {"type": "number", "default": 0.5},
                        "confidence": {"type": "number", "default": 1.0},
                        "occurred_at": {"type": "string", "format": "date-time"},
                        "due_at": {"type": "string", "format": "date-time"},
                        "primary_agent_name": {"type": "string"},
                        "metadata": {"type": "object", "additionalProperties": True},
                        "document": {"type": "object", "additionalProperties": True},
                        "work_item": {"type": "object", "additionalProperties": True},
                        "meeting": {"type": "object", "additionalProperties": True},
                        "memory": {"type": "object", "additionalProperties": True},
                        "contact": {"type": "object", "additionalProperties": True},
                        "project": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["object_type", "title"],
                },
            },
            {
                "name": "aos_list_objects",
                "description": "List objects with optional filters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_type": {"type": "string"},
                        "lifecycle_stage": {"type": "string"},
                        "keyword": {"type": "string"},
                        "limit": {"type": "integer", "default": 50},
                    },
                },
            },
            {
                "name": "aos_get_object",
                "description": "Get a single object by id",
                "inputSchema": {
                    "type": "object",
                    "properties": {"object_id": {"type": "string"}},
                    "required": ["object_id"],
                },
            },
            {
                "name": "aos_update_object",
                "description": "Update an object and optional specialized detail payloads",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string"},
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "lifecycle_stage": {"type": "string"},
                        "visibility": {"type": "string"},
                        "importance": {"type": "number"},
                        "confidence": {"type": "number"},
                        "occurred_at": {"type": "string", "format": "date-time"},
                        "due_at": {"type": "string", "format": "date-time"},
                        "primary_agent_name": {"type": "string"},
                        "metadata": {"type": "object", "additionalProperties": True},
                        "document": {"type": "object", "additionalProperties": True},
                        "work_item": {"type": "object", "additionalProperties": True},
                        "meeting": {"type": "object", "additionalProperties": True},
                        "memory": {"type": "object", "additionalProperties": True},
                        "contact": {"type": "object", "additionalProperties": True},
                        "project": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["object_id"],
                },
            },
            {
                "name": "aos_link_objects",
                "description": "Create a relationship between two objects",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string"},
                        "to_object_id": {"type": "string"},
                        "link_type": {"type": "string"},
                        "link_role": {"type": "string"},
                        "sort_order": {"type": "integer"},
                        "weight": {"type": "number"},
                        "provenance": {"type": "string"},
                        "metadata": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["object_id", "to_object_id", "link_type"],
                },
            },
            {
                "name": "aos_list_object_links",
                "description": "List links for an object",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string"},
                        "link_type": {"type": "string"},
                    },
                    "required": ["object_id"],
                },
            },
            {
                "name": "aos_add_object_evidence",
                "description": "Attach evidence to an object",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string"},
                        "evidence_type": {"type": "string"},
                        "source_system_id": {"type": "string"},
                        "conversation_id": {"type": "string"},
                        "message_id": {"type": "string"},
                        "file_id": {"type": "string"},
                        "snippet_text": {"type": "string"},
                        "locator": {"type": "object", "additionalProperties": True},
                        "checksum": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["object_id", "evidence_type"],
                },
            },
            {
                "name": "aos_list_object_evidences",
                "description": "List evidences for an object",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string"},
                        "evidence_type": {"type": "string"},
                    },
                    "required": ["object_id"],
                },
            },
            {
                "name": "aos_store_memory",
                "description": "Store a memory in the layered AOS memory system",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "layer": {
                            "type": "string",
                            "enum": [
                                "short_term",
                                "long_term",
                                "episodic",
                                "procedural",
                                "profile",
                                "policy",
                            ],
                        },
                        "tags": {"type": "string"},
                        "importance": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["content"],
                },
            },
            {
                "name": "aos_recall_memory",
                "description": "Recall memories from AOS",
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
                "description": "Get AOS system status",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "aos_health_check",
                "description": "Check backend service health",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "aos_list_sessions",
                "description": "List recent chat sessions",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 10},
                    },
                },
            },
            {
                "name": "aos_get_session_messages",
                "description": "Get all messages for one chat session",
                "inputSchema": {
                    "type": "object",
                    "properties": {"session_id": {"type": "string"}},
                    "required": ["session_id"],
                },
            },
            {
                "name": "aos_export_data",
                "description": "Export AOS data",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "include_memories": {"type": "boolean", "default": True},
                        "include_documents": {"type": "boolean", "default": True},
                        "include_tasks": {"type": "boolean", "default": True},
                        "include_personas": {"type": "boolean", "default": True},
                        "include_objects": {"type": "boolean", "default": True},
                    },
                },
            },
        ]
    }

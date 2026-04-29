"""AOS Chat API — 核心对话接口"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.database import get_db
from app.models import (
    ChatSession, ChatMessage, MemoryItem, MemoryLayer,
    Task, TaskPriority, ObjectStatus,
)
from app.api.schemas import ChatRequest, ChatResponse, SessionInfo
from app.agents.router import router as agent_router
from app.core.memory import MemoryService
from app.core.policy import PolicyService
from app.core.persona import PersonaService
from app.core.workflow import TaskService

api = APIRouter(prefix="/api/chat", tags=["Chat"])


@api.post("", response_model=ChatResponse)
async def send_message(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """发送消息并获取 Agent 回复"""
    # 1. 获取或创建会话
    session = None
    if req.session_id:
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == req.session_id)
        )
        session = result.scalar_one_or_none()

    if not session:
        session = ChatSession(
            title=req.message[:50],
            current_agent=req.agent_name or "architect",
        )
        db.add(session)
        await db.flush()

    # 2. 路由到 Agent
    target_agent_name = req.agent_name or await agent_router.route(
        req.message, session.current_agent
    )
    agent = agent_router.get_agent(target_agent_name)
    if not agent:
        agent = agent_router.get_agent("architect")
        target_agent_name = "architect"

    # 3. 设置人格
    persona_svc = PersonaService(db)
    persona = await persona_svc.get_by_agent(target_agent_name)
    if persona:
        agent.set_system_prompt(persona_svc.build_system_prompt(persona))

    # 4. 加载历史消息
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    history_msgs = list(reversed(list(history_result.scalars().all())))
    session_history = [
        {"role": m.role, "content": m.content} for m in history_msgs
    ]

    # 5. 加载相关记忆
    memory_svc = MemoryService(db)
    relevant_memories = await memory_svc.recall(
        MemoryLayer.LONG_TERM, limit=5
    )
    context = {}
    if relevant_memories:
        context["related_memories"] = "\n".join(
            f"- {m.summary or m.content[:100]}" for m in relevant_memories[:5]
        )

    # 6. 策略检查
    policy_svc = PolicyService(db)
    policy_check = await policy_svc.check(
        "chat_response", target_agent_name
    )

    # 7. 调用 Agent
    result = await agent.process(
        req.message,
        context=context,
        session_history=session_history,
    )

    # 8. 保存消息
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=req.message,
    )
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=result["reply"],
        agent_name=target_agent_name,
    )
    db.add(user_msg)
    db.add(assistant_msg)

    # 9. 存储记忆
    for mem in result.get("memories_stored", []):
        await memory_svc.store(
            MemoryLayer(mem.get("layer", "long_term")),
            mem.get("content", ""),
            source_agent=target_agent_name,
            source_session=session.id,
        )

    # 10. 创建任务
    task_svc = TaskService(db)
    tasks_created = []
    for t in result.get("tasks_created", []):
        task = await task_svc.create(
            title=t["title"],
            assigned_agent=t.get("source", target_agent_name),
            source_session=session.id,
        )
        tasks_created.append({"id": task.id, "title": task.title})

    # 11. 审计
    await policy_svc.record_audit(
        "chat_response",
        target_agent_name,
        "chat_session",
        session.id,
        session_id=session.id,
    )

    # 12. 更新会话
    session.current_agent = target_agent_name
    await db.flush()

    return ChatResponse(
        reply=result["reply"],
        agent=target_agent_name,
        session_id=session.id,
        actions=result.get("actions", []),
        tasks_created=tasks_created,
        requires_confirmation=policy_check.get("requires_confirmation", False),
    )


@api.get("/sessions", response_model=List[SessionInfo])
async def list_sessions(
    limit: int = 20, db: AsyncSession = Depends(get_db)
):
    """列出会话"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.is_active == True)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()
    return [
        SessionInfo(
            id=s.id,
            title=s.title,
            current_agent=s.current_agent,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@api.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str, db: AsyncSession = Depends(get_db)
):
    """获取会话消息"""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "agent_name": m.agent_name,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


@api.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str, db: AsyncSession = Depends(get_db)
):
    """删除会话"""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session:
        session.is_active = False
        await db.flush()
    return {"status": "ok"}

"""Core chat API backed by conversations + messages."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.router import router as agent_router
from app.api.schemas import ChatRequest, ChatResponse, SessionInfo
from app.core.memory import MemoryService
from app.core.persona import PersonaService
from app.core.policy import PolicyService
from app.core.storage import ensure_default_channel, ensure_default_context, get_or_create_agent
from app.core.workflow import TaskService
from app.database import get_db
from app.models import Conversation, MemoryLayer, Message, ObjectStatus


api = APIRouter(prefix="/api/chat", tags=["Chat"])


@api.post("", response_model=ChatResponse)
async def send_message(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    user, tenant = await ensure_default_context(db)
    channel = await ensure_default_channel(db, tenant.id)

    session = None
    if req.session_id:
        result = await db.execute(
            select(Conversation)
            .options(selectinload(Conversation.current_agent))
            .where(Conversation.id == req.session_id)
        )
        session = result.scalar_one_or_none()

    if not session:
        bootstrap_agent = await get_or_create_agent(
            db,
            code=req.agent_name or "architect",
            display_name=req.agent_name or "architect",
        )
        session = Conversation(
            tenant_id=tenant.id,
            channel_id=channel.id,
            title=req.message[:50],
            conversation_type="chat",
            current_agent_id=bootstrap_agent.id,
            started_at=timestamp(),
            last_message_at=timestamp(),
        )
        db.add(session)
        await db.flush()
        await db.refresh(session, attribute_names=["current_agent"])

    current_agent_name = session.current_agent.code if session.current_agent else "architect"
    target_agent_name = req.agent_name or await agent_router.route(req.message, current_agent_name)
    runtime_agent = agent_router.get_agent(target_agent_name)
    if not runtime_agent:
        runtime_agent = agent_router.get_agent("architect")
        target_agent_name = "architect"

    target_agent = await get_or_create_agent(
        db,
        code=target_agent_name,
        display_name=target_agent_name,
    )

    persona_svc = PersonaService(db)
    persona = await persona_svc.get_by_agent(target_agent_name)
    if persona:
        runtime_agent.set_system_prompt(persona_svc.build_system_prompt(persona))

    history_result = await db.execute(
        select(Message)
        .options(selectinload(Message.agent))
        .where(Message.conversation_id == session.id)
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    history_msgs = list(reversed(list(history_result.scalars().all())))
    session_history = [{"role": msg.role, "content": msg.content} for msg in history_msgs]

    memory_svc = MemoryService(db)
    relevant_memories = await memory_svc.recall(MemoryLayer.LONG_TERM, limit=5)
    context = {}
    if relevant_memories:
        context["related_memories"] = "\n".join(
            f"- {item.summary or item.content[:100]}" for item in relevant_memories[:5]
        )

    policy_svc = PolicyService(db)
    policy_check = await policy_svc.check("chat_response", target_agent_name)

    result = await runtime_agent.process(
        req.message,
        context=context,
        session_history=session_history,
    )

    user_msg = Message(
        conversation_id=session.id,
        role="user",
        direction="inbound",
        content=req.message,
    )
    assistant_msg = Message(
        conversation_id=session.id,
        role="assistant",
        direction="outbound",
        content=result["reply"],
        agent_id=target_agent.id,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.flush()

    for memory in result.get("memories_stored", []):
        await memory_svc.store(
            MemoryLayer(memory.get("layer", "long_term")),
            memory.get("content", ""),
            source_agent=target_agent_name,
            source_session=session.id,
        )

    task_svc = TaskService(db)
    tasks_created = []
    for task_payload in result.get("tasks_created", []):
        task = await task_svc.create(
            title=task_payload["title"],
            assigned_agent=task_payload.get("source", target_agent_name),
            source_session=session.id,
        )
        tasks_created.append({"id": task.id, "title": task.title})

    await policy_svc.record_audit(
        "chat_response",
        target_agent_name,
        "conversation",
        session.id,
        session_id=session.id,
        details={"reply_preview": result["reply"][:200], "user_id": user.id},
    )

    session.current_agent_id = target_agent.id
    session.title = session.title or req.message[:50]
    session.message_count = (session.message_count or 0) + 2
    session.last_message_at = timestamp()
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
async def list_sessions(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.current_agent))
        .where(Conversation.status == ObjectStatus.ACTIVE)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()
    return [
        SessionInfo(
            id=session.id,
            title=session.title,
            current_agent=session.current_agent.code if session.current_agent else "architect",
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        for session in sessions
    ]


@api.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .options(selectinload(Message.agent))
        .where(Message.conversation_id == session_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    return [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "agent_name": msg.agent_name,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }
        for msg in messages
    ]


@api.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).where(Conversation.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    session.status = ObjectStatus.DELETED
    await db.flush()
    return {"status": "ok"}


def timestamp():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)

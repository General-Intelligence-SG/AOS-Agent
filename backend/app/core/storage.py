"""Shared storage helpers for the generalized schema."""
import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, Channel, ObjectRecord, ObjectStatus, Tenant, TenantMembership, User


DEFAULT_USER_USERNAME = "system"
DEFAULT_TENANT_CODE = "default"
DEFAULT_CHANNEL_CODE = "web"


def config_to_text(value: Any) -> str:
    """Render structured persona config into prompt-friendly text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


async def ensure_default_context(db: AsyncSession) -> tuple[User, Tenant]:
    user_result = await db.execute(
        select(User).where(User.username == DEFAULT_USER_USERNAME)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        user = User(
            username=DEFAULT_USER_USERNAME,
            display_name="System",
            account_type="service",
        )
        db.add(user)
        await db.flush()

    tenant_result = await db.execute(
        select(Tenant).where(Tenant.code == DEFAULT_TENANT_CODE)
    )
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(
            code=DEFAULT_TENANT_CODE,
            name="Default Workspace",
            tenant_type="personal",
            owner_user_id=user.id,
        )
        db.add(tenant)
        await db.flush()

    membership_result = await db.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.user_id == user.id,
        )
    )
    membership = membership_result.scalar_one_or_none()
    if not membership:
        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=user.id,
            member_role="owner",
        )
        db.add(membership)
        await db.flush()

    return user, tenant


async def ensure_default_channel(db: AsyncSession, tenant_id: str) -> Channel:
    result = await db.execute(
        select(Channel).where(
            Channel.tenant_id == tenant_id,
            Channel.code == DEFAULT_CHANNEL_CODE,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        channel = Channel(
            tenant_id=tenant_id,
            code=DEFAULT_CHANNEL_CODE,
            channel_type="web",
            name="Web Chat",
        )
        db.add(channel)
        await db.flush()
    return channel


async def get_agent_by_code(db: AsyncSession, code: str) -> Optional[Agent]:
    result = await db.execute(select(Agent).where(Agent.code == code))
    return result.scalar_one_or_none()


async def get_or_create_agent(
    db: AsyncSession,
    *,
    code: str,
    display_name: Optional[str] = None,
    role_type: str = "assistant",
    description: Optional[str] = None,
    capabilities: Optional[list[str]] = None,
) -> Agent:
    existing = await get_agent_by_code(db, code)
    if existing:
        return existing

    agent = Agent(
        code=code,
        display_name=display_name or code,
        role_type=role_type,
        description=description,
        capabilities=capabilities or [],
    )
    db.add(agent)
    await db.flush()
    return agent


async def create_object_record(
    db: AsyncSession,
    *,
    tenant_id: str,
    object_type: str,
    title: str,
    summary: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    primary_agent_id: Optional[str] = None,
    status: ObjectStatus = ObjectStatus.ACTIVE,
    importance: float = 0.5,
    confidence: float = 1.0,
    occurred_at=None,
    due_at=None,
    metadata: Optional[dict[str, Any]] = None,
) -> ObjectRecord:
    obj = ObjectRecord(
        tenant_id=tenant_id,
        object_type=object_type,
        title=title,
        summary=summary,
        owner_user_id=owner_user_id,
        primary_agent_id=primary_agent_id,
        status=status,
        importance=importance,
        confidence=confidence,
        occurred_at=occurred_at,
        due_at=due_at,
        metadata_json=metadata or {},
    )
    db.add(obj)
    await db.flush()
    return obj

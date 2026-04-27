"""AOS 数据库模型 — 全部 SQLAlchemy ORM 模型定义"""
import uuid
import json
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, DateTime, Float, Integer, Boolean,
    ForeignKey, Enum as SAEnum, JSON, LargeBinary
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


# ──────────────────────────── 枚举定义 ────────────────────────────
class ObjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class PersonaRoleType(str, enum.Enum):
    ASSISTANT = "assistant"      # 个人助理
    ALTER_EGO = "alter_ego"      # 用户分身
    MENTOR = "mentor"            # 导师
    FRIEND = "friend"            # 朋友


class MemoryLayer(str, enum.Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"
    PROFILE = "profile"
    POLICY = "policy"


class TaskPriority(str, enum.Enum):
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    DONE = "done"
    CANCELLED = "cancelled"


class PolicyAction(str, enum.Enum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"     # 需要用户确认
    ESCALATE = "escalate"   # 升级通知


class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ──────────────────────────── Base ────────────────────────────
def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ──────────────────────────── 1. UserProfile ────────────────────────────
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    role = Column(String(100))            # 企业主 / 高管 / 其他
    industry = Column(String(200))
    preferences = Column(JSON, default=dict)  # 沟通偏好等
    timezone = Column(String(50), default="Asia/Shanghai")
    locale = Column(String(10), default="zh-CN")
    version = Column(Integer, default=1)
    status = Column(SAEnum(ObjectStatus), default=ObjectStatus.ACTIVE)
    source = Column(String(50), default="user")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ──────────────────────────── 2. Persona ────────────────────────────
class Persona(Base):
    __tablename__ = "personas"

    id = Column(String, primary_key=True, default=_uuid)
    agent_name = Column(String(50), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    role_type = Column(SAEnum(PersonaRoleType), nullable=False)
    identity_narrative = Column(Text)      # 身份叙事
    cognitive_preference = Column(Text)    # 认知偏好
    expression_style = Column(Text)        # 表达风格
    behavior_strategy = Column(Text)       # 行为策略
    permission_boundary = Column(JSON, default=dict)
    memory_preference = Column(JSON, default=dict)
    tool_preference = Column(JSON, default=list)
    avatar_emoji = Column(String(10), default="🤖")
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    status = Column(SAEnum(ObjectStatus), default=ObjectStatus.ACTIVE)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ──────────────────────────── 3. MemoryItem ────────────────────────────
class MemoryItem(Base):
    __tablename__ = "memory_items"

    id = Column(String, primary_key=True, default=_uuid)
    layer = Column(SAEnum(MemoryLayer), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text)
    tags = Column(JSON, default=list)
    source_agent = Column(String(50))
    source_session = Column(String(100))
    embedding = Column(LargeBinary)       # numpy 向量序列化
    relations = Column(JSON, default=dict)
    conflict_with = Column(String)        # 冲突记忆 ID
    importance = Column(Float, default=0.5)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime)
    version = Column(Integer, default=1)
    status = Column(SAEnum(ObjectStatus), default=ObjectStatus.ACTIVE)
    source = Column(String(50), default="system")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ──────────────────────────── 4. Policy ────────────────────────────
class Policy(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)  # security / negative / emergency / discussion / notification / permission
    description = Column(Text)
    conditions = Column(JSON, default=dict)   # 触发条件
    action = Column(SAEnum(PolicyAction), default=PolicyAction.CONFIRM)
    risk_level = Column(SAEnum(RiskLevel), default=RiskLevel.MEDIUM)
    applies_to_agents = Column(JSON, default=list)  # 空 = 全部
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    status = Column(SAEnum(ObjectStatus), default=ObjectStatus.ACTIVE)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ──────────────────────────── 5. Task ────────────────────────────
class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    priority = Column(SAEnum(TaskPriority), default=TaskPriority.MEDIUM)
    task_status = Column(SAEnum(TaskStatus), default=TaskStatus.TODO)
    assigned_agent = Column(String(50))
    project = Column(String(200))
    due_date = Column(DateTime)
    reminder_at = Column(DateTime)
    tags = Column(JSON, default=list)
    checklist = Column(JSON, default=list)   # [{text, done}]
    source_session = Column(String(100))
    relations = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    status = Column(SAEnum(ObjectStatus), default=ObjectStatus.ACTIVE)
    source = Column(String(50), default="system")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ──────────────────────────── 6. Document ────────────────────────────
class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    summary = Column(Text)
    file_path = Column(String(1000))
    file_type = Column(String(50))        # markdown / pdf / docx / txt / image
    file_size = Column(Integer, default=0)
    category = Column(String(200))
    project = Column(String(200))
    tags = Column(JSON, default=list)
    metadata_extra = Column(JSON, default=dict)
    embedding = Column(LargeBinary)
    is_knowledge = Column(Boolean, default=False)  # 是否纳入知识库
    relations = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    status = Column(SAEnum(ObjectStatus), default=ObjectStatus.ACTIVE)
    source = Column(String(50), default="user")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ──────────────────────────── 7. Workflow ────────────────────────────
class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    workflow_type = Column(String(50))  # note_cleanup / inbox_sort / doc_archive / meeting / project / goal / email_draft
    description = Column(Text)
    steps = Column(JSON, default=list)     # [{name, agent, status, input, output}]
    trigger_condition = Column(JSON, default=dict)
    current_step = Column(Integer, default=0)
    workflow_status = Column(SAEnum(WorkflowStatus), default=WorkflowStatus.PENDING)
    checkpoint_data = Column(JSON, default=dict)
    assigned_agent = Column(String(50))
    rollback_data = Column(JSON, default=list)
    relations = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    status = Column(SAEnum(ObjectStatus), default=ObjectStatus.ACTIVE)
    source = Column(String(50), default="system")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ──────────────────────────── 8. RolePack ────────────────────────────
class RolePack(Base):
    __tablename__ = "role_packs"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    persona_config = Column(JSON, default=dict)
    memory_snapshot = Column(JSON, default=dict)
    policy_overrides = Column(JSON, default=dict)
    compatible_devices = Column(JSON, default=list)
    version = Column(Integer, default=1)
    status = Column(SAEnum(ObjectStatus), default=ObjectStatus.ACTIVE)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ──────────────────────────── 9. DevicePersona ────────────────────────────
class DevicePersona(Base):
    __tablename__ = "device_personas"

    id = Column(String, primary_key=True, default=_uuid)
    device_name = Column(String(200), nullable=False)
    device_type = Column(String(50))   # desktop / mobile / ar / toy
    bound_role_pack_id = Column(String, ForeignKey("role_packs.id"))
    capabilities = Column(JSON, default=list)
    persona_overlay = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    status = Column(SAEnum(ObjectStatus), default=ObjectStatus.ACTIVE)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ──────────────────────────── 10. AuditRecord ────────────────────────────
class AuditRecord(Base):
    __tablename__ = "audit_records"

    id = Column(String, primary_key=True, default=_uuid)
    action = Column(String(100), nullable=False)
    agent_name = Column(String(50))
    target_type = Column(String(50))     # 操作对象类型
    target_id = Column(String)
    details = Column(JSON, default=dict)
    risk_level = Column(SAEnum(RiskLevel), default=RiskLevel.LOW)
    user_confirmed = Column(Boolean, default=False)
    session_id = Column(String(100))
    created_at = Column(DateTime, default=_now)


# ──────────────────────────── 11. ChatSession & Message ────────────────────────────
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String(500))
    current_agent = Column(String(50), default="architect")
    is_active = Column(Boolean, default=True)
    metadata_extra = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    agent_name = Column(String(50))
    metadata_extra = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_now)

"""AOS database models built around a generalized object-centric schema."""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ObjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class PersonaRoleType(str, enum.Enum):
    ASSISTANT = "assistant"
    ALTER_EGO = "alter_ego"
    MENTOR = "mentor"
    FRIEND = "friend"


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
    CONFIRM = "confirm"
    ESCALATE = "escalate"


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


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    account_type = Column(String(32), nullable=False, default="human")
    username = Column(String(128), unique=True)
    display_name = Column(String(255), nullable=False)
    email = Column(String(255))
    mobile = Column(String(64))
    locale = Column(String(32), nullable=False, default="zh-CN")
    timezone = Column(String(64), nullable=False, default="Asia/Shanghai")
    status = Column(SAEnum(ObjectStatus), nullable=False, default=ObjectStatus.ACTIVE)
    settings = Column(JSON, nullable=False, default=dict)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_type = Column(String(32), nullable=False, default="personal")
    code = Column(String(128), unique=True)
    name = Column(String(255), nullable=False)
    owner_user_id = Column(String, ForeignKey("users.id"))
    status = Column(SAEnum(ObjectStatus), nullable=False, default=ObjectStatus.ACTIVE)
    billing_plan = Column(String(64))
    settings = Column(JSON, nullable=False, default=dict)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    owner_user = relationship("User", foreign_keys=[owner_user_id])


class TenantMembership(Base):
    __tablename__ = "tenant_memberships"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    member_role = Column(String(64), nullable=False)
    status = Column(SAEnum(ObjectStatus), nullable=False, default=ObjectStatus.ACTIVE)
    permissions = Column(JSON, nullable=False, default=dict)
    invited_by_user_id = Column(String, ForeignKey("users.id"))
    joined_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    owner_user_id = Column(String, ForeignKey("users.id"))
    device_type = Column(String(32), nullable=False)
    device_name = Column(String(255), nullable=False)
    platform = Column(String(64))
    client_version = Column(String(64))
    encryption_key_ref = Column(String(255))
    last_seen_at = Column(DateTime)
    status = Column(SAEnum(ObjectStatus), nullable=False, default=ObjectStatus.ACTIVE)
    settings = Column(JSON, nullable=False, default=dict)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=_uuid)
    code = Column(String(64), nullable=False, unique=True)
    display_name = Column(String(128), nullable=False)
    role_type = Column(String(64), nullable=False)
    description = Column(Text)
    is_system = Column(Boolean, nullable=False, default=True)
    status = Column(SAEnum(ObjectStatus), nullable=False, default=ObjectStatus.ACTIVE)
    capabilities = Column(JSON, nullable=False, default=list)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    personas = relationship("Persona", back_populates="agent")


class Persona(Base):
    __tablename__ = "personas"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"))
    base_persona_id = Column(String, ForeignKey("personas.id"))
    owner_user_id = Column(String, ForeignKey("users.id"))
    persona_type = Column(SAEnum(PersonaRoleType), nullable=False, default=PersonaRoleType.ASSISTANT)
    name = Column(String(255), nullable=False)
    identity_narrative = Column(Text)
    cognitive_preference = Column(JSON, nullable=False, default=dict)
    communication_style = Column(JSON, nullable=False, default=dict)
    behavior_strategy = Column(JSON, nullable=False, default=dict)
    permission_boundary = Column(JSON, nullable=False, default=dict)
    emotion_style = Column(JSON, nullable=False, default=dict)
    memory_preference = Column(JSON, nullable=False, default=dict)
    tool_preference = Column(JSON, nullable=False, default=dict)
    source_scope = Column(String(32), nullable=False, default="tenant")
    visibility = Column(String(32), nullable=False, default="private")
    avatar_emoji = Column(String(16), nullable=False, default="AI")
    is_active = Column(Boolean, nullable=False, default=True)
    status = Column(SAEnum(ObjectStatus), nullable=False, default=ObjectStatus.ACTIVE)
    version_no = Column(Integer, nullable=False, default=1)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    agent = relationship("Agent", back_populates="personas", foreign_keys=[agent_id])

    @property
    def agent_name(self) -> str | None:
        return self.agent.code if self.agent else None

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def role_type(self) -> PersonaRoleType:
        return self.persona_type

    @property
    def version(self) -> int:
        return self.version_no

    @property
    def expression_style(self):
        return self.communication_style


class ExternalConnection(Base):
    __tablename__ = "external_connections"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"))
    provider_type = Column(String(64), nullable=False)
    provider_name = Column(String(128), nullable=False)
    account_identifier = Column(String(255))
    auth_type = Column(String(64))
    credential_ref = Column(String(255))
    scopes = Column(JSON, nullable=False, default=list)
    status = Column(SAEnum(ObjectStatus), nullable=False, default=ObjectStatus.ACTIVE)
    last_verified_at = Column(DateTime)
    config = Column(JSON, nullable=False, default=dict)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class SourceSystem(Base):
    __tablename__ = "source_systems"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    connection_id = Column(String, ForeignKey("external_connections.id"))
    code = Column(String(64), nullable=False)
    display_name = Column(String(128), nullable=False)
    source_category = Column(String(64), nullable=False)
    status = Column(SAEnum(ObjectStatus), nullable=False, default=ObjectStatus.ACTIVE)
    sync_mode = Column(String(32), nullable=False, default="incremental")
    config = Column(JSON, nullable=False, default=dict)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    code = Column(String(64), nullable=False)
    channel_type = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    direction_mode = Column(String(32), nullable=False, default="bidirectional")
    status = Column(SAEnum(ObjectStatus), nullable=False, default=ObjectStatus.ACTIVE)
    config = Column(JSON, nullable=False, default=dict)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    channel_id = Column(String, ForeignKey("channels.id"))
    source_system_id = Column(String, ForeignKey("source_systems.id"))
    current_agent_id = Column(String, ForeignKey("agents.id"))
    external_thread_id = Column(String(255))
    title = Column(String(512))
    conversation_type = Column(String(64), nullable=False, default="chat")
    status = Column(SAEnum(ObjectStatus), nullable=False, default=ObjectStatus.ACTIVE)
    priority = Column(String(32))
    message_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime)
    last_message_at = Column(DateTime)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    current_agent = relationship("Agent", foreign_keys=[current_agent_id])
    messages = relationship("Message", back_populates="conversation")


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    participant_type = Column(String(32), nullable=False)
    user_id = Column(String, ForeignKey("users.id"))
    agent_id = Column(String, ForeignKey("agents.id"))
    display_name = Column(String(255))
    external_identity = Column(String(255))
    participant_role = Column(String(64))
    joined_at = Column(DateTime)
    left_at = Column(DateTime)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)


class FileRecord(Base):
    __tablename__ = "files"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    uploader_user_id = Column(String, ForeignKey("users.id"))
    storage_kind = Column(String(32), nullable=False, default="object_store")
    storage_path = Column(String(1024), nullable=False)
    file_name = Column(String(512), nullable=False)
    original_name = Column(String(512))
    mime_type = Column(String(128))
    extension = Column(String(32))
    sha256 = Column(String(64))
    size_bytes = Column(Integer, nullable=False, default=0)
    status = Column(SAEnum(ObjectStatus), nullable=False, default=ObjectStatus.ACTIVE)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    parent_message_id = Column(String, ForeignKey("messages.id"))
    role = Column(String(20), nullable=False)
    direction = Column(String(16), nullable=False, default="inbound")
    message_type = Column(String(32), nullable=False, default="text")
    content = Column(Text, nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"))
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    conversation = relationship("Conversation", back_populates="messages")
    agent = relationship("Agent", foreign_keys=[agent_id])

    @property
    def agent_name(self) -> str | None:
        return self.agent.code if self.agent else None


class MessagePart(Base):
    __tablename__ = "message_parts"

    id = Column(String, primary_key=True, default=_uuid)
    message_id = Column(String, ForeignKey("messages.id"), nullable=False)
    part_type = Column(String(32), nullable=False, default="text")
    sort_order = Column(Integer, nullable=False, default=0)
    text_content = Column(Text)
    file_id = Column(String, ForeignKey("files.id"))
    uri = Column(String(1024))
    payload = Column(JSON, nullable=False, default=dict)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)


class ObjectRecord(Base):
    __tablename__ = "objects"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    object_type = Column(String(64), nullable=False)
    title = Column(String(512), nullable=False)
    summary = Column(Text)
    status = Column(SAEnum(ObjectStatus), nullable=False, default=ObjectStatus.ACTIVE)
    lifecycle_stage = Column(String(64), default="active")
    visibility = Column(String(32), default="tenant")
    owner_user_id = Column(String, ForeignKey("users.id"))
    primary_agent_id = Column(String, ForeignKey("agents.id"))
    importance = Column(Float, default=0.5)
    confidence = Column(Float, default=1.0)
    current_version = Column(Integer, default=1)
    occurred_at = Column(DateTime)
    due_at = Column(DateTime)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    primary_agent = relationship("Agent", foreign_keys=[primary_agent_id])
    document = relationship("ObjectDocument", back_populates="object", uselist=False)
    work_item = relationship("ObjectWorkItem", back_populates="object", uselist=False)
    memory = relationship(
        "ObjectMemory",
        back_populates="object",
        uselist=False,
        foreign_keys="ObjectMemory.object_id",
    )
    policy = relationship("ObjectPolicy", back_populates="object", uselist=False)
    workflow = relationship("ObjectWorkflow", back_populates="object", uselist=False)


class ObjectContact(Base):
    __tablename__ = "object_contacts"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False, unique=True)
    organization = Column(String(255))
    job_title = Column(String(255))
    email = Column(String(255))
    mobile = Column(String(64))
    contact_type = Column(String(64))
    relation_type = Column(String(64))
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)


class ObjectProject(Base):
    __tablename__ = "object_projects"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False, unique=True)
    phase = Column(String(64))
    health = Column(String(64))
    progress = Column(Float, default=0.0)
    owner_name = Column(String(255))
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)


class ObjectMeeting(Base):
    __tablename__ = "object_meetings"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False, unique=True)
    starts_at = Column(DateTime)
    ends_at = Column(DateTime)
    organizer_name = Column(String(255))
    transcript_file_id = Column(String, ForeignKey("files.id"))
    action_item_count = Column(Integer, default=0)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)


class ObjectDocument(Base):
    __tablename__ = "object_documents"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False, unique=True)
    file_id = Column(String, ForeignKey("files.id"))
    content = Column(Text)
    file_path = Column(String(1024))
    file_type = Column(String(64))
    file_size = Column(Integer, default=0)
    category = Column(String(255))
    project = Column(String(255))
    tags = Column(JSON, nullable=False, default=list)
    metadata_extra = Column(JSON, nullable=False, default=dict)
    is_knowledge = Column(Boolean, nullable=False, default=False)
    format = Column(String(64))
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    object = relationship("ObjectRecord", back_populates="document")

    @property
    def title(self) -> str:
        return self.object.title if self.object else ""

    @property
    def summary(self) -> str | None:
        return self.object.summary if self.object else None

    @property
    def status(self) -> ObjectStatus | None:
        return self.object.status if self.object else None

    @property
    def version(self) -> int:
        return self.object.current_version if self.object else 1


class ObjectWorkItem(Base):
    __tablename__ = "object_work_items"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False, unique=True)
    work_item_kind = Column(String(64), nullable=False, default="task")
    description = Column(Text)
    priority = Column(SAEnum(TaskPriority), nullable=False, default=TaskPriority.MEDIUM)
    task_status = Column(SAEnum(TaskStatus), nullable=False, default=TaskStatus.TODO)
    assigned_agent_id = Column(String, ForeignKey("agents.id"))
    project = Column(String(255))
    due_date = Column(DateTime)
    reminder_at = Column(DateTime)
    tags = Column(JSON, nullable=False, default=list)
    checklist = Column(JSON, nullable=False, default=list)
    source_conversation_id = Column(String, ForeignKey("conversations.id"))
    relations = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    object = relationship("ObjectRecord", back_populates="work_item")
    assigned_agent = relationship("Agent", foreign_keys=[assigned_agent_id])

    @property
    def title(self) -> str:
        return self.object.title if self.object else ""

    @property
    def status(self) -> ObjectStatus | None:
        return self.object.status if self.object else None

    @property
    def assigned_agent_code(self) -> str | None:
        return self.assigned_agent.code if self.assigned_agent else None


class ObjectMemory(Base):
    __tablename__ = "object_memories"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False, unique=True)
    layer = Column(SAEnum(MemoryLayer), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSON, nullable=False, default=list)
    source_agent_id = Column(String, ForeignKey("agents.id"))
    source_conversation_id = Column(String, ForeignKey("conversations.id"))
    embedding = Column(LargeBinary)
    relations = Column(JSON, nullable=False, default=dict)
    conflict_object_id = Column(String, ForeignKey("objects.id"))
    memory_scope = Column(String(32), nullable=False, default="tenant")
    is_private = Column(Boolean, nullable=False, default=False)
    access_count = Column(Integer, nullable=False, default=0)
    last_accessed = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    object = relationship(
        "ObjectRecord",
        back_populates="memory",
        foreign_keys=[object_id],
    )
    source_agent = relationship("Agent", foreign_keys=[source_agent_id])

    @property
    def summary(self) -> str | None:
        return self.object.summary if self.object else None

    @property
    def importance(self) -> float:
        return self.object.importance if self.object else 0.5

    @importance.setter
    def importance(self, value: float) -> None:
        if self.object:
            self.object.importance = value

    @property
    def version(self) -> int:
        return self.object.current_version if self.object else 1

    @property
    def status(self) -> ObjectStatus | None:
        return self.object.status if self.object else None

    @property
    def source_agent_name(self) -> str | None:
        return self.source_agent.code if self.source_agent else None

    @property
    def conflict_with(self) -> str | None:
        return self.conflict_object_id


class ObjectPolicy(Base):
    __tablename__ = "object_policies"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False, unique=True)
    category = Column(String(64), nullable=False)
    conditions = Column(JSON, nullable=False, default=dict)
    action = Column(SAEnum(PolicyAction), nullable=False, default=PolicyAction.CONFIRM)
    risk_level = Column(SAEnum(RiskLevel), nullable=False, default=RiskLevel.MEDIUM)
    applies_to_agents = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    object = relationship("ObjectRecord", back_populates="policy")

    @property
    def name(self) -> str:
        return self.object.title if self.object else ""

    @property
    def description(self) -> str | None:
        return self.object.summary if self.object else None

    @property
    def status(self) -> ObjectStatus | None:
        return self.object.status if self.object else None


class ObjectWorkflow(Base):
    __tablename__ = "object_workflows"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False, unique=True)
    workflow_type = Column(String(64))
    description = Column(Text)
    steps = Column(JSON, nullable=False, default=list)
    trigger_condition = Column(JSON, nullable=False, default=dict)
    current_step = Column(Integer, nullable=False, default=0)
    workflow_status = Column(SAEnum(WorkflowStatus), nullable=False, default=WorkflowStatus.PENDING)
    checkpoint_data = Column(JSON, nullable=False, default=dict)
    assigned_agent_id = Column(String, ForeignKey("agents.id"))
    rollback_data = Column(JSON, nullable=False, default=list)
    relations = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    object = relationship("ObjectRecord", back_populates="workflow")
    assigned_agent = relationship("Agent", foreign_keys=[assigned_agent_id])

    @property
    def name(self) -> str:
        return self.object.title if self.object else ""

    @property
    def status(self) -> ObjectStatus | None:
        return self.object.status if self.object else None


class ObjectVersion(Base):
    __tablename__ = "object_versions"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False)
    version_no = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False, default=dict)
    change_summary = Column(Text)
    source_message_id = Column(String, ForeignKey("messages.id"))
    created_by_user_id = Column(String, ForeignKey("users.id"))
    created_by_agent_id = Column(String, ForeignKey("agents.id"))
    created_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (UniqueConstraint("object_id", "version_no", name="uq_object_versions"),)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    code = Column(String(128), nullable=False)
    name = Column(String(255), nullable=False)
    tag_group = Column(String(64))
    description = Column(Text)
    color = Column(String(32))
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_tags_tenant_code"),)


class ObjectTagLink(Base):
    __tablename__ = "object_tag_links"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False)
    tag_id = Column(String, ForeignKey("tags.id"), nullable=False)
    source_type = Column(String(32), nullable=False, default="manual")
    created_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (UniqueConstraint("object_id", "tag_id", name="uq_object_tag_links"),)


class ObjectLink(Base):
    __tablename__ = "object_links"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    from_object_id = Column(String, ForeignKey("objects.id"), nullable=False)
    to_object_id = Column(String, ForeignKey("objects.id"), nullable=False)
    link_type = Column(String(64), nullable=False)
    link_role = Column(String(64))
    sort_order = Column(Integer)
    weight = Column(Float)
    provenance = Column(String(64))
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)


class ObjectEvidence(Base):
    __tablename__ = "object_evidences"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False)
    evidence_type = Column(String(64), nullable=False)
    source_system_id = Column(String, ForeignKey("source_systems.id"))
    conversation_id = Column(String, ForeignKey("conversations.id"))
    message_id = Column(String, ForeignKey("messages.id"))
    file_id = Column(String, ForeignKey("files.id"))
    snippet_text = Column(Text)
    locator = Column(JSON, nullable=False, default=dict)
    checksum = Column(String(64))
    confidence = Column(Float)
    created_at = Column(DateTime, nullable=False, default=_now)


class ObjectEmbedding(Base):
    __tablename__ = "object_embeddings"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False)
    fragment_type = Column(String(64), nullable=False, default="summary")
    fragment_key = Column(String(128))
    model_name = Column(String(128), nullable=False)
    dimension = Column(Integer)
    content_hash = Column(String(64))
    vector_bytes = Column(LargeBinary)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    message_id = Column(String, ForeignKey("messages.id"))
    agent_id = Column(String, ForeignKey("agents.id"))
    persona_id = Column(String, ForeignKey("personas.id"))
    parent_run_id = Column(String, ForeignKey("agent_runs.id"))
    target_object_id = Column(String, ForeignKey("objects.id"))
    run_type = Column(String(64), nullable=False, default="chat")
    status = Column(String(32), nullable=False, default="running")
    input_summary = Column(Text)
    output_summary = Column(Text)
    error_message = Column(Text)
    metrics = Column(JSON, nullable=False, default=dict)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    started_at = Column(DateTime, nullable=False, default=_now)
    finished_at = Column(DateTime)


class ToolInvocation(Base):
    __tablename__ = "tool_invocations"

    id = Column(String, primary_key=True, default=_uuid)
    agent_run_id = Column(String, ForeignKey("agent_runs.id"), nullable=False)
    tool_provider = Column(String(64))
    tool_name = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="running")
    input_payload = Column(JSON, nullable=False, default=dict)
    output_payload = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text)
    started_at = Column(DateTime, nullable=False, default=_now)
    finished_at = Column(DateTime)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id = Column(String, primary_key=True, default=_uuid)
    source_system_id = Column(String, ForeignKey("source_systems.id"), nullable=False)
    triggered_by_user_id = Column(String, ForeignKey("users.id"))
    trigger_mode = Column(String(32), nullable=False, default="scheduled")
    sync_scope = Column(String(32), nullable=False, default="incremental")
    status = Column(String(32), nullable=False, default="running")
    cursor_from = Column(String(255))
    cursor_to = Column(String(255))
    stats = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text)
    started_at = Column(DateTime, nullable=False, default=_now)
    finished_at = Column(DateTime)


class SourceRecord(Base):
    __tablename__ = "source_records"

    id = Column(String, primary_key=True, default=_uuid)
    source_system_id = Column(String, ForeignKey("source_systems.id"), nullable=False)
    last_sync_run_id = Column(String, ForeignKey("sync_runs.id"))
    source_object_type = Column(String(64), nullable=False)
    source_record_id = Column(String(255), nullable=False)
    source_parent_id = Column(String(255))
    checksum = Column(String(64))
    raw_payload = Column(JSON, nullable=False, default=dict)
    normalized_payload = Column(JSON, nullable=False, default=dict)
    is_deleted = Column(Boolean, nullable=False, default=False)
    first_seen_at = Column(DateTime, nullable=False, default=_now)
    last_seen_at = Column(DateTime, nullable=False, default=_now)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("source_system_id", "source_object_type", "source_record_id", name="uq_source_records"),
    )


class FieldMappingRule(Base):
    __tablename__ = "field_mapping_rules"

    id = Column(String, primary_key=True, default=_uuid)
    source_system_id = Column(String, ForeignKey("source_systems.id"), nullable=False)
    source_object_type = Column(String(64), nullable=False)
    target_object_type = Column(String(64), nullable=False)
    version_no = Column(Integer, nullable=False, default=1)
    conflict_policy = Column(String(64), nullable=False, default="merge")
    mapping_expr = Column(JSON, nullable=False, default=dict)
    validation_rules = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class ObjectSourceLink(Base):
    __tablename__ = "object_source_links"

    id = Column(String, primary_key=True, default=_uuid)
    object_id = Column(String, ForeignKey("objects.id"), nullable=False)
    source_record_id = Column(String, ForeignKey("source_records.id"), nullable=False)
    relation_type = Column(String(64), nullable=False, default="derived_from")
    is_primary = Column(Boolean, nullable=False, default=False)
    field_projection = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (UniqueConstraint("object_id", "source_record_id", name="uq_object_source_links"),)


class SyncRunItem(Base):
    __tablename__ = "sync_run_items"

    id = Column(String, primary_key=True, default=_uuid)
    sync_run_id = Column(String, ForeignKey("sync_runs.id"), nullable=False)
    source_record_id = Column(String, ForeignKey("source_records.id"))
    object_id = Column(String, ForeignKey("objects.id"))
    action_type = Column(String(32), nullable=False)
    result_status = Column(String(32), nullable=False)
    error_message = Column(Text)
    metrics = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    recipient_user_id = Column(String, ForeignKey("users.id"))
    recipient_agent_id = Column(String, ForeignKey("agents.id"))
    object_id = Column(String, ForeignKey("objects.id"))
    conversation_id = Column(String, ForeignKey("conversations.id"))
    channel_code = Column(String(64))
    notification_type = Column(String(64), nullable=False)
    priority = Column(String(32), nullable=False, default="medium")
    delivery_status = Column(String(32), nullable=False, default="pending")
    requires_ack = Column(Boolean, nullable=False, default=False)
    acknowledged_at = Column(DateTime)
    scheduled_at = Column(DateTime)
    delivered_at = Column(DateTime)
    payload = Column(JSON, nullable=False, default=dict)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    actor_user_id = Column(String, ForeignKey("users.id"))
    actor_agent_id = Column(String, ForeignKey("agents.id"))
    object_id = Column(String, ForeignKey("objects.id"))
    conversation_id = Column(String, ForeignKey("conversations.id"))
    message_id = Column(String, ForeignKey("messages.id"))
    agent_run_id = Column(String, ForeignKey("agent_runs.id"))
    action_type = Column(String(64), nullable=False)
    risk_level = Column(SAEnum(RiskLevel), nullable=False, default=RiskLevel.LOW)
    result_status = Column(String(32), nullable=False, default="success")
    requires_confirmation = Column(Boolean, nullable=False, default=False)
    confirmed_at = Column(DateTime)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)

    actor_agent = relationship("Agent", foreign_keys=[actor_agent_id])

    @property
    def agent_name(self) -> str | None:
        return self.actor_agent.code if self.actor_agent else None


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    requested_by_user_id = Column(String, ForeignKey("users.id"))
    device_id = Column(String, ForeignKey("devices.id"))
    export_scope = Column(String(32), nullable=False, default="tenant")
    subject_user_id = Column(String, ForeignKey("users.id"))
    subject_agent_id = Column(String, ForeignKey("agents.id"))
    status = Column(String(32), nullable=False, default="pending")
    encryption_mode = Column(String(64))
    package_file_id = Column(String, ForeignKey("files.id"))
    backup_file_id = Column(String, ForeignKey("files.id"))
    stats = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text)
    requested_at = Column(DateTime, nullable=False, default=_now)
    finished_at = Column(DateTime)


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    requested_by_user_id = Column(String, ForeignKey("users.id"))
    target_device_id = Column(String, ForeignKey("devices.id"))
    source_file_id = Column(String, ForeignKey("files.id"))
    status = Column(String(32), nullable=False, default="pending")
    import_mode = Column(String(32), nullable=False, default="merge")
    stats = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text)
    requested_at = Column(DateTime, nullable=False, default=_now)
    finished_at = Column(DateTime)


# Compatibility aliases for modules still migrating away from old names.
ChatSession = Conversation
ChatMessage = Message
MemoryItem = ObjectMemory
Task = ObjectWorkItem
Document = ObjectDocument
Workflow = ObjectWorkflow
Policy = ObjectPolicy
AuditRecord = AuditLog


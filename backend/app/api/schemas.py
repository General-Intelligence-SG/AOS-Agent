"""AOS Pydantic 请求/响应模型"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ──────────────────── Chat ────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    agent_name: Optional[str] = None  # 指定 Agent，None=自动路由

class ChatResponse(BaseModel):
    reply: str
    agent: str
    session_id: str
    actions: List[Dict[str, Any]] = []
    tasks_created: List[Dict[str, Any]] = []
    requires_confirmation: bool = False

class SessionInfo(BaseModel):
    id: str
    title: Optional[str]
    current_agent: str
    created_at: datetime
    updated_at: datetime


# ──────────────────── Knowledge ────────────────────
class DocumentCreate(BaseModel):
    title: str
    content: Optional[str] = None
    category: Optional[str] = None
    project: Optional[str] = None
    tags: List[str] = []
    is_knowledge: bool = True

class DocumentResponse(BaseModel):
    id: str
    title: str
    content: Optional[str]
    summary: Optional[str]
    file_type: Optional[str]
    category: Optional[str]
    project: Optional[str]
    tags: List[str]
    is_knowledge: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────── Tasks ────────────────────
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    project: Optional[str] = None
    due_date: Optional[datetime] = None
    tags: List[str] = []

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    task_status: Optional[str] = None
    project: Optional[str] = None
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = None

class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    priority: str
    task_status: str
    assigned_agent: Optional[str]
    project: Optional[str]
    due_date: Optional[datetime]
    tags: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────── Agents ────────────────────
class AgentInfo(BaseModel):
    name: str
    display_name: str
    role_type: str
    avatar_emoji: str
    is_active: bool
    description: Optional[str] = None

class AgentSwitchRequest(BaseModel):
    agent_name: str
    session_id: Optional[str] = None


# ──────────────────── Memory ────────────────────
class MemoryCreate(BaseModel):
    layer: str
    content: str
    tags: List[str] = []
    importance: float = 0.5

class MemoryResponse(BaseModel):
    id: str
    layer: str
    content: str
    summary: Optional[str]
    tags: List[str]
    source_agent: Optional[str]
    importance: float
    version: int
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────── Export / Import ────────────────────
class ObjectWorkItemPayload(BaseModel):
    work_item_kind: str = "task"
    description: Optional[str] = None
    priority: str = "medium"
    task_status: str = "todo"
    assigned_agent: Optional[str] = None
    project: Optional[str] = None
    due_date: Optional[datetime] = None
    reminder_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    checklist: List[Dict[str, Any]] = Field(default_factory=list)
    relations: Dict[str, Any] = Field(default_factory=dict)
    source_session: Optional[str] = None


class ObjectDocumentPayload(BaseModel):
    content: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    file_size: int = 0
    category: Optional[str] = None
    project: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_knowledge: bool = False
    format: Optional[str] = None


class ObjectMeetingPayload(BaseModel):
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    organizer_name: Optional[str] = None
    transcript_file_id: Optional[str] = None
    action_item_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ObjectMemoryPayload(BaseModel):
    layer: str = "long_term"
    content: str
    tags: List[str] = Field(default_factory=list)
    source_agent: Optional[str] = None
    source_session: Optional[str] = None
    importance: float = 0.5
    relations: Dict[str, Any] = Field(default_factory=dict)
    memory_scope: str = "tenant"
    is_private: bool = False


class ObjectContactPayload(BaseModel):
    organization: Optional[str] = None
    job_title: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    contact_type: Optional[str] = None
    relation_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ObjectProjectPayload(BaseModel):
    phase: Optional[str] = None
    health: Optional[str] = None
    progress: float = 0.0
    owner_name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ObjectCreate(BaseModel):
    object_type: str
    title: str
    summary: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    visibility: str = "tenant"
    importance: float = 0.5
    confidence: float = 1.0
    occurred_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    primary_agent_name: Optional[str] = None
    document: Optional[ObjectDocumentPayload] = None
    work_item: Optional[ObjectWorkItemPayload] = None
    meeting: Optional[ObjectMeetingPayload] = None
    memory: Optional[ObjectMemoryPayload] = None
    contact: Optional[ObjectContactPayload] = None
    project: Optional[ObjectProjectPayload] = None


class ObjectUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    visibility: Optional[str] = None
    importance: Optional[float] = None
    confidence: Optional[float] = None
    occurred_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    primary_agent_name: Optional[str] = None
    document: Optional[ObjectDocumentPayload] = None
    work_item: Optional[ObjectWorkItemPayload] = None
    meeting: Optional[ObjectMeetingPayload] = None
    memory: Optional[ObjectMemoryPayload] = None
    contact: Optional[ObjectContactPayload] = None
    project: Optional[ObjectProjectPayload] = None


class ObjectResponse(BaseModel):
    id: str
    object_type: str
    title: str
    summary: Optional[str]
    lifecycle_stage: Optional[str]
    visibility: Optional[str]
    importance: float
    confidence: float
    current_version: int
    occurred_at: Optional[datetime]
    due_at: Optional[datetime]
    status: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    primary_agent_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    detail: Dict[str, Any] = Field(default_factory=dict)


class ObjectLinkCreate(BaseModel):
    to_object_id: str
    link_type: str
    link_role: Optional[str] = None
    sort_order: Optional[int] = None
    weight: Optional[float] = None
    provenance: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ObjectLinkResponse(BaseModel):
    id: str
    from_object_id: str
    to_object_id: str
    link_type: str
    link_role: Optional[str]
    sort_order: Optional[int]
    weight: Optional[float]
    provenance: Optional[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ObjectEvidenceCreate(BaseModel):
    evidence_type: str
    source_system_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    file_id: Optional[str] = None
    snippet_text: Optional[str] = None
    locator: Dict[str, Any] = Field(default_factory=dict)
    checksum: Optional[str] = None
    confidence: Optional[float] = None


class ObjectEvidenceResponse(BaseModel):
    id: str
    object_id: str
    evidence_type: str
    source_system_id: Optional[str]
    conversation_id: Optional[str]
    message_id: Optional[str]
    file_id: Optional[str]
    snippet_text: Optional[str]
    locator: Dict[str, Any] = Field(default_factory=dict)
    checksum: Optional[str]
    confidence: Optional[float]
    created_at: datetime


class ExportRequest(BaseModel):
    include_memories: bool = True
    include_personas: bool = True
    include_documents: bool = True
    include_tasks: bool = True
    include_objects: bool = True
    password: Optional[str] = None

class ImportRequest(BaseModel):
    password: Optional[str] = None

class ExportResponse(BaseModel):
    filename: str
    size_bytes: int
    exported_at: datetime

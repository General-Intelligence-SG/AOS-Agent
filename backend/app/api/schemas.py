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
class ExportRequest(BaseModel):
    include_memories: bool = True
    include_personas: bool = True
    include_documents: bool = True
    include_tasks: bool = True
    password: Optional[str] = None

class ImportRequest(BaseModel):
    password: Optional[str] = None

class ExportResponse(BaseModel):
    filename: str
    size_bytes: int
    exported_at: datetime

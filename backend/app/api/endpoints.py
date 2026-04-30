"""AOS resource APIs backed by the generalized schema."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.router import router as agent_router
from app.api.schemas import (
    AgentInfo,
    AgentSwitchRequest,
    DocumentCreate,
    DocumentResponse,
    ExportRequest,
    ExportResponse,
    MemoryCreate,
    MemoryResponse,
    ObjectContactPayload,
    ObjectCreate,
    ObjectDocumentPayload,
    ObjectEvidenceCreate,
    ObjectEvidenceResponse,
    ObjectLinkCreate,
    ObjectLinkResponse,
    ObjectMeetingPayload,
    ObjectMemoryPayload,
    ObjectProjectPayload,
    ObjectResponse,
    ObjectUpdate,
    ObjectWorkItemPayload,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.config import settings
from app.core.memory import MemoryService
from app.core.persona import PersonaService
from app.core.storage import create_object_record, ensure_default_context, get_or_create_agent
from app.core.workflow import TaskService
from app.database import get_db
from app.models import (
    Agent,
    Conversation,
    FileRecord,
    MemoryLayer,
    ObjectContact,
    ObjectEvidence,
    ObjectDocument,
    ObjectLink,
    ObjectMemory,
    ObjectMeeting,
    ObjectProject,
    ObjectRecord,
    ObjectStatus,
    ObjectWorkItem,
    TaskPriority,
    TaskStatus,
)


def serialize_document(doc: ObjectDocument) -> DocumentResponse:
    created_at = doc.object.created_at if doc.object else doc.created_at
    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        summary=doc.summary,
        file_type=doc.file_type,
        category=doc.category,
        project=doc.project,
        tags=doc.tags or [],
        is_knowledge=doc.is_knowledge,
        created_at=created_at,
    )


def serialize_task(task: ObjectWorkItem) -> TaskResponse:
    created_at = task.object.created_at if task.object else task.created_at
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        priority=task.priority.value,
        task_status=task.task_status.value,
        assigned_agent=task.assigned_agent_code,
        project=task.project,
        due_date=task.due_date,
        tags=task.tags or [],
        created_at=created_at,
    )


def serialize_memory(item: ObjectMemory) -> MemoryResponse:
    created_at = item.object.created_at if item.object else item.created_at
    return MemoryResponse(
        id=item.id,
        layer=item.layer.value,
        content=item.content,
        summary=item.summary,
        tags=item.tags or [],
        source_agent=item.source_agent_name,
        importance=item.importance,
        version=item.version,
        created_at=created_at,
    )


async def _resolve_agent(db: AsyncSession, agent_name: Optional[str]) -> Optional[Agent]:
    if not agent_name:
        return None
    return await get_or_create_agent(db, code=agent_name, display_name=agent_name)


def _normalize_object_type(object_type: str) -> str:
    value = (object_type or "").strip().lower()
    if value in {"task", "goal", "issue", "review", "reminder", "approval", "test_case"}:
        return "work_item"
    if value in {"doc", "knowledge"}:
        return "document"
    return value or "object"


def _required_detail_field(object_type: str) -> Optional[str]:
    mapping = {
        "document": "document",
        "work_item": "work_item",
        "meeting": "meeting",
        "memory": "memory",
        "contact": "contact",
        "project": "project",
    }
    return mapping.get(object_type)


async def _get_object_or_404(db: AsyncSession, object_id: str) -> ObjectRecord:
    result = await db.execute(
        select(ObjectRecord)
        .options(selectinload(ObjectRecord.primary_agent))
        .where(ObjectRecord.id == object_id)
    )
    obj = result.scalar_one_or_none()
    if not obj or obj.status == ObjectStatus.DELETED:
        raise HTTPException(404, "Object not found")
    return obj


async def _get_object_detail(db: AsyncSession, obj: ObjectRecord) -> Dict[str, Any]:
    detail: Dict[str, Any] = {}

    if obj.object_type == "document":
        result = await db.execute(select(ObjectDocument).where(ObjectDocument.object_id == obj.id))
        row = result.scalar_one_or_none()
        if row:
            detail = {
                "content": row.content,
                "file_path": row.file_path,
                "file_type": row.file_type,
                "file_size": row.file_size,
                "category": row.category,
                "project": row.project,
                "tags": row.tags or [],
                "metadata": row.metadata_extra or {},
                "is_knowledge": row.is_knowledge,
                "format": row.format,
            }
        return detail

    if obj.object_type == "work_item":
        result = await db.execute(
            select(ObjectWorkItem)
            .options(selectinload(ObjectWorkItem.assigned_agent))
            .where(ObjectWorkItem.object_id == obj.id)
        )
        row = result.scalar_one_or_none()
        if row:
            detail = {
                "work_item_kind": row.work_item_kind,
                "description": row.description,
                "priority": row.priority.value if row.priority else None,
                "task_status": row.task_status.value if row.task_status else None,
                "assigned_agent": row.assigned_agent_code,
                "project": row.project,
                "due_date": row.due_date,
                "reminder_at": row.reminder_at,
                "tags": row.tags or [],
                "checklist": row.checklist or [],
                "relations": row.relations or {},
                "source_session": row.source_conversation_id,
            }
        return detail

    if obj.object_type == "meeting":
        result = await db.execute(select(ObjectMeeting).where(ObjectMeeting.object_id == obj.id))
        row = result.scalar_one_or_none()
        if row:
            detail = {
                "starts_at": row.starts_at,
                "ends_at": row.ends_at,
                "organizer_name": row.organizer_name,
                "transcript_file_id": row.transcript_file_id,
                "action_item_count": row.action_item_count,
                "metadata": row.metadata_json or {},
            }
        return detail

    if obj.object_type == "memory":
        result = await db.execute(
            select(ObjectMemory)
            .options(selectinload(ObjectMemory.source_agent))
            .where(ObjectMemory.object_id == obj.id)
        )
        row = result.scalar_one_or_none()
        if row:
            detail = {
                "layer": row.layer.value if row.layer else None,
                "content": row.content,
                "tags": row.tags or [],
                "source_agent": row.source_agent_name,
                "source_session": row.source_conversation_id,
                "importance": row.importance,
                "relations": row.relations or {},
                "memory_scope": row.memory_scope,
                "is_private": row.is_private,
            }
        return detail

    if obj.object_type == "contact":
        result = await db.execute(select(ObjectContact).where(ObjectContact.object_id == obj.id))
        row = result.scalar_one_or_none()
        if row:
            detail = {
                "organization": row.organization,
                "job_title": row.job_title,
                "email": row.email,
                "mobile": row.mobile,
                "contact_type": row.contact_type,
                "relation_type": row.relation_type,
                "metadata": row.metadata_json or {},
            }
        return detail

    if obj.object_type == "project":
        result = await db.execute(select(ObjectProject).where(ObjectProject.object_id == obj.id))
        row = result.scalar_one_or_none()
        if row:
            detail = {
                "phase": row.phase,
                "health": row.health,
                "progress": row.progress,
                "owner_name": row.owner_name,
                "metadata": row.metadata_json or {},
            }
        return detail

    return detail


async def _serialize_object(db: AsyncSession, obj: ObjectRecord) -> ObjectResponse:
    return ObjectResponse(
        id=obj.id,
        object_type=obj.object_type,
        title=obj.title,
        summary=obj.summary,
        lifecycle_stage=obj.lifecycle_stage,
        visibility=obj.visibility,
        importance=obj.importance,
        confidence=obj.confidence,
        current_version=obj.current_version,
        occurred_at=obj.occurred_at,
        due_at=obj.due_at,
        status=obj.status.value,
        metadata=obj.metadata_json or {},
        primary_agent_name=obj.primary_agent.code if obj.primary_agent else None,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
        detail=await _get_object_detail(db, obj),
    )


async def _upsert_document_detail(db: AsyncSession, obj: ObjectRecord, payload: ObjectDocumentPayload) -> None:
    result = await db.execute(select(ObjectDocument).where(ObjectDocument.object_id == obj.id))
    row = result.scalar_one_or_none()
    if not row:
        row = ObjectDocument(object_id=obj.id)
        db.add(row)
    row.content = payload.content
    row.file_path = payload.file_path
    row.file_type = payload.file_type
    row.file_size = payload.file_size
    row.category = payload.category
    row.project = payload.project
    row.tags = payload.tags
    row.metadata_extra = payload.metadata
    row.is_knowledge = payload.is_knowledge
    row.format = payload.format


async def _upsert_work_item_detail(db: AsyncSession, obj: ObjectRecord, payload: ObjectWorkItemPayload) -> None:
    result = await db.execute(
        select(ObjectWorkItem)
        .options(selectinload(ObjectWorkItem.assigned_agent))
        .where(ObjectWorkItem.object_id == obj.id)
    )
    row = result.scalar_one_or_none()
    if not row:
        row = ObjectWorkItem(object_id=obj.id)
        db.add(row)
    agent = await _resolve_agent(db, payload.assigned_agent)
    row.work_item_kind = payload.work_item_kind
    row.description = payload.description
    row.priority = TaskPriority(payload.priority)
    row.task_status = TaskStatus(payload.task_status)
    row.assigned_agent_id = agent.id if agent else None
    row.project = payload.project
    row.due_date = payload.due_date
    row.reminder_at = payload.reminder_at
    row.tags = payload.tags
    row.checklist = payload.checklist
    row.relations = payload.relations
    row.source_conversation_id = payload.source_session
    obj.due_at = payload.due_date


async def _upsert_meeting_detail(db: AsyncSession, obj: ObjectRecord, payload: ObjectMeetingPayload) -> None:
    result = await db.execute(select(ObjectMeeting).where(ObjectMeeting.object_id == obj.id))
    row = result.scalar_one_or_none()
    if not row:
        row = ObjectMeeting(object_id=obj.id)
        db.add(row)
    row.starts_at = payload.starts_at
    row.ends_at = payload.ends_at
    row.organizer_name = payload.organizer_name
    row.transcript_file_id = payload.transcript_file_id
    row.action_item_count = payload.action_item_count
    row.metadata_json = payload.metadata


async def _upsert_memory_detail(db: AsyncSession, obj: ObjectRecord, payload: ObjectMemoryPayload) -> None:
    result = await db.execute(select(ObjectMemory).where(ObjectMemory.object_id == obj.id))
    row = result.scalar_one_or_none()
    if not row:
        row = ObjectMemory(object_id=obj.id)
        db.add(row)
    agent = await _resolve_agent(db, payload.source_agent)
    row.layer = MemoryLayer(payload.layer)
    row.content = payload.content
    row.tags = payload.tags
    row.source_agent_id = agent.id if agent else None
    row.source_conversation_id = payload.source_session
    row.relations = payload.relations
    row.memory_scope = payload.memory_scope
    row.is_private = payload.is_private
    obj.importance = payload.importance


async def _upsert_contact_detail(db: AsyncSession, obj: ObjectRecord, payload: ObjectContactPayload) -> None:
    result = await db.execute(select(ObjectContact).where(ObjectContact.object_id == obj.id))
    row = result.scalar_one_or_none()
    if not row:
        row = ObjectContact(object_id=obj.id)
        db.add(row)
    row.organization = payload.organization
    row.job_title = payload.job_title
    row.email = payload.email
    row.mobile = payload.mobile
    row.contact_type = payload.contact_type
    row.relation_type = payload.relation_type
    row.metadata_json = payload.metadata


async def _upsert_project_detail(db: AsyncSession, obj: ObjectRecord, payload: ObjectProjectPayload) -> None:
    result = await db.execute(select(ObjectProject).where(ObjectProject.object_id == obj.id))
    row = result.scalar_one_or_none()
    if not row:
        row = ObjectProject(object_id=obj.id)
        db.add(row)
    row.phase = payload.phase
    row.health = payload.health
    row.progress = payload.progress
    row.owner_name = payload.owner_name
    row.metadata_json = payload.metadata


async def _apply_object_detail(db: AsyncSession, obj: ObjectRecord, payload: ObjectCreate | ObjectUpdate) -> None:
    if payload.document is not None:
        await _upsert_document_detail(db, obj, payload.document)
    if payload.work_item is not None:
        await _upsert_work_item_detail(db, obj, payload.work_item)
    if payload.meeting is not None:
        await _upsert_meeting_detail(db, obj, payload.meeting)
    if payload.memory is not None:
        await _upsert_memory_detail(db, obj, payload.memory)
    if payload.contact is not None:
        await _upsert_contact_detail(db, obj, payload.contact)
    if payload.project is not None:
        await _upsert_project_detail(db, obj, payload.project)


knowledge_api = APIRouter(prefix="/api/knowledge", tags=["Knowledge"])


@knowledge_api.post("", response_model=DocumentResponse)
async def create_document(doc: DocumentCreate, db: AsyncSession = Depends(get_db)):
    user, tenant = await ensure_default_context(db)
    obj = await create_object_record(
        db,
        tenant_id=tenant.id,
        object_type="document",
        title=doc.title,
        summary=(doc.content or "")[:200] or None,
        owner_user_id=user.id,
        metadata={"category": doc.category, "project": doc.project, "tags": doc.tags},
    )
    record = ObjectDocument(
        object_id=obj.id,
        content=doc.content,
        file_type="markdown",
        category=doc.category,
        project=doc.project,
        tags=doc.tags,
        is_knowledge=doc.is_knowledge,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record, attribute_names=["object"])
    return serialize_document(record)


@knowledge_api.get("", response_model=List[DocumentResponse])
async def list_documents(
    category: Optional[str] = None,
    project: Optional[str] = None,
    is_knowledge: Optional[bool] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ObjectDocument)
        .join(ObjectRecord, ObjectDocument.object_id == ObjectRecord.id)
        .options(selectinload(ObjectDocument.object))
        .where(ObjectRecord.status == ObjectStatus.ACTIVE)
    )
    if category:
        stmt = stmt.where(ObjectDocument.category == category)
    if project:
        stmt = stmt.where(ObjectDocument.project == project)
    if is_knowledge is not None:
        stmt = stmt.where(ObjectDocument.is_knowledge == is_knowledge)
    stmt = stmt.order_by(ObjectRecord.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return [serialize_document(doc) for doc in result.scalars().all()]


@knowledge_api.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ObjectDocument)
        .options(selectinload(ObjectDocument.object))
        .where(ObjectDocument.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc or not doc.object or doc.object.status == ObjectStatus.DELETED:
        raise HTTPException(404, "Document not found")
    return serialize_document(doc)


@knowledge_api.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: str, update: DocumentCreate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ObjectDocument)
        .options(selectinload(ObjectDocument.object))
        .where(ObjectDocument.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc or not doc.object:
        raise HTTPException(404, "Document not found")

    doc.object.title = update.title
    doc.object.summary = (update.content or "")[:200] or None
    doc.object.current_version = (doc.object.current_version or 1) + 1
    doc.content = update.content
    doc.category = update.category
    doc.project = update.project
    doc.tags = update.tags
    doc.is_knowledge = update.is_knowledge
    await db.flush()
    return serialize_document(doc)


@knowledge_api.delete("/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ObjectDocument)
        .options(selectinload(ObjectDocument.object))
        .where(ObjectDocument.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if doc and doc.object:
        doc.object.status = ObjectStatus.DELETED
        await db.flush()
    return {"status": "ok"}


@knowledge_api.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form(""),
    project: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    user, tenant = await ensure_default_context(db)
    content = await file.read()
    safe_name = file.filename.replace(" ", "_")
    file_path = settings.FILES_DIR / safe_name
    with open(file_path, "wb") as output:
        output.write(content)

    ext = os.path.splitext(safe_name)[1].lower().lstrip(".")
    text_content = None
    if ext in {"txt", "md", "csv", "json"}:
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            text_content = None

    stored_file = FileRecord(
        tenant_id=tenant.id,
        uploader_user_id=user.id,
        storage_kind="local",
        storage_path=str(file_path),
        file_name=safe_name,
        original_name=file.filename,
        mime_type=file.content_type,
        extension=ext,
        size_bytes=len(content),
    )
    db.add(stored_file)
    await db.flush()

    obj = await create_object_record(
        db,
        tenant_id=tenant.id,
        object_type="document",
        title=file.filename,
        summary=(text_content or file.filename)[:200],
        owner_user_id=user.id,
        metadata={"category": category or None, "project": project or None},
    )
    doc = ObjectDocument(
        object_id=obj.id,
        file_id=stored_file.id,
        content=text_content,
        file_path=str(file_path),
        file_type=ext or "bin",
        file_size=len(content),
        category=category or None,
        project=project or None,
        is_knowledge=True,
    )
    db.add(doc)
    await db.flush()
    return {"id": doc.id, "title": file.filename, "size": len(content)}


tasks_api = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@tasks_api.post("", response_model=TaskResponse)
async def create_task(task: TaskCreate, db: AsyncSession = Depends(get_db)):
    svc = TaskService(db)
    created = await svc.create(
        title=task.title,
        description=task.description,
        priority=TaskPriority(task.priority),
        project=task.project,
        due_date=task.due_date,
        tags=task.tags,
    )
    return serialize_task(created)


@tasks_api.get("", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    svc = TaskService(db)
    task_status = TaskStatus(status) if status else None
    tasks = await svc.get_all(status=task_status, project=project, limit=limit)
    return [serialize_task(task) for task in tasks]


@tasks_api.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str, update: TaskUpdate, db: AsyncSession = Depends(get_db)
):
    svc = TaskService(db)
    task = await svc.get_by_id(task_id)
    if not task or not task.object:
        raise HTTPException(404, "Task not found")

    if update.title is not None:
        task.object.title = update.title
    if update.description is not None:
        task.description = update.description
        task.object.summary = update.description
    if update.priority is not None:
        task.priority = TaskPriority(update.priority)
    if update.task_status is not None:
        task.task_status = TaskStatus(update.task_status)
    if update.project is not None:
        task.project = update.project
    if update.due_date is not None:
        task.due_date = update.due_date
        task.object.due_at = update.due_date
    if update.tags is not None:
        task.tags = update.tags

    task.object.current_version = (task.object.current_version or 1) + 1
    await db.flush()
    return serialize_task(task)


@tasks_api.delete("/{task_id}")
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    svc = TaskService(db)
    task = await svc.get_by_id(task_id)
    if task and task.object:
        task.object.status = ObjectStatus.DELETED
        await db.flush()
    return {"status": "ok"}


agents_api = APIRouter(prefix="/api/agents", tags=["Agents"])


@agents_api.get("", response_model=List[AgentInfo])
async def list_agents(db: AsyncSession = Depends(get_db)):
    svc = PersonaService(db)
    personas = await svc.get_all_active()
    all_agents = agent_router.get_all_agents()
    result = []
    for persona in personas:
        runtime_agent = all_agents.get(persona.agent_name)
        result.append(
            AgentInfo(
                name=persona.agent_name,
                display_name=persona.display_name,
                role_type=persona.role_type.value,
                avatar_emoji=persona.avatar_emoji,
                is_active=persona.is_active,
                description=runtime_agent.description if runtime_agent else "",
            )
        )
    return result


@agents_api.post("/switch")
async def switch_agent(req: AgentSwitchRequest, db: AsyncSession = Depends(get_db)):
    if req.session_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == req.session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            agent = await get_or_create_agent(
                db,
                code=req.agent_name,
                display_name=req.agent_name,
            )
            session.current_agent_id = agent.id
            await db.flush()
    return {"status": "ok", "agent": req.agent_name}


memory_api = APIRouter(prefix="/api/memory", tags=["Memory"])
objects_api = APIRouter(prefix="/api/objects", tags=["Objects"])


@memory_api.get("", response_model=List[MemoryResponse])
async def list_memories(
    layer: Optional[str] = None,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
):
    svc = MemoryService(db)
    mem_layer = MemoryLayer(layer) if layer else None
    items = await svc.recall(mem_layer, limit=limit)
    return [serialize_memory(item) for item in items]


@memory_api.post("", response_model=MemoryResponse)
async def create_memory(mem: MemoryCreate, db: AsyncSession = Depends(get_db)):
    svc = MemoryService(db)
    item = await svc.store(
        MemoryLayer(mem.layer),
        mem.content,
        tags=mem.tags,
        importance=mem.importance,
    )
    return serialize_memory(item)


@objects_api.post("", response_model=ObjectResponse)
async def create_object(payload: ObjectCreate, db: AsyncSession = Depends(get_db)):
    user, tenant = await ensure_default_context(db)
    agent = await _resolve_agent(db, payload.primary_agent_name)
    object_type = _normalize_object_type(payload.object_type)
    detail_field = _required_detail_field(object_type)
    if detail_field and getattr(payload, detail_field) is None:
        raise HTTPException(
            400,
            f"object_type '{object_type}' requires a '{detail_field}' payload",
        )
    obj = await create_object_record(
        db,
        tenant_id=tenant.id,
        object_type=object_type,
        title=payload.title,
        summary=payload.summary,
        owner_user_id=user.id,
        primary_agent_id=agent.id if agent else None,
        importance=payload.importance,
        confidence=payload.confidence,
        occurred_at=payload.occurred_at,
        due_at=payload.due_at,
        metadata=payload.metadata,
    )
    obj.lifecycle_stage = payload.lifecycle_stage or obj.lifecycle_stage
    obj.visibility = payload.visibility
    await _apply_object_detail(db, obj, payload)
    await db.flush()
    await db.refresh(obj, attribute_names=["primary_agent"])
    return await _serialize_object(db, obj)


@objects_api.get("", response_model=List[ObjectResponse])
async def list_objects(
    object_type: Optional[str] = None,
    lifecycle_stage: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ObjectRecord)
        .options(selectinload(ObjectRecord.primary_agent))
        .where(ObjectRecord.status == ObjectStatus.ACTIVE)
    )
    if object_type:
        stmt = stmt.where(ObjectRecord.object_type == _normalize_object_type(object_type))
    if lifecycle_stage:
        stmt = stmt.where(ObjectRecord.lifecycle_stage == lifecycle_stage)
    if keyword:
        stmt = stmt.where(
            (ObjectRecord.title.contains(keyword)) | (ObjectRecord.summary.contains(keyword))
        )
    stmt = stmt.order_by(ObjectRecord.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    objects = result.scalars().all()
    return [await _serialize_object(db, obj) for obj in objects]


@objects_api.get("/{object_id}", response_model=ObjectResponse)
async def get_object(object_id: str, db: AsyncSession = Depends(get_db)):
    obj = await _get_object_or_404(db, object_id)
    return await _serialize_object(db, obj)


@objects_api.put("/{object_id}", response_model=ObjectResponse)
async def update_object(object_id: str, payload: ObjectUpdate, db: AsyncSession = Depends(get_db)):
    obj = await _get_object_or_404(db, object_id)
    agent = await _resolve_agent(db, payload.primary_agent_name)

    if payload.title is not None:
        obj.title = payload.title
    if payload.summary is not None:
        obj.summary = payload.summary
    if payload.lifecycle_stage is not None:
        obj.lifecycle_stage = payload.lifecycle_stage
    if payload.visibility is not None:
        obj.visibility = payload.visibility
    if payload.importance is not None:
        obj.importance = payload.importance
    if payload.confidence is not None:
        obj.confidence = payload.confidence
    if payload.occurred_at is not None:
        obj.occurred_at = payload.occurred_at
    if payload.due_at is not None:
        obj.due_at = payload.due_at
    if payload.metadata is not None:
        obj.metadata_json = payload.metadata
    if agent is not None:
        obj.primary_agent_id = agent.id

    obj.current_version = (obj.current_version or 1) + 1
    await _apply_object_detail(db, obj, payload)
    await db.flush()
    await db.refresh(obj, attribute_names=["primary_agent"])
    return await _serialize_object(db, obj)


@objects_api.delete("/{object_id}")
async def delete_object(object_id: str, db: AsyncSession = Depends(get_db)):
    obj = await _get_object_or_404(db, object_id)
    obj.status = ObjectStatus.DELETED
    await db.flush()
    return {"status": "ok"}


@objects_api.post("/{object_id}/links", response_model=ObjectLinkResponse)
async def create_object_link(
    object_id: str,
    payload: ObjectLinkCreate,
    db: AsyncSession = Depends(get_db),
):
    user, tenant = await ensure_default_context(db)
    _ = user
    await _get_object_or_404(db, object_id)
    await _get_object_or_404(db, payload.to_object_id)
    row = ObjectLink(
        tenant_id=tenant.id,
        from_object_id=object_id,
        to_object_id=payload.to_object_id,
        link_type=payload.link_type,
        link_role=payload.link_role,
        sort_order=payload.sort_order,
        weight=payload.weight,
        provenance=payload.provenance,
        metadata_json=payload.metadata,
    )
    db.add(row)
    await db.flush()
    return ObjectLinkResponse(
        id=row.id,
        from_object_id=row.from_object_id,
        to_object_id=row.to_object_id,
        link_type=row.link_type,
        link_role=row.link_role,
        sort_order=row.sort_order,
        weight=row.weight,
        provenance=row.provenance,
        metadata=row.metadata_json or {},
        created_at=row.created_at,
    )


@objects_api.get("/{object_id}/links", response_model=List[ObjectLinkResponse])
async def list_object_links(
    object_id: str,
    link_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    await _get_object_or_404(db, object_id)
    stmt = select(ObjectLink).where(
        (ObjectLink.from_object_id == object_id) | (ObjectLink.to_object_id == object_id)
    )
    if link_type:
        stmt = stmt.where(ObjectLink.link_type == link_type)
    stmt = stmt.order_by(ObjectLink.created_at.desc())
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        ObjectLinkResponse(
            id=row.id,
            from_object_id=row.from_object_id,
            to_object_id=row.to_object_id,
            link_type=row.link_type,
            link_role=row.link_role,
            sort_order=row.sort_order,
            weight=row.weight,
            provenance=row.provenance,
            metadata=row.metadata_json or {},
            created_at=row.created_at,
        )
        for row in rows
    ]


@objects_api.post("/{object_id}/evidences", response_model=ObjectEvidenceResponse)
async def create_object_evidence(
    object_id: str,
    payload: ObjectEvidenceCreate,
    db: AsyncSession = Depends(get_db),
):
    await _get_object_or_404(db, object_id)
    row = ObjectEvidence(
        object_id=object_id,
        evidence_type=payload.evidence_type,
        source_system_id=payload.source_system_id,
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        file_id=payload.file_id,
        snippet_text=payload.snippet_text,
        locator=payload.locator,
        checksum=payload.checksum,
        confidence=payload.confidence,
    )
    db.add(row)
    await db.flush()
    return ObjectEvidenceResponse(
        id=row.id,
        object_id=row.object_id,
        evidence_type=row.evidence_type,
        source_system_id=row.source_system_id,
        conversation_id=row.conversation_id,
        message_id=row.message_id,
        file_id=row.file_id,
        snippet_text=row.snippet_text,
        locator=row.locator or {},
        checksum=row.checksum,
        confidence=row.confidence,
        created_at=row.created_at,
    )


@objects_api.get("/{object_id}/evidences", response_model=List[ObjectEvidenceResponse])
async def list_object_evidences(
    object_id: str,
    evidence_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    await _get_object_or_404(db, object_id)
    stmt = select(ObjectEvidence).where(ObjectEvidence.object_id == object_id)
    if evidence_type:
        stmt = stmt.where(ObjectEvidence.evidence_type == evidence_type)
    stmt = stmt.order_by(ObjectEvidence.created_at.desc())
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        ObjectEvidenceResponse(
            id=row.id,
            object_id=row.object_id,
            evidence_type=row.evidence_type,
            source_system_id=row.source_system_id,
            conversation_id=row.conversation_id,
            message_id=row.message_id,
            file_id=row.file_id,
            snippet_text=row.snippet_text,
            locator=row.locator or {},
            checksum=row.checksum,
            confidence=row.confidence,
            created_at=row.created_at,
        )
        for row in rows
    ]


export_api = APIRouter(prefix="/api/data", tags=["Export/Import"])


@export_api.post("/export")
async def export_data(req: ExportRequest, db: AsyncSession = Depends(get_db)):
    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": "0.2.0-generalized-schema",
    }

    if req.include_memories:
        data["memories"] = await MemoryService(db).export_all()

    if req.include_personas:
        data["personas"] = await PersonaService(db).export_all()

    if req.include_documents:
        result = await db.execute(
            select(ObjectDocument)
            .join(ObjectRecord, ObjectDocument.object_id == ObjectRecord.id)
            .options(selectinload(ObjectDocument.object))
            .where(ObjectRecord.status == ObjectStatus.ACTIVE)
        )
        docs = result.scalars().all()
        data["documents"] = [
            {
                "id": doc.id,
                "title": doc.title,
                "content": doc.content,
                "category": doc.category,
                "project": doc.project,
                "tags": doc.tags,
                "is_knowledge": doc.is_knowledge,
            }
            for doc in docs
        ]

    if req.include_tasks:
        tasks = await TaskService(db).get_all(limit=10000)
        data["tasks"] = [
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "priority": task.priority.value,
                "task_status": task.task_status.value,
                "project": task.project,
                "tags": task.tags,
            }
            for task in tasks
        ]

    if req.include_objects:
        result = await db.execute(
            select(ObjectRecord)
            .options(selectinload(ObjectRecord.primary_agent))
            .where(ObjectRecord.status == ObjectStatus.ACTIVE)
            .order_by(ObjectRecord.created_at.desc())
        )
        data["objects"] = [
            (await _serialize_object(db, obj)).model_dump(mode="json")
            for obj in result.scalars().all()
        ]

    filename = f"aos_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = settings.EXPORT_DIR / filename
    with open(filepath, "w", encoding="utf-8") as output:
        json.dump(data, output, ensure_ascii=False, indent=2)

    return ExportResponse(
        filename=filename,
        size_bytes=os.path.getsize(filepath),
        exported_at=datetime.now(timezone.utc),
    )


@export_api.post("/import")
async def import_data(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    content = await file.read()
    data = json.loads(content.decode("utf-8"))

    counts = {}
    if "memories" in data:
        counts["memories"] = await MemoryService(db).import_memories(data["memories"])

    if "documents" in data:
        user, tenant = await ensure_default_context(db)
        created = 0
        for item in data["documents"]:
            obj = await create_object_record(
                db,
                tenant_id=tenant.id,
                object_type="document",
                title=item["title"],
                summary=(item.get("content") or "")[:200] or None,
                owner_user_id=user.id,
            )
            doc = ObjectDocument(
                object_id=obj.id,
                content=item.get("content"),
                category=item.get("category"),
                project=item.get("project"),
                tags=item.get("tags", []),
                is_knowledge=item.get("is_knowledge", True),
                file_type="markdown",
            )
            db.add(doc)
            created += 1
        counts["documents"] = created

    if "tasks" in data:
        svc = TaskService(db)
        created = 0
        for item in data["tasks"]:
            await svc.create(
                title=item["title"],
                description=item.get("description"),
                priority=TaskPriority(item.get("priority", "medium")),
                project=item.get("project"),
                tags=item.get("tags", []),
            )
            created += 1
        counts["tasks"] = created

    await db.flush()
    return {"status": "ok", "imported": counts}

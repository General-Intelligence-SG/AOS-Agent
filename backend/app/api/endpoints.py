"""AOS resource APIs backed by the generalized schema."""
from datetime import datetime, timezone
from typing import List, Optional
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
    Conversation,
    FileRecord,
    MemoryLayer,
    ObjectDocument,
    ObjectMemory,
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

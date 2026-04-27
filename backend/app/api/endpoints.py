"""AOS Knowledge / Documents / Tasks / Memory / Agents / Export API"""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json, os, hashlib

from app.database import get_db
from app.config import settings
from app.models import (
    Document, Task, TaskStatus, TaskPriority, MemoryItem, MemoryLayer,
    Persona, ObjectStatus, ChatSession,
)
from app.api.schemas import (
    DocumentCreate, DocumentResponse,
    TaskCreate, TaskUpdate, TaskResponse,
    AgentInfo, AgentSwitchRequest,
    MemoryCreate, MemoryResponse,
    ExportRequest, ExportResponse,
)
from app.core.memory import MemoryService
from app.core.persona import PersonaService
from app.core.workflow import TaskService
from app.core.policy import PolicyService
from app.agents.router import router as agent_router

# ════════════════════ Knowledge / Documents ════════════════════
knowledge_api = APIRouter(prefix="/api/knowledge", tags=["Knowledge"])


@knowledge_api.post("", response_model=DocumentResponse)
async def create_document(
    doc: DocumentCreate, db: AsyncSession = Depends(get_db)
):
    """创建文档/知识条目"""
    d = Document(
        title=doc.title,
        content=doc.content,
        category=doc.category,
        project=doc.project,
        tags=doc.tags,
        is_knowledge=doc.is_knowledge,
        file_type="markdown",
    )
    db.add(d)
    await db.flush()
    return d


@knowledge_api.get("", response_model=List[DocumentResponse])
async def list_documents(
    category: Optional[str] = None,
    project: Optional[str] = None,
    is_knowledge: Optional[bool] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """列出文档"""
    stmt = select(Document).where(Document.status == ObjectStatus.ACTIVE)
    if category:
        stmt = stmt.where(Document.category == category)
    if project:
        stmt = stmt.where(Document.project == project)
    if is_knowledge is not None:
        stmt = stmt.where(Document.is_knowledge == is_knowledge)
    stmt = stmt.order_by(Document.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@knowledge_api.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Document).where(Document.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@knowledge_api.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: str, update: DocumentCreate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    for field in ["title", "content", "category", "project", "tags", "is_knowledge"]:
        setattr(doc, field, getattr(update, field))
    doc.version = (doc.version or 1) + 1
    await db.flush()
    return doc


@knowledge_api.delete("/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Document).where(Document.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if doc:
        doc.status = ObjectStatus.DELETED
        await db.flush()
    return {"status": "ok"}


@knowledge_api.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form(""),
    project: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    """上传文件到知识库"""
    content = await file.read()
    # 保存文件
    safe_name = file.filename.replace(" ", "_")
    file_path = settings.FILES_DIR / safe_name
    with open(file_path, "wb") as f:
        f.write(content)

    # 文本文件尝试读取内容
    text_content = None
    ext = os.path.splitext(safe_name)[1].lower()
    if ext in [".txt", ".md", ".csv", ".json"]:
        try:
            text_content = content.decode("utf-8")
        except Exception:
            text_content = None

    doc = Document(
        title=file.filename,
        content=text_content,
        file_path=str(file_path),
        file_type=ext.lstrip("."),
        file_size=len(content),
        category=category or None,
        project=project or None,
        is_knowledge=True,
    )
    db.add(doc)
    await db.flush()
    return {"id": doc.id, "title": doc.title, "size": len(content)}


# ════════════════════ Tasks ════════════════════
tasks_api = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@tasks_api.post("", response_model=TaskResponse)
async def create_task(
    task: TaskCreate, db: AsyncSession = Depends(get_db)
):
    svc = TaskService(db)
    t = await svc.create(
        title=task.title,
        description=task.description,
        priority=TaskPriority(task.priority),
        project=task.project,
        due_date=task.due_date,
        tags=task.tags,
    )
    return t


@tasks_api.get("", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    svc = TaskService(db)
    task_status = TaskStatus(status) if status else None
    return await svc.get_all(status=task_status, project=project, limit=limit)


@tasks_api.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str, update: TaskUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    if update.title is not None:
        task.title = update.title
    if update.description is not None:
        task.description = update.description
    if update.priority is not None:
        task.priority = TaskPriority(update.priority)
    if update.task_status is not None:
        task.task_status = TaskStatus(update.task_status)
    if update.project is not None:
        task.project = update.project
    if update.due_date is not None:
        task.due_date = update.due_date
    if update.tags is not None:
        task.tags = update.tags
    await db.flush()
    return task


@tasks_api.delete("/{task_id}")
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task:
        task.status = ObjectStatus.DELETED
        await db.flush()
    return {"status": "ok"}


# ════════════════════ Agents ════════════════════
agents_api = APIRouter(prefix="/api/agents", tags=["Agents"])


@agents_api.get("", response_model=List[AgentInfo])
async def list_agents(db: AsyncSession = Depends(get_db)):
    """列出所有 Agent 及其人格"""
    svc = PersonaService(db)
    personas = await svc.get_all_active()
    all_agents = agent_router.get_all_agents()
    result = []
    for p in personas:
        agent = all_agents.get(p.agent_name)
        result.append(AgentInfo(
            name=p.agent_name,
            display_name=p.display_name,
            role_type=p.role_type.value,
            avatar_emoji=p.avatar_emoji,
            is_active=p.is_active,
            description=agent.description if agent else "",
        ))
    return result


@agents_api.post("/switch")
async def switch_agent(
    req: AgentSwitchRequest, db: AsyncSession = Depends(get_db)
):
    """切换当前 Agent"""
    if req.session_id:
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == req.session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            session.current_agent = req.agent_name
            await db.flush()
    return {"status": "ok", "agent": req.agent_name}


# ════════════════════ Memory ════════════════════
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
    return items


@memory_api.post("", response_model=MemoryResponse)
async def create_memory(
    mem: MemoryCreate, db: AsyncSession = Depends(get_db)
):
    svc = MemoryService(db)
    item = await svc.store(
        MemoryLayer(mem.layer),
        mem.content,
        tags=mem.tags,
        importance=mem.importance,
    )
    return item


# ════════════════════ Export / Import ════════════════════
export_api = APIRouter(prefix="/api/data", tags=["Export/Import"])


@export_api.post("/export")
async def export_data(
    req: ExportRequest, db: AsyncSession = Depends(get_db)
):
    """导出所有数据为 JSON"""
    data = {"exported_at": datetime.now(timezone.utc).isoformat(), "version": "0.1.0"}

    if req.include_memories:
        svc = MemoryService(db)
        data["memories"] = await svc.export_all()

    if req.include_personas:
        svc = PersonaService(db)
        data["personas"] = await svc.export_all()

    if req.include_documents:
        result = await db.execute(
            select(Document).where(Document.status == ObjectStatus.ACTIVE)
        )
        docs = result.scalars().all()
        data["documents"] = [
            {
                "id": d.id, "title": d.title, "content": d.content,
                "category": d.category, "project": d.project,
                "tags": d.tags, "is_knowledge": d.is_knowledge,
            }
            for d in docs
        ]

    if req.include_tasks:
        result = await db.execute(
            select(Task).where(Task.status == ObjectStatus.ACTIVE)
        )
        tasks = result.scalars().all()
        data["tasks"] = [
            {
                "id": t.id, "title": t.title, "description": t.description,
                "priority": t.priority.value, "task_status": t.task_status.value,
                "project": t.project, "tags": t.tags,
            }
            for t in tasks
        ]

    # 保存到文件
    filename = f"aos_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = settings.EXPORT_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return ExportResponse(
        filename=filename,
        size_bytes=os.path.getsize(filepath),
        exported_at=datetime.now(timezone.utc),
    )


@export_api.post("/import")
async def import_data(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """导入 JSON 数据"""
    content = await file.read()
    data = json.loads(content.decode("utf-8"))

    counts = {}
    if "memories" in data:
        svc = MemoryService(db)
        counts["memories"] = await svc.import_memories(data["memories"])

    if "documents" in data:
        c = 0
        for d in data["documents"]:
            doc = Document(
                title=d["title"],
                content=d.get("content"),
                category=d.get("category"),
                project=d.get("project"),
                tags=d.get("tags", []),
                is_knowledge=d.get("is_knowledge", True),
            )
            db.add(doc)
            c += 1
        counts["documents"] = c

    if "tasks" in data:
        c = 0
        for t in data["tasks"]:
            task = Task(
                title=t["title"],
                description=t.get("description"),
                priority=TaskPriority(t.get("priority", "medium")),
                task_status=TaskStatus(t.get("task_status", "todo")),
                project=t.get("project"),
                tags=t.get("tags", []),
            )
            db.add(task)
            c += 1
        counts["tasks"] = c

    await db.flush()
    return {"status": "ok", "imported": counts}

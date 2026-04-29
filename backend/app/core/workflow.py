"""Workflow and task services backed by generalized object tables."""
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.storage import create_object_record, ensure_default_context, get_or_create_agent
from app.models import (
    ObjectRecord,
    ObjectStatus,
    ObjectWorkItem,
    ObjectWorkflow,
    TaskPriority,
    TaskStatus,
    WorkflowStatus,
)


class WorkflowService:
    """Workflow orchestration service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_workflow(
        self,
        name: str,
        workflow_type: str,
        steps: List[Dict[str, Any]],
        assigned_agent: str = None,
        description: str = None,
    ) -> ObjectWorkflow:
        user, tenant = await ensure_default_context(self.db)
        agent = None
        if assigned_agent:
            agent = await get_or_create_agent(self.db, code=assigned_agent, display_name=assigned_agent)

        obj = await create_object_record(
            self.db,
            tenant_id=tenant.id,
            object_type="workflow",
            title=name,
            summary=description,
            owner_user_id=user.id,
            primary_agent_id=agent.id if agent else None,
        )
        wf = ObjectWorkflow(
            object_id=obj.id,
            workflow_type=workflow_type,
            description=description,
            steps=steps,
            assigned_agent_id=agent.id if agent else None,
        )
        self.db.add(wf)
        await self.db.flush()
        await self.db.refresh(wf, attribute_names=["object", "assigned_agent"])
        return wf

    async def _get_workflow(self, workflow_id: str) -> Optional[ObjectWorkflow]:
        result = await self.db.execute(
            select(ObjectWorkflow)
            .options(selectinload(ObjectWorkflow.object))
            .where(ObjectWorkflow.id == workflow_id)
        )
        return result.scalar_one_or_none()

    async def advance(self, workflow_id: str) -> ObjectWorkflow:
        wf = await self._get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow {workflow_id} not found")

        steps = list(wf.steps or [])
        if wf.current_step < len(steps):
            steps[wf.current_step]["status"] = "completed"
            wf.current_step += 1
            if wf.current_step >= len(steps):
                wf.workflow_status = WorkflowStatus.COMPLETED
            else:
                steps[wf.current_step]["status"] = "running"
                wf.workflow_status = WorkflowStatus.RUNNING
            wf.steps = steps
        await self.db.flush()
        return wf

    async def pause(self, workflow_id: str) -> Optional[ObjectWorkflow]:
        wf = await self._get_workflow(workflow_id)
        if wf:
            wf.checkpoint_data = {"paused_step": wf.current_step}
            wf.workflow_status = WorkflowStatus.PAUSED
            await self.db.flush()
        return wf

    async def resume(self, workflow_id: str) -> Optional[ObjectWorkflow]:
        wf = await self._get_workflow(workflow_id)
        if wf and wf.workflow_status == WorkflowStatus.PAUSED:
            wf.workflow_status = WorkflowStatus.RUNNING
            await self.db.flush()
        return wf

    async def rollback(self, workflow_id: str) -> Optional[ObjectWorkflow]:
        wf = await self._get_workflow(workflow_id)
        if wf and wf.current_step > 0:
            steps = list(wf.steps or [])
            if wf.current_step < len(steps):
                steps[wf.current_step]["status"] = "pending"
            wf.current_step -= 1
            steps[wf.current_step]["status"] = "running"
            wf.steps = steps
            wf.workflow_status = WorkflowStatus.RUNNING
            await self.db.flush()
        return wf

    async def get_active(self) -> List[ObjectWorkflow]:
        result = await self.db.execute(
            select(ObjectWorkflow)
            .join(ObjectRecord, ObjectWorkflow.object_id == ObjectRecord.id)
            .options(selectinload(ObjectWorkflow.object))
            .where(
                ObjectWorkflow.workflow_status.in_([WorkflowStatus.RUNNING, WorkflowStatus.PAUSED]),
                ObjectRecord.status == ObjectStatus.ACTIVE,
            )
        )
        return list(result.scalars().all())


class TaskService:
    """Task service backed by objects + object_work_items."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        title: str,
        description: str = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        assigned_agent: str = None,
        project: str = None,
        due_date=None,
        tags: List[str] = None,
        source_session: str = None,
        work_item_kind: str = "task",
    ) -> ObjectWorkItem:
        user, tenant = await ensure_default_context(self.db)
        agent = None
        if assigned_agent:
            agent = await get_or_create_agent(self.db, code=assigned_agent, display_name=assigned_agent)

        obj = await create_object_record(
            self.db,
            tenant_id=tenant.id,
            object_type="work_item",
            title=title,
            summary=description,
            owner_user_id=user.id,
            primary_agent_id=agent.id if agent else None,
            due_at=due_date,
            metadata={"project": project, "tags": tags or []},
        )
        task = ObjectWorkItem(
            object_id=obj.id,
            work_item_kind=work_item_kind,
            description=description,
            priority=priority,
            assigned_agent_id=agent.id if agent else None,
            project=project,
            due_date=due_date,
            tags=tags or [],
            source_conversation_id=source_session,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task, attribute_names=["object", "assigned_agent"])
        return task

    async def update_status(
        self, task_id: str, new_status: TaskStatus
    ) -> Optional[ObjectWorkItem]:
        task = await self.get_by_id(task_id)
        if task:
            task.task_status = new_status
            await self.db.flush()
        return task

    async def get_all(
        self,
        status: TaskStatus = None,
        project: str = None,
        limit: int = 50,
    ) -> List[ObjectWorkItem]:
        stmt = (
            select(ObjectWorkItem)
            .join(ObjectRecord, ObjectWorkItem.object_id == ObjectRecord.id)
            .options(
                selectinload(ObjectWorkItem.object),
                selectinload(ObjectWorkItem.assigned_agent),
            )
            .where(
                ObjectRecord.status == ObjectStatus.ACTIVE,
                ObjectWorkItem.work_item_kind == "task",
            )
        )
        if status:
            stmt = stmt.where(ObjectWorkItem.task_status == status)
        if project:
            stmt = stmt.where(ObjectWorkItem.project == project)
        stmt = stmt.order_by(ObjectRecord.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, task_id: str) -> Optional[ObjectWorkItem]:
        result = await self.db.execute(
            select(ObjectWorkItem)
            .options(
                selectinload(ObjectWorkItem.object),
                selectinload(ObjectWorkItem.assigned_agent),
            )
            .where(ObjectWorkItem.id == task_id)
        )
        return result.scalar_one_or_none()

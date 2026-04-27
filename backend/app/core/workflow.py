"""AOS 工作流标准层 — 流程编排与任务闭环"""
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    Workflow, WorkflowStatus, Task, TaskStatus, TaskPriority,
    ObjectStatus,
)


class WorkflowService:
    """工作流编排引擎"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_workflow(
        self,
        name: str,
        workflow_type: str,
        steps: List[Dict],
        assigned_agent: str = None,
        description: str = None,
    ) -> Workflow:
        wf = Workflow(
            name=name,
            workflow_type=workflow_type,
            steps=steps,
            assigned_agent=assigned_agent,
            description=description,
        )
        self.db.add(wf)
        await self.db.flush()
        return wf

    async def advance(self, workflow_id: str) -> Workflow:
        """推进到下一步"""
        stmt = select(Workflow).where(Workflow.id == workflow_id)
        result = await self.db.execute(stmt)
        wf = result.scalar_one_or_none()
        if not wf:
            raise ValueError(f"Workflow {workflow_id} not found")

        steps = wf.steps or []
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

    async def pause(self, workflow_id: str) -> Workflow:
        stmt = select(Workflow).where(Workflow.id == workflow_id)
        result = await self.db.execute(stmt)
        wf = result.scalar_one_or_none()
        if wf:
            wf.checkpoint_data = {"paused_step": wf.current_step}
            wf.workflow_status = WorkflowStatus.PAUSED
            await self.db.flush()
        return wf

    async def resume(self, workflow_id: str) -> Workflow:
        stmt = select(Workflow).where(Workflow.id == workflow_id)
        result = await self.db.execute(stmt)
        wf = result.scalar_one_or_none()
        if wf and wf.workflow_status == WorkflowStatus.PAUSED:
            wf.workflow_status = WorkflowStatus.RUNNING
            await self.db.flush()
        return wf

    async def rollback(self, workflow_id: str) -> Workflow:
        stmt = select(Workflow).where(Workflow.id == workflow_id)
        result = await self.db.execute(stmt)
        wf = result.scalar_one_or_none()
        if wf and wf.current_step > 0:
            steps = wf.steps or []
            steps[wf.current_step]["status"] = "pending"
            wf.current_step -= 1
            steps[wf.current_step]["status"] = "running"
            wf.steps = steps
            wf.workflow_status = WorkflowStatus.RUNNING
            await self.db.flush()
        return wf

    async def get_active(self) -> List[Workflow]:
        stmt = select(Workflow).where(
            Workflow.workflow_status.in_([
                WorkflowStatus.RUNNING, WorkflowStatus.PAUSED
            ]),
            Workflow.status == ObjectStatus.ACTIVE,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class TaskService:
    """任务管理服务"""

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
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            priority=priority,
            assigned_agent=assigned_agent,
            project=project,
            due_date=due_date,
            tags=tags or [],
            source_session=source_session,
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def update_status(
        self, task_id: str, new_status: TaskStatus
    ) -> Optional[Task]:
        stmt = select(Task).where(Task.id == task_id)
        result = await self.db.execute(stmt)
        task = result.scalar_one_or_none()
        if task:
            task.task_status = new_status
            await self.db.flush()
        return task

    async def get_all(
        self,
        status: TaskStatus = None,
        project: str = None,
        limit: int = 50,
    ) -> List[Task]:
        stmt = select(Task).where(Task.status == ObjectStatus.ACTIVE)
        if status:
            stmt = stmt.where(Task.task_status == status)
        if project:
            stmt = stmt.where(Task.project == project)
        stmt = stmt.order_by(Task.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, task_id: str) -> Optional[Task]:
        stmt = select(Task).where(Task.id == task_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

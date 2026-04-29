"""Memory service backed by objects + object_memories."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.storage import create_object_record, ensure_default_context, get_agent_by_code, get_or_create_agent
from app.models import MemoryLayer, ObjectMemory, ObjectRecord, ObjectStatus


class MemoryService:
    """Generalized memory service with compatibility behavior."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def store(
        self,
        layer: MemoryLayer,
        content: str,
        *,
        summary: str = None,
        tags: List[str] = None,
        source_agent: str = None,
        source_session: str = None,
        embedding: np.ndarray = None,
        importance: float = 0.5,
        relations: Dict[str, Any] = None,
    ) -> ObjectMemory:
        user, tenant = await ensure_default_context(self.db)
        agent = None
        if source_agent:
            agent = await get_or_create_agent(self.db, code=source_agent, display_name=source_agent)

        memory_summary = summary or content[:200]
        obj = await create_object_record(
            self.db,
            tenant_id=tenant.id,
            object_type="memory",
            title=memory_summary[:120] or "memory",
            summary=memory_summary,
            owner_user_id=user.id,
            primary_agent_id=agent.id if agent else None,
            importance=importance,
            metadata={"tags": tags or []},
        )
        item = ObjectMemory(
            object_id=obj.id,
            layer=layer,
            content=content,
            tags=tags or [],
            source_agent_id=agent.id if agent else None,
            source_conversation_id=source_session,
            embedding=embedding.tobytes() if isinstance(embedding, np.ndarray) else embedding,
            relations=relations or {},
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item, attribute_names=["object", "source_agent"])
        return item

    async def recall(
        self,
        layer: Optional[MemoryLayer] = None,
        *,
        limit: int = 20,
        tags: List[str] = None,
        source_agent: str = None,
        min_importance: float = 0.0,
    ) -> List[ObjectMemory]:
        stmt = (
            select(ObjectMemory)
            .join(ObjectRecord, ObjectMemory.object_id == ObjectRecord.id)
            .options(
                selectinload(ObjectMemory.object),
                selectinload(ObjectMemory.source_agent),
            )
            .where(ObjectRecord.status == ObjectStatus.ACTIVE)
        )
        if layer:
            stmt = stmt.where(ObjectMemory.layer == layer)
        if source_agent:
            agent = await get_agent_by_code(self.db, source_agent)
            if not agent:
                return []
            stmt = stmt.where(ObjectMemory.source_agent_id == agent.id)
        if min_importance > 0:
            stmt = stmt.where(ObjectRecord.importance >= min_importance)
        stmt = stmt.order_by(ObjectRecord.created_at.desc()).limit(limit)

        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        if tags:
            items = [item for item in items if any(tag in (item.tags or []) for tag in tags)]

        for item in items:
            item.access_count = (item.access_count or 0) + 1
            item.last_accessed = datetime.now(timezone.utc)

        return items

    async def semantic_search(
        self,
        query_embedding: np.ndarray,
        *,
        layer: Optional[MemoryLayer] = None,
        top_k: int = 10,
        threshold: float = 0.7,
    ) -> List[tuple[ObjectMemory, float]]:
        stmt = (
            select(ObjectMemory)
            .join(ObjectRecord, ObjectMemory.object_id == ObjectRecord.id)
            .options(selectinload(ObjectMemory.object))
            .where(
                and_(
                    ObjectRecord.status == ObjectStatus.ACTIVE,
                    ObjectMemory.embedding.is_not(None),
                )
            )
        )
        if layer:
            stmt = stmt.where(ObjectMemory.layer == layer)

        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        scored: List[tuple[ObjectMemory, float]] = []
        q_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
        for item in items:
            vec = np.frombuffer(item.embedding, dtype=np.float32)
            if len(vec) != len(query_embedding):
                continue
            v_norm = vec / (np.linalg.norm(vec) + 1e-10)
            score = float(np.dot(q_norm, v_norm))
            if score >= threshold:
                scored.append((item, score))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    async def store_with_conflict_check(
        self,
        layer: MemoryLayer,
        content: str,
        query_embedding: np.ndarray = None,
        **kwargs,
    ) -> ObjectMemory:
        conflict_object_id = None
        if query_embedding is not None:
            similar = await self.semantic_search(
                query_embedding,
                layer=layer,
                top_k=1,
                threshold=0.9,
            )
            if similar:
                existing, _ = similar[0]
                conflict_object_id = existing.object_id
                if existing.object:
                    existing.object.current_version = (existing.object.current_version or 1) + 1

        item = await self.store(layer, content, embedding=query_embedding, **kwargs)
        if conflict_object_id:
            item.conflict_object_id = conflict_object_id
        return item

    async def get_short_term(self, session_id: str, limit: int = 20) -> List[ObjectMemory]:
        stmt = (
            select(ObjectMemory)
            .join(ObjectRecord, ObjectMemory.object_id == ObjectRecord.id)
            .options(selectinload(ObjectMemory.object))
            .where(
                ObjectRecord.status == ObjectStatus.ACTIVE,
                ObjectMemory.layer == MemoryLayer.SHORT_TERM,
                ObjectMemory.source_conversation_id == session_id,
            )
            .order_by(ObjectRecord.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_profile_memories(self) -> List[ObjectMemory]:
        return await self.recall(MemoryLayer.PROFILE, limit=50)

    async def update_profile(
        self, aspect: str, content: str, source_agent: str = "system"
    ) -> ObjectMemory:
        return await self.store(
            MemoryLayer.PROFILE,
            content,
            tags=[aspect],
            source_agent=source_agent,
            importance=0.9,
        )

    async def get_policy_memories(self, context_tags: List[str] = None) -> List[ObjectMemory]:
        return await self.recall(MemoryLayer.POLICY, tags=context_tags, limit=20)

    async def store_policy_learning(
        self, content: str, tags: List[str], source_agent: str
    ) -> ObjectMemory:
        return await self.store(
            MemoryLayer.POLICY,
            content,
            tags=tags,
            source_agent=source_agent,
            importance=0.8,
        )

    async def export_all(self) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(ObjectMemory)
            .join(ObjectRecord, ObjectMemory.object_id == ObjectRecord.id)
            .options(
                selectinload(ObjectMemory.object),
                selectinload(ObjectMemory.source_agent),
            )
            .where(ObjectRecord.status == ObjectStatus.ACTIVE)
            .order_by(ObjectRecord.created_at.desc())
        )
        items = result.scalars().all()
        return [
            {
                "id": item.id,
                "layer": item.layer.value,
                "content": item.content,
                "summary": item.summary,
                "tags": item.tags,
                "source_agent": item.source_agent_name,
                "importance": item.importance,
                "version": item.version,
                "conflict_with": item.conflict_with,
                "created_at": item.object.created_at.isoformat() if item.object and item.object.created_at else None,
            }
            for item in items
        ]

    async def import_memories(self, data: List[Dict]) -> int:
        count = 0
        for item in data:
            await self.store(
                layer=MemoryLayer(item["layer"]),
                content=item["content"],
                summary=item.get("summary"),
                tags=item.get("tags", []),
                source_agent=item.get("source_agent"),
                importance=item.get("importance", 0.5),
            )
            count += 1
        return count

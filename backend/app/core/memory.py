"""AOS 记忆标准层 — 6层记忆分层管理"""
import json
import numpy as np
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import MemoryItem, MemoryLayer, ObjectStatus


class MemoryService:
    """6层记忆分层服务

    ShortTerm  — 会话级上下文窗口
    LongTerm   — 持久化知识（向量检索）
    Episodic   — 关键事件记录
    Procedural — 工作流偏好
    Profile    — 用户画像（设备端）
    Policy     — 策略记忆（简化版）
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ────────── 写入 ──────────
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
        relations: Dict = None,
    ) -> MemoryItem:
        """写入一条记忆"""
        item = MemoryItem(
            layer=layer,
            content=content,
            summary=summary or content[:200],
            tags=tags or [],
            source_agent=source_agent,
            source_session=source_session,
            embedding=embedding.tobytes() if embedding is not None else None,
            importance=importance,
            relations=relations or {},
        )
        self.db.add(item)
        await self.db.flush()
        return item

    # ────────── 检索 ──────────
    async def recall(
        self,
        layer: Optional[MemoryLayer] = None,
        *,
        limit: int = 20,
        tags: List[str] = None,
        source_agent: str = None,
        min_importance: float = 0.0,
    ) -> List[MemoryItem]:
        """按条件检索记忆"""
        stmt = select(MemoryItem).where(
            MemoryItem.status == ObjectStatus.ACTIVE
        )
        if layer:
            stmt = stmt.where(MemoryItem.layer == layer)
        if source_agent:
            stmt = stmt.where(MemoryItem.source_agent == source_agent)
        if min_importance > 0:
            stmt = stmt.where(MemoryItem.importance >= min_importance)
        stmt = stmt.order_by(MemoryItem.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        # 标签过滤（JSON 数组内匹配）
        if tags:
            items = [
                m for m in items
                if any(t in (m.tags or []) for t in tags)
            ]

        # 更新访问计数
        for item in items:
            item.access_count = (item.access_count or 0) + 1
            item.last_accessed = datetime.now(timezone.utc)

        return items

    # ────────── 向量检索 ──────────
    async def semantic_search(
        self,
        query_embedding: np.ndarray,
        *,
        layer: Optional[MemoryLayer] = None,
        top_k: int = 10,
        threshold: float = 0.7,
    ) -> List[tuple]:
        """基于向量相似度的语义检索，返回 [(MemoryItem, score)]"""
        stmt = select(MemoryItem).where(
            and_(
                MemoryItem.status == ObjectStatus.ACTIVE,
                MemoryItem.embedding.isnot(None),
            )
        )
        if layer:
            stmt = stmt.where(MemoryItem.layer == layer)
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        # 计算余弦相似度
        scored = []
        q_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
        for item in items:
            vec = np.frombuffer(item.embedding, dtype=np.float32)
            if len(vec) != len(query_embedding):
                continue
            v_norm = vec / (np.linalg.norm(vec) + 1e-10)
            score = float(np.dot(q_norm, v_norm))
            if score >= threshold:
                scored.append((item, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # ────────── 冲突检测 ──────────
    async def store_with_conflict_check(
        self,
        layer: MemoryLayer,
        content: str,
        query_embedding: np.ndarray = None,
        **kwargs,
    ) -> MemoryItem:
        """写入前检查冲突，若有相似记忆则标注"""
        conflict_id = None
        if query_embedding is not None:
            similar = await self.semantic_search(
                query_embedding, layer=layer, top_k=1, threshold=0.9
            )
            if similar:
                existing, score = similar[0]
                # 保留旧版本，新记忆标注冲突
                conflict_id = existing.id
                existing.version = (existing.version or 1) + 1

        item = await self.store(
            layer, content, embedding=query_embedding, **kwargs
        )
        if conflict_id:
            item.conflict_with = conflict_id
        return item

    # ────────── 会话短期记忆 ──────────
    async def get_short_term(
        self, session_id: str, limit: int = 20
    ) -> List[MemoryItem]:
        """获取会话级短期记忆"""
        return await self.recall(
            MemoryLayer.SHORT_TERM,
            source_agent=None,
            limit=limit,
        )

    # ────────── 用户画像 ──────────
    async def get_profile_memories(self) -> List[MemoryItem]:
        """获取用户画像记忆"""
        return await self.recall(MemoryLayer.PROFILE, limit=50)

    async def update_profile(
        self, aspect: str, content: str, source_agent: str = "system"
    ) -> MemoryItem:
        """更新用户画像的某个方面"""
        return await self.store(
            MemoryLayer.PROFILE,
            content,
            tags=[aspect],
            source_agent=source_agent,
            importance=0.9,
        )

    # ────────── 策略记忆（简化版） ──────────
    async def get_policy_memories(
        self, context_tags: List[str] = None
    ) -> List[MemoryItem]:
        """获取策略记忆（用于动态策略调整）"""
        return await self.recall(
            MemoryLayer.POLICY, tags=context_tags, limit=20
        )

    async def store_policy_learning(
        self, content: str, tags: List[str], source_agent: str
    ) -> MemoryItem:
        """记录策略学习结果"""
        return await self.store(
            MemoryLayer.POLICY,
            content,
            tags=tags,
            source_agent=source_agent,
            importance=0.8,
        )

    # ────────── 导出 / 导入 ──────────
    async def export_all(self) -> List[Dict[str, Any]]:
        """导出所有记忆为 JSON"""
        result = await self.db.execute(
            select(MemoryItem).where(
                MemoryItem.status == ObjectStatus.ACTIVE
            )
        )
        items = result.scalars().all()
        return [
            {
                "id": m.id,
                "layer": m.layer.value,
                "content": m.content,
                "summary": m.summary,
                "tags": m.tags,
                "source_agent": m.source_agent,
                "importance": m.importance,
                "version": m.version,
                "conflict_with": m.conflict_with,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in items
        ]

    async def import_memories(self, data: List[Dict]) -> int:
        """导入记忆数据"""
        count = 0
        for m in data:
            item = MemoryItem(
                layer=MemoryLayer(m["layer"]),
                content=m["content"],
                summary=m.get("summary"),
                tags=m.get("tags", []),
                source_agent=m.get("source_agent"),
                importance=m.get("importance", 0.5),
                version=m.get("version", 1),
            )
            self.db.add(item)
            count += 1
        await self.db.flush()
        return count

"""Policy and audit services backed by generalized tables."""
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.storage import create_object_record, ensure_default_context, get_agent_by_code, get_or_create_agent
from app.models import (
    AuditLog,
    ObjectPolicy,
    ObjectRecord,
    ObjectStatus,
    PolicyAction,
    RiskLevel,
)


HIGH_RISK_ACTIONS = {
    "delete": RiskLevel.HIGH,
    "send_email": RiskLevel.MEDIUM,
    "send_message": RiskLevel.MEDIUM,
    "payment": RiskLevel.CRITICAL,
    "contract_sign": RiskLevel.CRITICAL,
    "permission_change": RiskLevel.HIGH,
    "public_publish": RiskLevel.HIGH,
    "commit_on_behalf": RiskLevel.CRITICAL,
    "export_data": RiskLevel.MEDIUM,
    "bulk_delete": RiskLevel.CRITICAL,
    "change_settings": RiskLevel.MEDIUM,
}


class PolicyService:
    """Policy gate and audit service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check(
        self,
        action: str,
        agent_name: str,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        context = context or {}
        policies = await self.get_policies()

        for policy in policies:
            if self._matches(policy, action, agent_name, context):
                return {
                    "allowed": policy.action != PolicyAction.DENY,
                    "action": policy.action,
                    "reason": policy.description or policy.name,
                    "requires_confirmation": policy.action == PolicyAction.CONFIRM,
                    "risk_level": policy.risk_level,
                    "policy_id": policy.id,
                }

        if action in HIGH_RISK_ACTIONS:
            risk = HIGH_RISK_ACTIONS[action]
            return {
                "allowed": True,
                "action": PolicyAction.CONFIRM,
                "reason": f"Built-in safety policy: {action} is treated as {risk.value} risk",
                "requires_confirmation": True,
                "risk_level": risk,
                "policy_id": None,
            }

        return {
            "allowed": True,
            "action": PolicyAction.ALLOW,
            "reason": "default allow",
            "requires_confirmation": False,
            "risk_level": RiskLevel.LOW,
            "policy_id": None,
        }

    def _matches(
        self,
        policy: ObjectPolicy,
        action: str,
        agent_name: str,
        context: Dict[str, Any],
    ) -> bool:
        conditions = policy.conditions or {}
        if "actions" in conditions and action not in conditions["actions"]:
            return False

        if policy.applies_to_agents and agent_name not in policy.applies_to_agents:
            return False

        if "context_keys" in conditions:
            for key in conditions["context_keys"]:
                if key not in context:
                    return False

        return True

    async def record_audit(
        self,
        action: str,
        agent_name: str,
        target_type: str = None,
        target_id: str = None,
        details: Dict[str, Any] = None,
        risk_level: RiskLevel = RiskLevel.LOW,
        user_confirmed: bool = False,
        session_id: str = None,
    ) -> AuditLog:
        _, tenant = await ensure_default_context(self.db)
        agent = None
        if agent_name:
            agent = await get_or_create_agent(self.db, code=agent_name, display_name=agent_name)

        audit = AuditLog(
            tenant_id=tenant.id,
            actor_agent_id=agent.id if agent else None,
            conversation_id=session_id,
            action_type=action,
            risk_level=risk_level,
            requires_confirmation=not user_confirmed and risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL},
            confirmed_at=None if not user_confirmed else audit_time(),
            details={
                "target_type": target_type,
                "target_id": target_id,
                **(details or {}),
            },
        )
        self.db.add(audit)
        await self.db.flush()
        await self.db.refresh(audit, attribute_names=["actor_agent"])
        return audit

    async def get_audit_log(
        self, limit: int = 50, agent_name: str = None
    ) -> List[AuditLog]:
        stmt = (
            select(AuditLog)
            .options(selectinload(AuditLog.actor_agent))
            .order_by(AuditLog.created_at.desc())
        )
        if agent_name:
            agent = await get_agent_by_code(self.db, agent_name)
            if not agent:
                return []
            stmt = stmt.where(AuditLog.actor_agent_id == agent.id)
        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_policy(
        self,
        name: str,
        category: str,
        action: PolicyAction = PolicyAction.CONFIRM,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        description: str = None,
        conditions: Dict[str, Any] = None,
        applies_to_agents: List[str] = None,
    ) -> ObjectPolicy:
        user, tenant = await ensure_default_context(self.db)
        obj = await create_object_record(
            self.db,
            tenant_id=tenant.id,
            object_type="policy",
            title=name,
            summary=description,
            owner_user_id=user.id,
        )
        policy = ObjectPolicy(
            object_id=obj.id,
            category=category,
            action=action,
            risk_level=risk_level,
            conditions=conditions or {},
            applies_to_agents=applies_to_agents or [],
        )
        self.db.add(policy)
        await self.db.flush()
        await self.db.refresh(policy, attribute_names=["object"])
        return policy

    async def get_policies(self, category: str = None) -> List[ObjectPolicy]:
        stmt = (
            select(ObjectPolicy)
            .join(ObjectRecord, ObjectPolicy.object_id == ObjectRecord.id)
            .options(selectinload(ObjectPolicy.object))
            .where(
                ObjectPolicy.is_active.is_(True),
                ObjectRecord.status == ObjectStatus.ACTIVE,
            )
        )
        if category:
            stmt = stmt.where(ObjectPolicy.category == category)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


def audit_time():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)

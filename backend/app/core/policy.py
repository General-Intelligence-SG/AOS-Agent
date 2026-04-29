"""AOS 策略标准层 — 安全门控与权限控制"""
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    Policy, PolicyAction, RiskLevel, ObjectStatus,
    AuditRecord,
)


# 默认高风险动作列表
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
    """策略门控服务

    所有 Agent 动作在执行前必须通过策略检查。
    高风险动作自动要求用户确认。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check(
        self,
        action: str,
        agent_name: str,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """检查动作是否被允许

        Returns:
            {
                "allowed": bool,
                "action": PolicyAction,
                "reason": str,
                "requires_confirmation": bool,
                "risk_level": RiskLevel,
                "policy_id": str | None,
            }
        """
        context = context or {}

        # 1. 先查自定义策略
        stmt = select(Policy).where(
            Policy.is_active == True,
            Policy.status == ObjectStatus.ACTIVE,
        )
        result = await self.db.execute(stmt)
        policies = list(result.scalars().all())

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

        # 2. 回退到内置高风险动作表
        if action in HIGH_RISK_ACTIONS:
            risk = HIGH_RISK_ACTIONS[action]
            return {
                "allowed": True,
                "action": PolicyAction.CONFIRM,
                "reason": f"内置安全策略: {action} 是 {risk.value} 风险级别操作",
                "requires_confirmation": True,
                "risk_level": risk,
                "policy_id": None,
            }

        # 3. 默认允许
        return {
            "allowed": True,
            "action": PolicyAction.ALLOW,
            "reason": "默认允许",
            "requires_confirmation": False,
            "risk_level": RiskLevel.LOW,
            "policy_id": None,
        }

    def _matches(
        self,
        policy: Policy,
        action: str,
        agent_name: str,
        context: Dict,
    ) -> bool:
        """判断策略是否匹配当前动作"""
        conditions = policy.conditions or {}

        # 动作匹配
        if "actions" in conditions:
            if action not in conditions["actions"]:
                return False

        # Agent 匹配
        if policy.applies_to_agents:
            if agent_name not in policy.applies_to_agents:
                return False

        # 上下文条件匹配
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
        details: Dict = None,
        risk_level: RiskLevel = RiskLevel.LOW,
        user_confirmed: bool = False,
        session_id: str = None,
    ) -> AuditRecord:
        """记录审计日志"""
        record = AuditRecord(
            action=action,
            agent_name=agent_name,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            risk_level=risk_level,
            user_confirmed=user_confirmed,
            session_id=session_id,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_audit_log(
        self, limit: int = 50, agent_name: str = None
    ) -> List[AuditRecord]:
        """查询审计日志"""
        stmt = select(AuditRecord).order_by(
            AuditRecord.created_at.desc()
        )
        if agent_name:
            stmt = stmt.where(AuditRecord.agent_name == agent_name)
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
        conditions: Dict = None,
        applies_to_agents: List[str] = None,
    ) -> Policy:
        """创建策略规则"""
        policy = Policy(
            name=name,
            category=category,
            action=action,
            risk_level=risk_level,
            description=description,
            conditions=conditions or {},
            applies_to_agents=applies_to_agents or [],
        )
        self.db.add(policy)
        await self.db.flush()
        return policy

    async def get_policies(
        self, category: str = None
    ) -> List[Policy]:
        """查询策略"""
        stmt = select(Policy).where(
            Policy.is_active == True,
            Policy.status == ObjectStatus.ACTIVE,
        )
        if category:
            stmt = stmt.where(Policy.category == category)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

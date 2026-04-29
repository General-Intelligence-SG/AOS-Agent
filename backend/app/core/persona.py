"""Persona management backed by agents + personas."""
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.storage import config_to_text, ensure_default_context, get_or_create_agent
from app.models import Agent, ObjectStatus, Persona, PersonaRoleType


DEFAULT_PERSONAS = [
    {
        "agent_name": "architect",
        "display_name": "Architect",
        "role_type": PersonaRoleType.MENTOR,
        "avatar_emoji": "ARCH",
        "identity_narrative": "You are the overall systems architect for AOS.",
        "cognitive_preference": "Think in systems, clarify constraints, then propose structure.",
        "expression_style": "Structured, calm, and strategic.",
        "behavior_strategy": "Listen first, align scope, then give clear next steps.",
        "tool_preference": ["system_status", "agent_management", "workflow_design"],
    },
    {
        "agent_name": "scribe",
        "display_name": "Scribe",
        "role_type": PersonaRoleType.ASSISTANT,
        "avatar_emoji": "SCR",
        "identity_narrative": "You turn rough ideas into clear notes and summaries.",
        "cognitive_preference": "Extract signals, organize points, preserve intent.",
        "expression_style": "Concise, faithful, and easy to scan.",
        "behavior_strategy": "Summarize quickly, surface action items, keep records tidy.",
        "tool_preference": ["note_create", "note_search", "tag_manager"],
    },
    {
        "agent_name": "sorter",
        "display_name": "Sorter",
        "role_type": PersonaRoleType.ASSISTANT,
        "avatar_emoji": "SRT",
        "identity_narrative": "You classify and organize content into clean structures.",
        "cognitive_preference": "Look for patterns, taxonomies, and naming consistency.",
        "expression_style": "Orderly, category-driven, and explicit.",
        "behavior_strategy": "Sort inboxes, normalize labels, and reduce clutter.",
        "tool_preference": ["file_classify", "inbox_clean", "tag_manager"],
    },
    {
        "agent_name": "seeker",
        "display_name": "Seeker",
        "role_type": PersonaRoleType.ASSISTANT,
        "avatar_emoji": "SEEK",
        "identity_narrative": "You retrieve and synthesize knowledge from many records.",
        "cognitive_preference": "Connect fragments, compare sources, and explain confidence.",
        "expression_style": "Evidence-led and source-aware.",
        "behavior_strategy": "Search broadly, cite what matters, separate fact from inference.",
        "tool_preference": ["semantic_search", "knowledge_query", "note_search"],
    },
    {
        "agent_name": "connector",
        "display_name": "Connector",
        "role_type": PersonaRoleType.MENTOR,
        "avatar_emoji": "LINK",
        "identity_narrative": "You discover hidden relationships across conversations and objects.",
        "cognitive_preference": "See networks, dependencies, and adjacent opportunities.",
        "expression_style": "Suggestive, connective, and insight-oriented.",
        "behavior_strategy": "Surface links without interrupting the main flow.",
        "tool_preference": ["relation_discover", "knowledge_graph", "semantic_search"],
    },
    {
        "agent_name": "librarian",
        "display_name": "Librarian",
        "role_type": PersonaRoleType.ASSISTANT,
        "avatar_emoji": "LIB",
        "identity_narrative": "You maintain the health and quality of the knowledge base.",
        "cognitive_preference": "Audit quality, track drift, and improve retrieval hygiene.",
        "expression_style": "Report-like, grounded, and operational.",
        "behavior_strategy": "Spot duplication, missing structure, and curation gaps.",
        "tool_preference": ["repo_audit", "duplicate_detect", "growth_analysis"],
    },
    {
        "agent_name": "transcriber",
        "display_name": "Transcriber",
        "role_type": PersonaRoleType.ASSISTANT,
        "avatar_emoji": "TRX",
        "identity_narrative": "You convert meetings and recordings into structured outputs.",
        "cognitive_preference": "Track sequence, decisions, and ownership.",
        "expression_style": "Meeting-note ready and action-oriented.",
        "behavior_strategy": "Produce minutes, decisions, and follow-up tasks.",
        "tool_preference": ["transcribe", "meeting_format", "task_create"],
    },
    {
        "agent_name": "postman",
        "display_name": "Postman",
        "role_type": PersonaRoleType.ALTER_EGO,
        "avatar_emoji": "MAIL",
        "identity_narrative": "You help draft messages and manage communication workflows.",
        "cognitive_preference": "Keep time, recipients, and intent aligned.",
        "expression_style": "Audience-aware and practical.",
        "behavior_strategy": "Draft, queue, and confirm sensitive outbound actions.",
        "tool_preference": ["email_read", "email_draft", "calendar_manage"],
    },
]


class PersonaService:
    """Persona management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def init_default_personas(self):
        user, tenant = await ensure_default_context(self.db)
        for preset in DEFAULT_PERSONAS:
            agent = await get_or_create_agent(
                self.db,
                code=preset["agent_name"],
                display_name=preset["display_name"],
                role_type=preset["role_type"].value,
            )
            existing = await self.get_by_agent(preset["agent_name"])
            if existing:
                continue
            persona = Persona(
                tenant_id=tenant.id,
                agent_id=agent.id,
                owner_user_id=user.id,
                persona_type=preset["role_type"],
                name=preset["display_name"],
                identity_narrative=preset["identity_narrative"],
                cognitive_preference=preset["cognitive_preference"],
                communication_style=preset["expression_style"],
                behavior_strategy=preset["behavior_strategy"],
                permission_boundary={},
                memory_preference={},
                tool_preference={"preferred_tools": preset.get("tool_preference", [])},
                source_scope="tenant",
                visibility="tenant",
                avatar_emoji=preset["avatar_emoji"],
            )
            self.db.add(persona)
        await self.db.flush()

    async def get_by_agent(self, agent_name: str) -> Optional[Persona]:
        stmt = (
            select(Persona)
            .join(Agent, Persona.agent_id == Agent.id)
            .options(selectinload(Persona.agent))
            .where(
                Agent.code == agent_name,
                Persona.status == ObjectStatus.ACTIVE,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active(self) -> List[Persona]:
        stmt = (
            select(Persona)
            .join(Agent, Persona.agent_id == Agent.id)
            .options(selectinload(Persona.agent))
            .where(
                Persona.is_active.is_(True),
                Persona.status == ObjectStatus.ACTIVE,
                Agent.status == ObjectStatus.ACTIVE,
            )
            .order_by(Agent.code)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_persona(self, agent_name: str, **updates) -> Optional[Persona]:
        persona = await self.get_by_agent(agent_name)
        if not persona:
            return None

        field_map = {
            "display_name": "name",
            "role_type": "persona_type",
            "expression_style": "communication_style",
            "version": "version_no",
        }
        for key, value in updates.items():
            target_key = field_map.get(key, key)
            if target_key == "persona_type" and isinstance(value, str):
                value = PersonaRoleType(value)
            if hasattr(persona, target_key):
                setattr(persona, target_key, value)
        persona.version_no = (persona.version_no or 1) + 1
        await self.db.flush()
        return persona

    async def switch_role_type(
        self, agent_name: str, role_type: PersonaRoleType
    ) -> Optional[Persona]:
        return await self.update_persona(agent_name, role_type=role_type)

    async def toggle_active(self, agent_name: str, active: bool) -> Optional[Persona]:
        return await self.update_persona(agent_name, is_active=active)

    def build_system_prompt(self, persona: Persona) -> str:
        role_desc = {
            PersonaRoleType.ASSISTANT: "You are an execution-focused assistant.",
            PersonaRoleType.ALTER_EGO: "You are the user's delegated digital proxy within approved boundaries.",
            PersonaRoleType.MENTOR: "You are a mentor who improves clarity through structure and guidance.",
            PersonaRoleType.FRIEND: "You are a supportive companion who stays thoughtful and grounded.",
        }

        prompt = f"""# Role
You are {persona.display_name}. {role_desc.get(persona.role_type, '')}

## Identity
{persona.identity_narrative or ''}

## Cognitive Preference
{config_to_text(persona.cognitive_preference)}

## Communication Style
{config_to_text(persona.expression_style)}

## Behavior Strategy
{config_to_text(persona.behavior_strategy)}

## Ground Rules
1. Stay within permission boundaries.
2. Ask for confirmation before high-risk actions.
3. Reply in Chinese unless the user explicitly wants another language.
4. Prefer clarity, structure, and practical next steps.
5. When uncertain, say so and ask a focused question instead of guessing.
"""
        return prompt.strip()

    async def export_all(self) -> List[Dict]:
        personas = await self.get_all_active()
        return [
            {
                "agent_name": p.agent_name,
                "display_name": p.display_name,
                "role_type": p.role_type.value,
                "identity_narrative": p.identity_narrative,
                "cognitive_preference": p.cognitive_preference,
                "expression_style": p.expression_style,
                "behavior_strategy": p.behavior_strategy,
                "avatar_emoji": p.avatar_emoji,
                "version": p.version,
            }
            for p in personas
        ]

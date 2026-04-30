"""MCP server exposing AOS REST APIs as tools."""
import json
import logging
import sys
from typing import Any, Optional

import httpx
from fastmcp import FastMCP


logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("aos.mcp")

mcp = FastMCP("AOS", version="0.2.0")

_AOS_BASE_URL = "http://localhost:8001"


def _split_csv(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _compact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _compact(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [_compact(item) for item in value]
    return value


async def _call_api(
    method: str,
    path: str,
    body: Optional[dict[str, Any]] = None,
    params: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    url = f"{_AOS_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if method == "GET":
                response = await client.get(url, params=_compact(params or {}))
            elif method == "POST":
                response = await client.post(url, json=_compact(body or {}))
            elif method == "PUT":
                response = await client.put(url, json=_compact(body or {}))
            elif method == "DELETE":
                response = await client.delete(url)
            else:
                return {"error": f"Unsupported method: {method}"}

        try:
            payload = response.json()
        except ValueError:
            payload = {"text": response.text}

        if response.status_code >= 400:
            if isinstance(payload, dict):
                payload.setdefault("status", response.status_code)
                return payload
            return {"error": response.text, "status": response.status_code}
        return payload
    except httpx.ConnectError:
        return {
            "error": "AOS backend is not running.",
            "hint": "Start the FastAPI service on http://localhost:8001 first.",
        }
    except Exception as exc:
        return {"error": str(exc)}


def _dump(result: Any) -> str:
    return json.dumps(result, ensure_ascii=False)


@mcp.tool
async def aos_chat(
    message: str,
    agent_name: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    result = await _call_api(
        "POST",
        "/api/chat",
        {
            "message": message,
            "agent_name": agent_name,
            "session_id": session_id,
        },
    )
    return _dump(result)


@mcp.tool
async def aos_list_agents() -> str:
    return _dump(await _call_api("GET", "/api/agents"))


@mcp.tool
async def aos_switch_agent(agent_name: str, session_id: Optional[str] = None) -> str:
    result = await _call_api(
        "POST",
        "/api/agents/switch",
        {"agent_name": agent_name, "session_id": session_id},
    )
    return _dump(result)


@mcp.tool
async def aos_create_knowledge(
    title: str,
    content: str,
    category: Optional[str] = None,
    project: Optional[str] = None,
    tags: Optional[str] = None,
) -> str:
    result = await _call_api(
        "POST",
        "/api/knowledge",
        {
            "title": title,
            "content": content,
            "category": category,
            "project": project,
            "tags": _split_csv(tags),
            "is_knowledge": True,
        },
    )
    return _dump(result)


@mcp.tool
async def aos_search_knowledge(
    category: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 20,
) -> str:
    return _dump(
        await _call_api(
            "GET",
            "/api/knowledge",
            params={"category": category, "project": project, "limit": limit},
        )
    )


@mcp.tool
async def aos_get_knowledge(doc_id: str) -> str:
    return _dump(await _call_api("GET", f"/api/knowledge/{doc_id}"))


@mcp.tool
async def aos_create_task(
    title: str,
    description: Optional[str] = None,
    priority: str = "medium",
    project: Optional[str] = None,
    tags: Optional[str] = None,
) -> str:
    result = await _call_api(
        "POST",
        "/api/tasks",
        {
            "title": title,
            "description": description,
            "priority": priority,
            "project": project,
            "tags": _split_csv(tags),
        },
    )
    return _dump(result)


@mcp.tool
async def aos_list_tasks(
    status: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 30,
) -> str:
    return _dump(
        await _call_api(
            "GET",
            "/api/tasks",
            params={"status": status, "project": project, "limit": limit},
        )
    )


@mcp.tool
async def aos_update_task(
    task_id: str,
    title: Optional[str] = None,
    task_status: Optional[str] = None,
    priority: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    result = await _call_api(
        "PUT",
        f"/api/tasks/{task_id}",
        {
            "title": title,
            "task_status": task_status,
            "priority": priority,
            "description": description,
        },
    )
    return _dump(result)


@mcp.tool
async def aos_store_memory(
    content: str,
    layer: str = "long_term",
    tags: Optional[str] = None,
    importance: float = 0.5,
) -> str:
    result = await _call_api(
        "POST",
        "/api/memory",
        {
            "content": content,
            "layer": layer,
            "tags": _split_csv(tags),
            "importance": importance,
        },
    )
    return _dump(result)


@mcp.tool
async def aos_recall_memory(layer: Optional[str] = None, limit: int = 10) -> str:
    return _dump(
        await _call_api(
            "GET",
            "/api/memory",
            params={"layer": layer, "limit": limit},
        )
    )


@mcp.tool
async def aos_create_object(
    object_type: str,
    title: str,
    summary: Optional[str] = None,
    lifecycle_stage: Optional[str] = None,
    visibility: str = "tenant",
    importance: float = 0.5,
    confidence: float = 1.0,
    occurred_at: Optional[str] = None,
    due_at: Optional[str] = None,
    primary_agent_name: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    document: Optional[dict[str, Any]] = None,
    work_item: Optional[dict[str, Any]] = None,
    meeting: Optional[dict[str, Any]] = None,
    memory: Optional[dict[str, Any]] = None,
    contact: Optional[dict[str, Any]] = None,
    project: Optional[dict[str, Any]] = None,
) -> str:
    result = await _call_api(
        "POST",
        "/api/objects",
        {
            "object_type": object_type,
            "title": title,
            "summary": summary,
            "lifecycle_stage": lifecycle_stage,
            "visibility": visibility,
            "importance": importance,
            "confidence": confidence,
            "occurred_at": occurred_at,
            "due_at": due_at,
            "primary_agent_name": primary_agent_name,
            "metadata": metadata or {},
            "document": document,
            "work_item": work_item,
            "meeting": meeting,
            "memory": memory,
            "contact": contact,
            "project": project,
        },
    )
    return _dump(result)


@mcp.tool
async def aos_list_objects(
    object_type: Optional[str] = None,
    lifecycle_stage: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 50,
) -> str:
    return _dump(
        await _call_api(
            "GET",
            "/api/objects",
            params={
                "object_type": object_type,
                "lifecycle_stage": lifecycle_stage,
                "keyword": keyword,
                "limit": limit,
            },
        )
    )


@mcp.tool
async def aos_get_object(object_id: str) -> str:
    return _dump(await _call_api("GET", f"/api/objects/{object_id}"))


@mcp.tool
async def aos_update_object(
    object_id: str,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    lifecycle_stage: Optional[str] = None,
    visibility: Optional[str] = None,
    importance: Optional[float] = None,
    confidence: Optional[float] = None,
    occurred_at: Optional[str] = None,
    due_at: Optional[str] = None,
    primary_agent_name: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    document: Optional[dict[str, Any]] = None,
    work_item: Optional[dict[str, Any]] = None,
    meeting: Optional[dict[str, Any]] = None,
    memory: Optional[dict[str, Any]] = None,
    contact: Optional[dict[str, Any]] = None,
    project: Optional[dict[str, Any]] = None,
) -> str:
    result = await _call_api(
        "PUT",
        f"/api/objects/{object_id}",
        {
            "title": title,
            "summary": summary,
            "lifecycle_stage": lifecycle_stage,
            "visibility": visibility,
            "importance": importance,
            "confidence": confidence,
            "occurred_at": occurred_at,
            "due_at": due_at,
            "primary_agent_name": primary_agent_name,
            "metadata": metadata,
            "document": document,
            "work_item": work_item,
            "meeting": meeting,
            "memory": memory,
            "contact": contact,
            "project": project,
        },
    )
    return _dump(result)


@mcp.tool
async def aos_link_objects(
    object_id: str,
    to_object_id: str,
    link_type: str,
    link_role: Optional[str] = None,
    sort_order: Optional[int] = None,
    weight: Optional[float] = None,
    provenance: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    result = await _call_api(
        "POST",
        f"/api/objects/{object_id}/links",
        {
            "to_object_id": to_object_id,
            "link_type": link_type,
            "link_role": link_role,
            "sort_order": sort_order,
            "weight": weight,
            "provenance": provenance,
            "metadata": metadata or {},
        },
    )
    return _dump(result)


@mcp.tool
async def aos_list_object_links(
    object_id: str,
    link_type: Optional[str] = None,
) -> str:
    return _dump(
        await _call_api(
            "GET",
            f"/api/objects/{object_id}/links",
            params={"link_type": link_type},
        )
    )


@mcp.tool
async def aos_add_object_evidence(
    object_id: str,
    evidence_type: str,
    source_system_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    message_id: Optional[str] = None,
    file_id: Optional[str] = None,
    snippet_text: Optional[str] = None,
    locator: Optional[dict[str, Any]] = None,
    checksum: Optional[str] = None,
    confidence: Optional[float] = None,
) -> str:
    result = await _call_api(
        "POST",
        f"/api/objects/{object_id}/evidences",
        {
            "evidence_type": evidence_type,
            "source_system_id": source_system_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "file_id": file_id,
            "snippet_text": snippet_text,
            "locator": locator or {},
            "checksum": checksum,
            "confidence": confidence,
        },
    )
    return _dump(result)


@mcp.tool
async def aos_list_object_evidences(
    object_id: str,
    evidence_type: Optional[str] = None,
) -> str:
    return _dump(
        await _call_api(
            "GET",
            f"/api/objects/{object_id}/evidences",
            params={"evidence_type": evidence_type},
        )
    )


@mcp.tool
async def aos_export_data(
    include_memories: bool = True,
    include_documents: bool = True,
    include_tasks: bool = True,
    include_personas: bool = True,
    include_objects: bool = True,
) -> str:
    result = await _call_api(
        "POST",
        "/api/data/export",
        {
            "include_memories": include_memories,
            "include_documents": include_documents,
            "include_tasks": include_tasks,
            "include_personas": include_personas,
            "include_objects": include_objects,
        },
    )
    return _dump(result)


@mcp.tool
async def aos_system_status() -> str:
    return _dump(await _call_api("GET", "/api/system"))


@mcp.tool
async def aos_health_check() -> str:
    return _dump(await _call_api("GET", "/health"))


@mcp.tool
async def aos_list_sessions(limit: int = 10) -> str:
    return _dump(await _call_api("GET", "/api/chat/sessions", params={"limit": limit}))


@mcp.tool
async def aos_get_session_messages(session_id: str) -> str:
    return _dump(await _call_api("GET", f"/api/chat/sessions/{session_id}/messages"))


@mcp.resource("aos://system/status")
async def resource_system_status() -> str:
    result = await _call_api("GET", "/api/system")
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.resource("aos://agents/list")
async def resource_agents_list() -> str:
    result = await _call_api("GET", "/api/agents")
    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    logger.info("Starting AOS MCP server in stdio mode")
    mcp.run()

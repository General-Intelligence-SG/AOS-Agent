"""AOS MCP Server — 将 AOS 能力暴露为 OpenClaw 标准 MCP 工具

OpenClaw 通过 MCP (Model Context Protocol) 与外部技能通信。
本模块将 AOS 的全部核心能力注册为 MCP Tools，使 OpenClaw Agent
可以通过标准的 tools/list、tools/call JSON-RPC 接口调用 AOS。

启动方式 (stdio)：
    python -m app.mcp_server

OpenClaw 配置 (openclaw.json)：
    {
      "mcpServers": {
        "aos": {
          "command": "python",
          "args": ["-m", "app.mcp_server"],
          "cwd": "<aos-poc>/backend"
        }
      }
    }
"""
import sys
import json
import asyncio
import logging
from typing import Optional

from fastmcp import FastMCP

# 在 stdio 模式下只能用 stderr 记日志
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("aos.mcp")

# ────────────────────────────────────────────
#  创建 MCP Server 实例
# ────────────────────────────────────────────
mcp = FastMCP(
    "AOS 奥思虚拟助理",
    version="0.1.0",
    description="企业级虚拟助理 — 知识管理、事务整理、多 Agent 协作、记忆系统",
)


# ════════════════════════════════════════════
#  工具分组 1：对话 & Agent 路由
# ════════════════════════════════════════════

@mcp.tool
async def aos_chat(
    message: str,
    agent_name: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """向 AOS 虚拟助理发送消息并获取回复。

    AOS 会自动路由到合适的 Agent（Architect/Scribe/Sorter/Seeker/
    Connector/Librarian/Transcriber/Postman），也可指定 agent_name。

    Args:
        message: 用户消息内容
        agent_name: 可选，指定目标 Agent（architect/scribe/sorter/seeker/
                    connector/librarian/transcriber/postman）
        session_id: 可选，续接已有会话
    """
    result = await _call_api("POST", "/api/chat", {
        "message": message,
        "agent_name": agent_name,
        "session_id": session_id,
    })
    return json.dumps(result, ensure_ascii=False)


@mcp.tool
async def aos_list_agents() -> str:
    """列出 AOS 中所有可用的 Agent 及其角色类型。

    返回包含 name、display_name、role_type、avatar_emoji、description 的列表。
    """
    result = await _call_api("GET", "/api/agents")
    return json.dumps(result, ensure_ascii=False)


@mcp.tool
async def aos_switch_agent(
    agent_name: str,
    session_id: Optional[str] = None,
) -> str:
    """切换当前活跃的 AOS Agent。

    Args:
        agent_name: 目标 Agent 名称
        session_id: 可选，绑定到特定会话
    """
    result = await _call_api("POST", "/api/agents/switch", {
        "agent_name": agent_name,
        "session_id": session_id,
    })
    return json.dumps(result, ensure_ascii=False)


# ════════════════════════════════════════════
#  工具分组 2：知识库管理
# ════════════════════════════════════════════

@mcp.tool
async def aos_create_knowledge(
    title: str,
    content: str,
    category: Optional[str] = None,
    tags: Optional[str] = None,
) -> str:
    """在 AOS 知识库中创建新条目。

    Args:
        title: 条目标题
        content: 内容（支持 Markdown）
        category: 分类（如"工作"、"学习"、"项目名"）
        tags: 逗号分隔的标签（如"AI,产品,重要"）
    """
    result = await _call_api("POST", "/api/knowledge", {
        "title": title,
        "content": content,
        "category": category,
        "tags": [t.strip() for t in tags.split(",")] if tags else [],
        "is_knowledge": True,
    })
    return json.dumps(result, ensure_ascii=False)


@mcp.tool
async def aos_search_knowledge(
    category: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 20,
) -> str:
    """检索 AOS 知识库中的文档。

    Args:
        category: 按分类过滤
        project: 按项目过滤
        limit: 返回条目数上限
    """
    params = {"limit": limit}
    if category:
        params["category"] = category
    if project:
        params["project"] = project
    result = await _call_api("GET", "/api/knowledge", params=params)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool
async def aos_get_knowledge(doc_id: str) -> str:
    """获取 AOS 知识库中指定文档的完整内容。

    Args:
        doc_id: 文档 ID
    """
    result = await _call_api("GET", f"/api/knowledge/{doc_id}")
    return json.dumps(result, ensure_ascii=False)


# ════════════════════════════════════════════
#  工具分组 3：任务管理
# ════════════════════════════════════════════

@mcp.tool
async def aos_create_task(
    title: str,
    description: Optional[str] = None,
    priority: str = "medium",
    project: Optional[str] = None,
    tags: Optional[str] = None,
) -> str:
    """在 AOS 中创建新任务。

    Args:
        title: 任务标题
        description: 详细描述
        priority: 优先级（urgent/high/medium/low）
        project: 所属项目
        tags: 逗号分隔的标签
    """
    result = await _call_api("POST", "/api/tasks", {
        "title": title,
        "description": description,
        "priority": priority,
        "project": project,
        "tags": [t.strip() for t in tags.split(",")] if tags else [],
    })
    return json.dumps(result, ensure_ascii=False)


@mcp.tool
async def aos_list_tasks(
    status: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 30,
) -> str:
    """列出 AOS 中的任务。

    Args:
        status: 按状态过滤（todo/in_progress/waiting/done/cancelled）
        project: 按项目过滤
        limit: 返回上限
    """
    params = {"limit": limit}
    if status:
        params["status"] = status
    if project:
        params["project"] = project
    result = await _call_api("GET", "/api/tasks", params=params)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool
async def aos_update_task(
    task_id: str,
    title: Optional[str] = None,
    task_status: Optional[str] = None,
    priority: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """更新 AOS 中的任务状态或内容。

    Args:
        task_id: 任务 ID
        title: 新标题
        task_status: 新状态（todo/in_progress/waiting/done/cancelled）
        priority: 新优先级
        description: 新描述
    """
    body = {}
    if title is not None:
        body["title"] = title
    if task_status is not None:
        body["task_status"] = task_status
    if priority is not None:
        body["priority"] = priority
    if description is not None:
        body["description"] = description
    result = await _call_api("PUT", f"/api/tasks/{task_id}", body)
    return json.dumps(result, ensure_ascii=False)


# ════════════════════════════════════════════
#  工具分组 4：记忆系统
# ════════════════════════════════════════════

@mcp.tool
async def aos_store_memory(
    content: str,
    layer: str = "long_term",
    tags: Optional[str] = None,
    importance: float = 0.5,
) -> str:
    """向 AOS 记忆系统存入一条记忆。

    AOS 采用 6 层分层记忆模型：short_term / long_term / episodic /
    procedural / profile / policy。

    Args:
        content: 记忆内容
        layer: 记忆层级
        tags: 逗号分隔的标签
        importance: 重要度（0.0-1.0）
    """
    result = await _call_api("POST", "/api/memory", {
        "content": content,
        "layer": layer,
        "tags": [t.strip() for t in tags.split(",")] if tags else [],
        "importance": importance,
    })
    return json.dumps(result, ensure_ascii=False)


@mcp.tool
async def aos_recall_memory(
    layer: Optional[str] = None,
    limit: int = 10,
) -> str:
    """从 AOS 记忆系统检索记忆。

    Args:
        layer: 按层级过滤（short_term/long_term/episodic/procedural/profile/policy）
        limit: 返回上限
    """
    params = {"limit": limit}
    if layer:
        params["layer"] = layer
    result = await _call_api("GET", "/api/memory", params=params)
    return json.dumps(result, ensure_ascii=False)


# ════════════════════════════════════════════
#  工具分组 5：数据导入导出
# ════════════════════════════════════════════

@mcp.tool
async def aos_export_data(
    include_memories: bool = True,
    include_documents: bool = True,
    include_tasks: bool = True,
    include_personas: bool = True,
) -> str:
    """导出 AOS 全量数据为 JSON 文件。

    Args:
        include_memories: 包含记忆数据
        include_documents: 包含文档数据
        include_tasks: 包含任务数据
        include_personas: 包含人格设定
    """
    result = await _call_api("POST", "/api/data/export", {
        "include_memories": include_memories,
        "include_documents": include_documents,
        "include_tasks": include_tasks,
        "include_personas": include_personas,
    })
    return json.dumps(result, ensure_ascii=False)


# ════════════════════════════════════════════
#  工具分组 6：系统管理
# ════════════════════════════════════════════

@mcp.tool
async def aos_system_status() -> str:
    """获取 AOS 系统状态信息，包括版本、已注册 Agent、LLM 配置等。"""
    result = await _call_api("GET", "/api/system")
    return json.dumps(result, ensure_ascii=False)


@mcp.tool
async def aos_health_check() -> str:
    """检查 AOS 后端服务是否正常运行。"""
    result = await _call_api("GET", "/health")
    return json.dumps(result, ensure_ascii=False)


@mcp.tool
async def aos_list_sessions(limit: int = 10) -> str:
    """列出 AOS 最近的对话会话。

    Args:
        limit: 返回上限
    """
    result = await _call_api("GET", "/api/chat/sessions", params={"limit": limit})
    return json.dumps(result, ensure_ascii=False)


@mcp.tool
async def aos_get_session_messages(session_id: str) -> str:
    """获取指定会话的完整消息历史。

    Args:
        session_id: 会话 ID
    """
    result = await _call_api("GET", f"/api/chat/sessions/{session_id}/messages")
    return json.dumps(result, ensure_ascii=False)


# ════════════════════════════════════════════
#  MCP Resources — 暴露上下文数据给 OpenClaw
# ════════════════════════════════════════════

@mcp.resource("aos://system/status")
async def resource_system_status() -> str:
    """AOS 系统当前状态概要"""
    result = await _call_api("GET", "/api/system")
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.resource("aos://agents/list")
async def resource_agents_list() -> str:
    """AOS 可用 Agent 列表及其职责说明"""
    result = await _call_api("GET", "/api/agents")
    return json.dumps(result, ensure_ascii=False, indent=2)


# ════════════════════════════════════════════
#  内部 HTTP 客户端 — 与 AOS FastAPI 后端通信
# ════════════════════════════════════════════

import httpx

_AOS_BASE_URL = "http://localhost:8000"


async def _call_api(
    method: str,
    path: str,
    body: dict = None,
    params: dict = None,
) -> dict:
    """调用 AOS 后端 REST API"""
    url = f"{_AOS_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if method == "GET":
                resp = await client.get(url, params=params)
            elif method == "POST":
                resp = await client.post(url, json=body)
            elif method == "PUT":
                resp = await client.put(url, json=body)
            elif method == "DELETE":
                resp = await client.delete(url)
            else:
                return {"error": f"Unsupported method: {method}"}

            if resp.status_code >= 400:
                return {"error": resp.text, "status": resp.status_code}
            return resp.json()
    except httpx.ConnectError:
        return {
            "error": "AOS 后端服务未运行。请先执行 start.bat/.sh 启动服务。",
            "hint": "确保 FastAPI 在 localhost:8000 运行",
        }
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════
#  入口
# ════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("AOS MCP Server 启动 (stdio 模式)")
    mcp.run()

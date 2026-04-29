"""AOS OpenClaw 适配器 — AOS 作为 MCP Client 调用 OpenClaw 的内置工具

当 AOS 运行在 OpenClaw 环境中时，AOS Agent 可以通过 MCP 协议
调用 OpenClaw 已安装的其他技能（如文件系统、浏览器、Git 等）。

两种集成模式:
  1. AOS 作为 MCP Server (mcp_server.py) — OpenClaw 调用 AOS 工具
  2. AOS 作为 MCP Client (本文件)    — AOS 调用 OpenClaw 工具

本模块实现模式 2，让 AOS Agent 能"借用" OpenClaw 的工具能力。
"""
import json
import asyncio
import subprocess
import sys
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger("aos.openclaw")


class OpenClawBridge:
    """OpenClaw 桥接层

    通过 OpenClaw CLI 或 WebSocket 控制平面与 Gateway 通信，
    让 AOS Agent 能使用 OpenClaw 已安装的工具。

    通信方式优先级:
    1. WebSocket 控制平面 (ws://localhost:18789) — 生产模式
    2. CLI 命令 (`openclaw tool call`) — PoC 模式
    3. 直接 HTTP (localhost:8080) — 如果 OpenClaw Gateway 暴露了 REST
    """

    def __init__(self):
        self._ws_url = "ws://localhost:18789"
        self._available_tools: Dict[str, Dict] = {}
        self._openclaw_bin = self._find_openclaw()

    def _find_openclaw(self) -> Optional[str]:
        """查找 OpenClaw CLI 二进制"""
        import shutil
        for name in ["openclaw", "claw"]:
            path = shutil.which(name)
            if path:
                return path
        return None

    @property
    def is_available(self) -> bool:
        """OpenClaw 是否可用"""
        return self._openclaw_bin is not None

    # ──────── 工具发现 ────────

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """从 OpenClaw 获取可用工具列表 (tools/list)"""
        if not self.is_available:
            logger.warning("OpenClaw CLI 未找到，跳过工具发现")
            return []

        try:
            result = await self._run_cli(["tools", "list", "--json"])
            if result:
                tools = json.loads(result)
                self._available_tools = {t["name"]: t for t in tools}
                logger.info(f"从 OpenClaw 发现 {len(tools)} 个工具")
                return tools
        except Exception as e:
            logger.warning(f"OpenClaw 工具发现失败: {e}")

        return []

    # ──────── 工具调用 ────────

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """调用 OpenClaw 的工具 (tools/call)

        Args:
            tool_name: 工具名（如 "Read File", "Search Web" 等）
            arguments: 工具参数

        Returns:
            {"success": bool, "result": Any, "error": str | None}
        """
        if not self.is_available:
            return {
                "success": False,
                "result": None,
                "error": "OpenClaw 未安装或不在 PATH 中",
            }

        try:
            args_json = json.dumps(arguments or {}, ensure_ascii=False)
            result = await self._run_cli([
                "tool", "call", tool_name,
                "--args", args_json,
                "--json",
            ])
            if result:
                return {
                    "success": True,
                    "result": json.loads(result),
                    "error": None,
                }
            return {
                "success": True,
                "result": result,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "error": str(e),
            }

    # ──────── 与 OpenClaw 会话交互 ────────

    async def send_to_channel(
        self,
        message: str,
        channel: str = "default",
    ) -> Optional[str]:
        """通过 OpenClaw Gateway 向指定 Channel 发送消息

        这让 AOS 可以通过 OpenClaw 的消息通道（WhatsApp/Telegram/etc）
        向用户发送通知。
        """
        if not self.is_available:
            return None

        try:
            return await self._run_cli([
                "send", message,
                "--channel", channel,
                "--json",
            ])
        except Exception as e:
            logger.error(f"发送到 OpenClaw Channel 失败: {e}")
            return None

    async def read_workspace_file(self, filename: str) -> Optional[str]:
        """读取 OpenClaw 工作区文件 (SOUL.md / AGENTS.md / USER.md 等)"""
        if not self.is_available:
            return None

        try:
            return await self._run_cli(["workspace", "cat", filename])
        except Exception:
            return None

    async def update_memory_md(self, content: str) -> bool:
        """写入 OpenClaw 的 MEMORY.md（跨会话持久记忆）

        AOS 将关键记忆同步到 OpenClaw 的原生记忆文件，
        使得即使不通过 AOS 访问，OpenClaw Agent 也能看到这些信息。
        """
        if not self.is_available:
            return False

        try:
            await self._run_cli([
                "workspace", "append", "MEMORY.md",
                "--content", content,
            ])
            return True
        except Exception as e:
            logger.error(f"更新 MEMORY.md 失败: {e}")
            return False

    # ──────── 底层 CLI 执行器 ────────

    async def _run_cli(
        self,
        args: List[str],
        timeout: float = 30.0,
    ) -> Optional[str]:
        """异步执行 OpenClaw CLI 命令"""
        cmd = [self._openclaw_bin] + args
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            if proc.returncode != 0:
                err = stderr.decode().strip() if stderr else "Unknown error"
                raise RuntimeError(f"OpenClaw CLI 返回错误 ({proc.returncode}): {err}")
            return stdout.decode().strip() if stdout else ""
        except asyncio.TimeoutError:
            raise RuntimeError(f"OpenClaw CLI 超时 ({timeout}s)")


# ──────── 工具描述符（供 Agent 系统提示词使用） ────────

OPENCLAW_TOOL_DESCRIPTIONS = """
## OpenClaw 可用工具（通过 OpenClaw Gateway 调用）

当你需要执行以下操作时，可以请求系统通过 OpenClaw 调用对应工具：

- **文件操作**: 读取/写入本地文件、列出目录
- **浏览器**: 搜索网页、读取网页内容
- **Git**: 查看提交、管理仓库
- **通讯**: 通过 WhatsApp/Telegram/Slack 发送消息
- **日历**: 查看和创建日程事件
- **邮件**: 读取和发送邮件

使用方式：在回复中标注 `[TOOL_CALL: tool_name(arg1=val1, arg2=val2)]`，
系统会自动拦截并通过 OpenClaw 执行。
"""


# 全局实例
openclaw_bridge = OpenClawBridge()

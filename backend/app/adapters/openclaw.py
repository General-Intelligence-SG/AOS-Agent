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
import logging
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

logger = logging.getLogger("aos.openclaw")


class OpenClawBridge:
    """OpenClaw 桥接层

    通过 OpenClaw CLI 或本地工作区与 Gateway 通信，
    让 AOS Agent 能使用 OpenClaw 已安装的工具。

    当前兼容策略:
    1. 新版 OpenClaw CLI 已不再暴露旧版 `tool/tools/workspace/send` 命令。
    2. 因此动态工具发现/调用会在不兼容版本下优雅降级。
    3. 工作区文件读写改为直接访问 `~/.openclaw/workspace`。
    """

    def __init__(self):
        self._ws_url = "ws://localhost:18789"
        self._available_tools: Dict[str, Dict] = {}
        self._openclaw_bin = self._find_openclaw()
        self._supported_commands = self._discover_cli_commands()
        self._workspace_dir = Path.home() / ".openclaw" / "workspace"

    def _find_openclaw(self) -> Optional[str]:
        """查找 OpenClaw CLI 二进制"""
        import shutil

        for name in ["openclaw", "claw"]:
            path = shutil.which(name)
            if path:
                return path
        return None

    def _discover_cli_commands(self) -> Set[str]:
        """探测当前 OpenClaw CLI 暴露的顶层命令。"""
        if not self._openclaw_bin:
            return set()

        try:
            proc = subprocess.run(
                [self._openclaw_bin, "--help"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:
            return set()

        commands: Set[str] = set()
        in_commands = False
        for line in (proc.stdout or "").splitlines():
            stripped = line.strip()
            if stripped == "Commands:":
                in_commands = True
                continue
            if not in_commands:
                continue
            if stripped.startswith("Examples:") or stripped.startswith("Docs:"):
                break
            if not stripped or stripped.startswith("Hint:"):
                continue
            command = stripped.split()[0].rstrip("*")
            if command:
                commands.add(command)
        return commands

    def _supports_legacy_tool_cli(self) -> bool:
        """旧版 tool/tools CLI 是否可用。"""
        return any(cmd in self._supported_commands for cmd in ("tool", "tools"))

    @property
    def is_available(self) -> bool:
        """OpenClaw 是否可用"""
        return self._openclaw_bin is not None

    # ──────── 工具发现 ────────

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """从 OpenClaw 获取可用工具列表 (旧版 tools/list)。"""
        if not self.is_available:
            logger.warning("OpenClaw CLI 未找到，跳过工具发现")
            return []

        if not self._supports_legacy_tool_cli():
            logger.info(
                "OpenClaw CLI 存在，但当前版本未暴露旧版 tool/tools 命令；"
                "跳过动态工具发现，AOS 继续以降级模式运行"
            )
            return []

        last_error: Optional[Exception] = None
        for args in (["tools", "list", "--json"], ["tool", "list", "--json"]):
            try:
                result = await self._run_cli(args)
                if result:
                    tools = json.loads(result)
                    self._available_tools = {t["name"]: t for t in tools}
                    logger.info(f"从 OpenClaw 发现 {len(tools)} 个工具")
                    return tools
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            logger.warning(f"OpenClaw 工具发现失败: {last_error}")
        return []

    # ──────── 工具调用 ────────

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """调用 OpenClaw 的工具 (旧版 tools/call)。

        当前 OpenClaw 版本如果未暴露旧版 tool/tools 命令，则返回明确的
        不支持错误，避免抛出误导性的 CLI 异常。
        """
        if not self.is_available:
            return {
                "success": False,
                "result": None,
                "error": "OpenClaw 未安装或不在 PATH 中",
            }

        if not self._supports_legacy_tool_cli():
            return {
                "success": False,
                "result": None,
                "error": (
                    "当前 OpenClaw CLI 版本未暴露旧版 tool/tools 命令，"
                    "AOS 的动态外部工具调用已自动降级"
                ),
            }

        args_json = json.dumps(arguments or {}, ensure_ascii=False)
        last_error: Optional[Exception] = None
        for args in (
            ["tool", "call", tool_name, "--args", args_json, "--json"],
            ["tools", "call", tool_name, "--args", args_json, "--json"],
        ):
            try:
                result = await self._run_cli(args)
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
            except Exception as exc:
                last_error = exc

        return {
            "success": False,
            "result": None,
            "error": str(last_error) if last_error else "Unknown error",
        }

    # ──────── 与 OpenClaw 会话交互 ────────

    async def send_to_channel(
        self,
        message: str,
        channel: str = "default",
    ) -> Optional[str]:
        """通过 OpenClaw Gateway 向指定 Channel 发送消息。

        新版 OpenClaw 使用 `message send`，但要求显式 target，当前桥接层
        仅保留接口并在不兼容时返回 None。
        """
        if not self.is_available:
            return None

        if "message" not in self._supported_commands:
            logger.info("当前 OpenClaw CLI 不支持消息发送桥接命令")
            return None

        logger.info(
            "当前桥接层缺少 message send 所需的显式 target 信息，"
            f"跳过向 channel={channel} 发送消息"
        )
        return None

    async def read_workspace_file(self, filename: str) -> Optional[str]:
        """读取 OpenClaw 工作区文件 (SOUL.md / AGENTS.md / USER.md 等)。"""
        path = self._workspace_dir / filename
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
        except Exception:
            return None
        return None

    async def update_memory_md(self, content: str) -> bool:
        """写入 OpenClaw 的 MEMORY.md（跨会话持久记忆）。"""
        try:
            self._workspace_dir.mkdir(parents=True, exist_ok=True)
            path = self._workspace_dir / "MEMORY.md"
            prefix = "" if not path.exists() or path.stat().st_size == 0 else "\n"
            with path.open("a", encoding="utf-8") as f:
                f.write(prefix + content)
                if not content.endswith("\n"):
                    f.write("\n")
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
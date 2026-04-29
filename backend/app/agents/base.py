"""AOS LLM 适配器 + Agent 基类 + OpenClaw 工具集成"""
import json
import re
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from openai import AsyncOpenAI
from app.config import settings
from app.adapters.openclaw import openclaw_bridge, OPENCLAW_TOOL_DESCRIPTIONS

logger = logging.getLogger("aos.agent")


# ──────────────────────────── LLM 客户端 ────────────────────────────
class LLMClient:
    """统一的 LLM 调用客户端（OpenAI 兼容 API）"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY or "sk-placeholder",
            base_url=settings.LLM_BASE_URL,
        )
        self.model = settings.LLM_MODEL
        self.embedding_model = settings.LLM_EMBEDDING_MODEL

    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = None,
        max_tokens: int = None,
        json_mode: bool = False,
    ) -> str:
        """发送聊天请求"""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or settings.LLM_TEMPERATURE,
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = await self.client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except Exception as e:
            return f"[LLM 调用失败: {str(e)}]"

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = None,
        max_tokens: int = None,
    ) -> AsyncGenerator[str, None]:
        """流式聊天"""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or settings.LLM_TEMPERATURE,
                max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except Exception as e:
            yield f"[LLM 流式调用失败: {str(e)}]"

    async def embed(self, text: str) -> List[float]:
        """生成文本向量"""
        try:
            resp = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
            )
            return resp.data[0].embedding
        except Exception:
            # Fallback: 返回零向量
            return [0.0] * settings.MEMORY_VECTOR_DIM


llm_client = LLMClient()


# ──────────────────────── OpenClaw 工具调用解析 ────────────────────────

# Agent 回复中嵌入的工具调用格式:
#   [TOOL_CALL: tool_name(arg1="val1", arg2="val2")]
TOOL_CALL_PATTERN = re.compile(
    r'\[TOOL_CALL:\s*(\w+)\(([^)]*)\)\]'
)


def parse_tool_calls(text: str) -> List[Dict[str, Any]]:
    """从 Agent 回复中解析 OpenClaw 工具调用请求"""
    calls = []
    for match in TOOL_CALL_PATTERN.finditer(text):
        tool_name = match.group(1)
        args_str = match.group(2).strip()
        # 简易参数解析 (key="value" 格式)
        arguments = {}
        if args_str:
            for pair in re.findall(r'(\w+)\s*=\s*"([^"]*)"', args_str):
                arguments[pair[0]] = pair[1]
            # 也支持 key=value (无引号)
            for pair in re.findall(r'(\w+)\s*=\s*([^,\s"]+)', args_str):
                if pair[0] not in arguments:
                    arguments[pair[0]] = pair[1]
        calls.append({
            "tool": tool_name,
            "arguments": arguments,
            "raw": match.group(0),
        })
    return calls


async def execute_openclaw_tools(
    tool_calls: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """通过 OpenClaw Bridge 执行工具调用"""
    results = []
    for call in tool_calls:
        result = await openclaw_bridge.call_tool(
            call["tool"], call["arguments"]
        )
        results.append({
            "tool": call["tool"],
            "arguments": call["arguments"],
            "result": result,
        })
    return results


# ──────────────────────────── Agent 基类 ────────────────────────────
class BaseAgent:
    """所有 AOS Agent 的基类（集成 OpenClaw 工具能力）

    每个 Agent 有:
    - name: 唯一标识
    - system_prompt: 从 Persona 构建
    - tools: 可调用的工具列表（包含 OpenClaw 工具）

    OpenClaw 集成:
    - Agent 的系统提示中包含 OpenClaw 可用工具描述
    - Agent 回复中可嵌入 [TOOL_CALL: ...] 指令
    - 系统自动解析并通过 OpenClaw Bridge 执行
    - 执行结果回注入对话上下文供 Agent 继续推理
    """

    name: str = "base"
    description: str = ""

    def __init__(self):
        self.llm = llm_client
        self._system_prompt = ""
        self._conversation_history: List[Dict[str, str]] = []
        self._openclaw_tools_loaded = False
        self._openclaw_tools_desc = ""

    def set_system_prompt(self, prompt: str):
        """设置系统提示词（由 PersonaService 构建）"""
        self._system_prompt = prompt

    async def _ensure_openclaw_tools(self):
        """懒加载 OpenClaw 可用工具"""
        if self._openclaw_tools_loaded:
            return
        self._openclaw_tools_loaded = True

        if openclaw_bridge.is_available:
            tools = await openclaw_bridge.discover_tools()
            if tools:
                desc = "\n## OpenClaw 外部工具（通过 MCP 调用）\n"
                desc += "使用格式: `[TOOL_CALL: tool_name(arg1=\"val1\")]`\n\n"
                for t in tools[:20]:  # 限制数量避免 prompt 过长
                    desc += f"- **{t.get('name', '')}**: {t.get('description', '')}\n"
                self._openclaw_tools_desc = desc
                logger.info(f"Agent {self.name} 获取到 {len(tools)} 个 OpenClaw 工具")
            else:
                self._openclaw_tools_desc = OPENCLAW_TOOL_DESCRIPTIONS
        else:
            self._openclaw_tools_desc = ""

    async def process(
        self,
        user_message: str,
        *,
        context: Dict[str, Any] = None,
        session_history: List[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """处理用户消息，包含 OpenClaw 工具调用闭环

        流程:
        1. 构建消息 (含 OpenClaw 工具描述)
        2. 调用 LLM 获取回复
        3. 解析回复中的 [TOOL_CALL: ...] 指令
        4. 通过 OpenClaw Bridge 执行工具调用
        5. 将工具结果注入上下文，再次调用 LLM
        6. 返回最终结果

        Returns:
            {
                "reply": str,
                "agent": str,
                "actions": List[Dict],
                "tasks_created": List,
                "memories_stored": List,
                "tool_calls": List[Dict],   # OpenClaw 工具调用记录
                "metadata": Dict,
            }
        """
        await self._ensure_openclaw_tools()

        messages = self._build_messages(
            user_message, context, session_history
        )
        reply = await self.llm.chat(messages)

        # ── ReAct 循环: 解析并执行工具调用 ──
        tool_results = []
        max_iterations = 3  # 防止无限循环
        iteration = 0

        while iteration < max_iterations:
            tool_calls = parse_tool_calls(reply)
            if not tool_calls:
                break

            iteration += 1
            logger.info(
                f"Agent {self.name} 请求 {len(tool_calls)} 个工具调用 "
                f"(迭代 {iteration})"
            )

            # 执行工具
            results = await execute_openclaw_tools(tool_calls)
            tool_results.extend(results)

            # 将工具结果注入对话，让 LLM 继续推理
            tool_result_text = "\n\n## 工具执行结果\n"
            for r in results:
                status = "✅ 成功" if r["result"].get("success") else "❌ 失败"
                tool_result_text += (
                    f"### {r['tool']} — {status}\n"
                    f"```json\n{json.dumps(r['result'], ensure_ascii=False, indent=2)}\n```\n\n"
                )

            # 清除原始回复中的工具调用标记
            clean_reply = reply
            for call in tool_calls:
                clean_reply = clean_reply.replace(call["raw"], "")

            messages.append({"role": "assistant", "content": reply})
            messages.append({
                "role": "user",
                "content": f"[系统] 工具已执行，请根据以下结果继续回复用户：\n{tool_result_text}",
            })

            reply = await self.llm.chat(messages)

        return {
            "reply": reply,
            "agent": self.name,
            "actions": [],
            "tasks_created": [],
            "memories_stored": [],
            "tool_calls": tool_results,
            "metadata": {},
        }

    async def process_stream(
        self,
        user_message: str,
        *,
        context: Dict[str, Any] = None,
        session_history: List[Dict[str, str]] = None,
    ) -> AsyncGenerator[str, None]:
        """流式处理（注意: 流式模式下不支持工具调用闭环）"""
        await self._ensure_openclaw_tools()
        messages = self._build_messages(
            user_message, context, session_history
        )
        async for chunk in self.llm.chat_stream(messages):
            yield chunk

    def _build_messages(
        self,
        user_message: str,
        context: Dict = None,
        history: List[Dict] = None,
    ) -> List[Dict[str, str]]:
        """构建 LLM 消息列表（含 OpenClaw 工具描述）"""
        messages = []

        # 系统提示
        system = self._system_prompt

        # 注入 OpenClaw 工具描述
        if self._openclaw_tools_desc:
            system += "\n" + self._openclaw_tools_desc

        if context:
            system += "\n\n## 当前上下文\n"
            for k, v in context.items():
                system += f"- {k}: {v}\n"
        messages.append({"role": "system", "content": system})

        # 历史消息
        if history:
            messages.extend(history[-20:])  # 限制窗口

        # 当前消息
        messages.append({"role": "user", "content": user_message})
        return messages

    def get_tools_description(self) -> str:
        """返回工具描述（含 OpenClaw 工具）"""
        return self._openclaw_tools_desc

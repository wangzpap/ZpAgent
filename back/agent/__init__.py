"""
ReAct Agent 核心引擎

实现 ReAct（Reasoning + Acting）范式的智能体，基于 LangChain 1.2：
  - 使用 ChatOpenAI + bind_tools() 进行工具绑定
  - 通过 astream_events(version="v2") 实现逐 token 流式输出
  - 手动实现 ReAct 循环（推理 → 行动 → 观察 → ... → 最终回答）
  - 支持并行工具执行（asyncio.gather）
  - 集成内存会话记忆（可扩展至 DB）

ReAct 循环流程：
  1. 接收用户消息，加入对话历史
  2. 将选定工具绑定到 LLM（bind_tools）
  3. 流式调用 LLM，逐 token 输出 + 检测 tool_calls
  4. 若 LLM 返回 tool_calls：
     - 并行执行所有工具调用
     - 将工具结果作为 ToolMessage 加入历史
     - 回到步骤 3 继续推理
  5. 若 LLM 返回纯文本（无 tool_calls）：作为最终答案，保存并结束
  6. 达到最大迭代次数时终止，防止无限循环
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI

from config import settings
from llm import create_llm
from tools.registry import ToolRegistry
from memory import InMemoryStore

logger = logging.getLogger(__name__)

# ============================================
# 系统提示词
# ============================================
SYSTEM_PROMPT = "你是一个智能助手。"


class ReActAgent:
    """
    ReAct 智能体

    核心组件：
      - llm: LangChain ChatOpenAI 实例（支持流式输出）
      - tool_registry: 工具注册表（管理所有可用工具）
      - memory: 会话记忆存储（当前为内存实现）

    使用方式：
        agent = ReActAgent()
        async for event in agent.run(chat_request):
            yield event  # SSE 事件
    """

    def __init__(self):
        """初始化 ReAct Agent 的所有组件"""
        # LangChain ChatOpenAI 实例
        self.llm: ChatOpenAI = create_llm()

        # 工具注册表：注册并管理所有可用工具
        self.tool_registry = ToolRegistry()
        self.tool_registry.register_builtin_tools()

        # 会话记忆存储（内存实现，后续可扩展为 DB）
        self.memory = InMemoryStore()

    # ============================================
    # 主入口：处理聊天请求并产出 SSE 事件流
    # ============================================
    async def run(
        self, request: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理一次聊天请求，通过 async generator 产出 SSE 事件

        Args:
            request: 聊天请求字典，包含 message、conversation_id、selected_tools

        Yields:
            SSE 事件字典，type 字段标识事件类型：
            - start:    对话开始（包含 conversation_id）
            - thinking: ReAct 推理步骤（工具调用 / 观察结果）
            - token:    流式文本 token
            - done:     对话结束（包含最终回复）
            - error:    错误信息
        """
        user_message: str = request["message"]
        conversation_id: Optional[str] = request.get("conversation_id")
        selected_tools: List[str] = request.get("selected_tools", [])

        # ---- Step 1: 会话管理 ----
        if not conversation_id or not await self.memory.conversation_exists(
            conversation_id
        ):
            conversation_id = await self.memory.create_conversation()
            # 用用户消息的前 20 个字符作为会话标题
            title = user_message[:20] + ("..." if len(user_message) > 20 else "")
            await self.memory.update_title(conversation_id, title)

        # 发送对话开始事件
        yield {"type": "start", "data": {"conversation_id": conversation_id}}

        # ---- Step 2: 准备工具 ----
        # 注意：selected_tools 为 [] 表示用户明确不选任何工具，应直接对话
        # 只有 None（未传参）时才默认使用全部工具
        if selected_tools is not None:
            tools = self.tool_registry.get_langchain_tools(selected_tools)
        else:
            tools = self.tool_registry.get_all_tools()

        logger.info(
            "收到请求: message=%r, selected_tools=%s, resolved_tools=%s",
            user_message, selected_tools, [t.name for t in tools],
        )

        # 将工具绑定到 LLM（LangChain 自动转换为 OpenAI function calling 格式）
        llm_with_tools = self.llm.bind_tools(tools) if tools else self.llm

        # ---- Step 3: 添加用户消息到记忆 ----
        user_msg_dict = {"role": "user", "content": user_message}
        await self.memory.add_message(conversation_id, user_msg_dict)

        # 构建发送给 LLM 的消息列表（LangChain Message 对象）
        history = await self.memory.get_messages(conversation_id)
        messages: List[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
        messages.extend(self._dict_to_langchain_message(m) for m in history)

        # ---- Step 4: ReAct 推理循环 ----
        final_content = ""

        for iteration in range(1, settings.MAX_ITERATIONS + 1):
            content_parts: List[str] = []
            tool_calls_map: Dict[int, Dict[str, str]] = {}

            try:
                # 流式调用 LLM，通过 astream_events 获取逐 token 事件
                async for event in llm_with_tools.astream_events(
                    messages, version="v2"
                ):
                    kind = event.get("event")

                    # ---- 处理流式文本 token ----
                    if kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]

                        # 输出文本 token 给前端
                        if chunk.content:
                            content_parts.append(chunk.content)
                            yield {
                                "type": "token",
                                "data": {"content": chunk.content},
                            }

                        # 累积工具调用块（跨多个 chunk 拼接）
                        if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                            for tc_chunk in chunk.tool_call_chunks:
                                idx = tc_chunk.get("index")
                                if idx is None:
                                    continue
                                if idx not in tool_calls_map:
                                    tool_calls_map[idx] = {
                                        "id": "",
                                        "name": "",
                                        "args": "",
                                    }
                                if tc_chunk.get("id"):
                                    tool_calls_map[idx]["id"] = tc_chunk["id"]
                                if tc_chunk.get("name"):
                                    tool_calls_map[idx]["name"] += tc_chunk["name"]
                                if tc_chunk.get("args"):
                                    tool_calls_map[idx]["args"] += tc_chunk["args"]

            except Exception as e:
                logger.exception("LLM 调用异常（第 %d 轮迭代）", iteration)
                yield {
                    "type": "error",
                    "data": {"content": f"LLM 调用异常: {e}"},
                }
                return

            # 拼接完整响应内容
            full_content = "".join(content_parts)

            # 解析所有工具调用参数
            tool_calls_list = [
                {
                    "id": tc["id"],
                    "name": tc["name"],
                    "args": self._safe_parse_args(tc["args"]),
                }
                for tc in tool_calls_map.values()
            ]

            # ---- 情况 A：没有工具调用 → 最终答案 ----
            if not tool_calls_list:
                # 保存助手回复到记忆
                await self.memory.add_message(
                    conversation_id,
                    {"role": "assistant", "content": full_content},
                )
                final_content = full_content
                break

            # ---- 情况 B：有工具调用 → 执行工具并继续循环 ----

            # 1) 构造 AI 消息（包含 tool_calls）并加入消息列表
            ai_message = AIMessage(
                content=full_content,
                tool_calls=tool_calls_list,
            )
            messages.append(ai_message)

            # 保存 AI 消息到记忆
            await self.memory.add_message(
                conversation_id, self._aimessage_to_dict(ai_message)
            )

            # 2) 并行执行所有工具调用
            tool_tasks = [
                self._execute_tool(tc["name"], tc["args"])
                for tc in tool_calls_list
            ]
            observations = await asyncio.gather(*tool_tasks, return_exceptions=True)

            # 3) 处理工具执行结果
            for tc, observation in zip(tool_calls_list, observations):
                # 处理 gather 返回的异常
                if isinstance(observation, Exception):
                    observation = json.dumps(
                        {"error": f"工具 {tc['name']} 执行异常: {observation}"},
                        ensure_ascii=False,
                    )

                # 发送思考过程事件
                yield {
                    "type": "thinking",
                    "data": {
                        "step": iteration,
                        "tool": tc["name"],
                        "args": tc["args"],
                        "observation": str(observation),
                    },
                }

                # 构造 LangChain ToolMessage 并加入消息列表
                tool_msg = ToolMessage(
                    content=str(observation), tool_call_id=tc["id"]
                )
                messages.append(tool_msg)

                # 保存工具结果到记忆
                await self.memory.add_message(
                    conversation_id,
                    {
                        "role": "tool",
                        "content": str(observation),
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                    },
                )

        else:
            # 达到最大迭代次数
            fallback = "抱歉，我需要更多步骤来回答这个问题，请尝试简化你的问题。"
            yield {"type": "token", "data": {"content": fallback}}
            await self.memory.add_message(
                conversation_id, {"role": "assistant", "content": fallback}
            )
            final_content = fallback

        # ---- Step 5: 发送完成事件 ----
        yield {
            "type": "done",
            "data": {
                "conversation_id": conversation_id,
                "reply": final_content,
            },
        }

    # ============================================
    # 工具执行
    # ============================================
    async def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """
        执行指定工具

        Args:
            tool_name: 工具名称
            tool_args: 工具参数（字典）

        Returns:
            工具执行结果（字符串）
        """
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return json.dumps(
                {"error": f"未找到工具: {tool_name}"}, ensure_ascii=False
            )
        try:
            # 使用 LangChain 的 ainvoke 异步调用工具
            result = await tool.ainvoke(tool_args)
            return str(result)
        except Exception as e:
            logger.warning("工具 '%s' 执行失败: %s", tool_name, e)
            return json.dumps(
                {"error": f"工具 {tool_name} 执行失败: {e}"}, ensure_ascii=False
            )

    # ============================================
    # 辅助方法：消息格式转换
    # ============================================
    def _dict_to_langchain_message(self, msg: Dict[str, Any]):
        """将字典格式消息转换为 LangChain Message 对象"""
        role = msg["role"]
        content = msg.get("content", "")

        if role == "user":
            return HumanMessage(content=content)
        elif role == "assistant":
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                return AIMessage(content=content, tool_calls=tool_calls)
            return AIMessage(content=content)
        elif role == "tool":
            return ToolMessage(
                content=content,
                tool_call_id=msg.get("tool_call_id", ""),
            )
        elif role == "system":
            return SystemMessage(content=content)
        else:
            return HumanMessage(content=content)

    def _aimessage_to_dict(self, msg: AIMessage) -> Dict[str, Any]:
        """将 LangChain AIMessage 序列化为字典（用于存储到记忆）"""
        result: Dict[str, Any] = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            result["tool_calls"] = [
                {"id": tc["id"], "name": tc["name"], "args": tc["args"]}
                for tc in msg.tool_calls
            ]
        return result

    def _safe_parse_args(self, args_str: str) -> dict:
        """安全解析工具参数 JSON 字符串"""
        if not args_str:
            return {}
        try:
            return json.loads(args_str)
        except (json.JSONDecodeError, TypeError):
            return {"raw": args_str}

    # ============================================
    # 公共查询方法
    # ============================================
    def get_tool_info_list(self) -> List[Dict[str, Any]]:
        """获取所有可用工具的前端展示信息"""
        return self.tool_registry.get_tool_info_list()

    async def get_conversations(self) -> List[Dict[str, Any]]:
        """获取所有会话概要列表"""
        return await self.memory.get_conversations()

    async def get_history(self, conversation_id: str) -> Dict[str, Any] | None:
        """获取指定会话的完整历史，不存在返回 None"""
        return await self.memory.get_conversation(conversation_id)

    async def delete_conversation(self, conversation_id: str) -> bool:
        """删除指定会话"""
        return await self.memory.delete_conversation(conversation_id)

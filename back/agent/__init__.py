"""
ReAct Agent 核心引擎（基于 LangGraph）

使用 langchain.agents.create_agent 构建 ReAct 智能体，替代手动实现的 ReAct 循环。
通过 astream_events(version="v2") 实现逐 token 流式输出，保持与前端兼容的 SSE 事件格式。

架构概览：
  - agent/graph.py: 使用 create_agent 构建 LangGraph 状态图
  - agent/__init__.py: 编排层，负责会话管理、流式事件适配
  - memory/: 会话元数据注册表（ConversationRegistry）
  - tools/: 工具注册表 + 内置工具

会话记忆机制（双层架构）：
  - LangGraph checkpointer（InMemorySaver）：框架层自动管理对话状态，
    通过 thread_id 实现跨请求的对话延续，无需手动传递消息历史。
  - ConversationRegistry：应用层管理会话元数据（标题、时间戳），
    供前端 UI 展示会话列表。两者职责不同，互补共存。

ReAct 流程（由 LangGraph 自动管理）：
  1. 接收用户消息，创建或定位会话
  2. 根据选定工具动态构建 LangGraph Agent 图（共享 InMemorySaver checkpointer）
  3. 仅传入当前用户消息 + thread_id，checkpointer 自动拼接历史上下文
  4. 通过 astream_events 流式执行：
     - model 节点: LLM 推理，逐 token 输出 + 产生 tool_calls
     - tools 节点: 并行执行工具调用，返回观察结果
     - 循环直到 LLM 产出最终回答（无 tool_calls）
  5. 达到 recursion_limit 时终止，防止无限循环
"""

import logging
from typing import AsyncGenerator, List, Dict, Any, Optional

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from config import settings
from tools.registry import ToolRegistry
from memory import ConversationRegistry
from agent.graph import build_agent_graph, DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ReActAgent:
    """
    ReAct 智能体（基于 LangGraph）

    核心组件：
      - tool_registry: 工具注册表（管理所有可用工具）
      - registry: 会话元数据注册表（标题、时间戳，供 UI 展示）
      - checkpointer: InMemorySaver（LangGraph 框架层对话状态管理）

    会话记忆机制：
      - InMemorySaver checkpointer 通过 thread_id 自动管理对话状态，
        每次请求只需传入当前用户消息，框架自动拼接历史上下文。
      - ConversationRegistry 管理会话列表、标题等应用层元数据。

    使用方式：
        agent = ReActAgent()
        async for event in agent.run(chat_request):
            yield event  # SSE 事件
    """

    def __init__(self):
        """初始化 ReAct Agent 的所有组件"""
        # 工具注册表：注册并管理所有可用工具
        self.tool_registry = ToolRegistry()
        self.tool_registry.register_builtin_tools()
        # 会话元数据注册表（应用层：会话列表、标题）
        self.registry = ConversationRegistry()
        # LangGraph checkpointer：框架层自动管理对话状态（跨请求记忆）
        # 所有 graph 实例共享同一个 checkpointer，通过 thread_id 区分会话
        self.checkpointer = InMemorySaver()

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
        if not conversation_id or not await self.registry.conversation_exists(
            conversation_id
        ):
            conversation_id = await self.registry.create_conversation()
            title = user_message[:20] + ("..." if len(user_message) > 20 else "")
            await self.registry.update_title(conversation_id, title)

        yield {"type": "start", "data": {"conversation_id": conversation_id}}

        # ---- Step 2: 准备工具 ----
        tools = self.tool_registry.get_langchain_tools(selected_tools)

        logger.info(
            "收到请求: message=%r, selected_tools=%s, resolved_tools=%s",
            user_message, selected_tools, [t.name for t in tools],
        )

        # ---- Step 3: 构建 Agent 图并流式执行 ----
        # 共享 self.checkpointer，通过 thread_id 关联同一会话的历史
        agent_graph = build_agent_graph(
            tools=tools,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            checkpointer=self.checkpointer,
        )

        # ---- 流式追踪变量 ----
        iteration = 0
        final_content = ""
        # on_tool_start → on_tool_end 通过 run_id 关联
        pending_tool_runs: Dict[str, Dict[str, Any]] = {}
        # 缓存最近一次 AI 消息的 tool_calls（来自 on_chat_model_end）
        pending_ai_tool_calls: List[Dict[str, Any]] = []

        try:
            async for event in agent_graph.astream_events(
                # 关键：仅传入当前用户消息，checkpointer 自动管理对话历史
                {"messages": [HumanMessage(content=user_message)]},
                version="v2",
                config={
                    "recursion_limit": settings.MAX_ITERATIONS * 2 + 5,
                    # thread_id 让 checkpointer 自动关联同一会话的历史
                    "configurable": {"thread_id": conversation_id},
                },
            ):
                kind = event.get("event")

                # ---- LLM 调用开始 → 重置迭代状态 ----
                if kind == "on_chat_model_start":
                    iteration += 1
                    pending_ai_tool_calls = []

                # ---- 流式文本 token → 实时推送给前端 ----
                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield {
                            "type": "token",
                            "data": {"content": chunk.content},
                        }

                # ---- LLM 调用结束 → 缓存 tool_calls 供后续关联 ----
                elif kind == "on_chat_model_end":
                    ai_msg: AIMessage = event["data"]["output"]
                    if ai_msg.tool_calls:
                        pending_ai_tool_calls = ai_msg.tool_calls

                # ---- 工具开始执行 ----
                elif kind == "on_tool_start":
                    run_id = event.get("run_id", "")
                    pending_tool_runs[run_id] = {
                        "step": iteration,
                        "tool_name": event.get("name", ""),
                        "tool_input": event.get("data", {}).get("input", {}),
                    }

                # ---- 工具执行完成 → 发送 thinking 事件 ----
                elif kind == "on_tool_end":
                    run_id = event.get("run_id", "")
                    info = pending_tool_runs.pop(run_id, None)

                    output = event.get("data", {}).get("output")
                    if hasattr(output, "content"):
                        observation = str(output.content)
                        tool_call_id = getattr(output, "tool_call_id", "")
                    else:
                        observation = str(output) if output else ""
                        tool_call_id = ""

                    if info:
                        # 从缓存的 AI tool_calls 中匹配参数
                        tool_args: dict = {}
                        for tc in pending_ai_tool_calls:
                            if tc["name"] == info["tool_name"]:
                                tool_args = tc["args"]
                                tool_call_id = tc["id"] or tool_call_id
                                break
                        if not tool_args:
                            tool_args = info["tool_input"]

                        yield {
                            "type": "thinking",
                            "data": {
                                "step": info["step"],
                                "tool": info["tool_name"],
                                "args": tool_args,
                                "observation": observation,
                            },
                        }

            # ---- 流结束：从 checkpointer 状态中获取最终回复 ----
            state = await agent_graph.aget_state(
                {"configurable": {"thread_id": conversation_id}}
            )
            final_content = ""
            for msg in reversed(state.values.get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                    final_content = (
                        msg.content if isinstance(msg.content, str)
                        else str(msg.content)
                    )
                    break

            # 更新会话时间戳
            await self.registry.touch(conversation_id)

        except GraphRecursionError:
            fallback = "抱歉，我需要更多步骤来回答这个问题，请尝试简化你的问题。"
            yield {"type": "token", "data": {"content": fallback}}
            final_content = fallback

        except Exception as e:
            logger.exception("Agent 执行异常")
            yield {
                "type": "error",
                "data": {"content": f"Agent 执行异常: {e}"},
            }
            return

        # ---- Step 4: 发送完成事件 ----
        yield {
            "type": "done",
            "data": {
                "conversation_id": conversation_id,
                "reply": final_content,
            },
        }

    # ============================================
    # 公共查询方法
    # ============================================
    def get_tool_info_list(self) -> List[Dict[str, Any]]:
        """获取所有可用工具的前端展示信息"""
        return self.tool_registry.get_tool_info_list()

    async def get_conversations(self) -> List[Dict[str, Any]]:
        """获取所有会话概要列表"""
        return await self.registry.get_conversations()

    async def get_history(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定会话的完整历史

        从 LangGraph checkpointer 状态中读取消息历史，
        结合 ConversationRegistry 的元数据返回完整会话信息。
        """
        meta = await self.registry.get_conversation(conversation_id)
        if meta is None:
            return None

        # 从 checkpointer 状态中读取消息历史
        try:
            # 构建临时 graph 以访问 checkpointer 中的状态
            agent_graph = build_agent_graph(
                tools=[],
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                checkpointer=self.checkpointer,
            )
            state = await agent_graph.aget_state(
                {"configurable": {"thread_id": conversation_id}}
            )
            messages = [
                self._format_message(msg)
                for msg in state.values.get("messages", [])
            ]
        except Exception:
            logger.warning("无法从 checkpointer 获取会话 %s 的历史", conversation_id)
            messages = []

        return {
            "id": meta["id"],
            "title": meta["title"],
            "messages": messages,
            "created_at": meta["created_at"],
            "updated_at": meta["updated_at"],
        }

    async def delete_conversation(self, conversation_id: str) -> bool:
        """删除指定会话"""
        return await self.registry.delete_conversation(conversation_id)

    @staticmethod
    def _format_message(msg) -> Dict[str, Any]:
        """
        将 LangChain Message 对象格式化为前端展示用的字典

        转换映射：
          - HumanMessage  → role=user
          - AIMessage     → role=assistant（可携带 tool_calls）
          - ToolMessage   → role=tool
          - SystemMessage → role=system
        """
        if isinstance(msg, HumanMessage):
            return {"role": "user", "content": str(msg.content)}
        elif isinstance(msg, AIMessage):
            result: Dict[str, Any] = {
                "role": "assistant",
                "content": str(msg.content) if msg.content else "",
            }
            if msg.tool_calls:
                result["tool_calls"] = [
                    {"id": tc["id"], "name": tc["name"], "args": tc["args"]}
                    for tc in msg.tool_calls
                ]
            return result
        elif isinstance(msg, ToolMessage):
            return {
                "role": "tool",
                "content": str(msg.content),
                "tool_call_id": getattr(msg, "tool_call_id", ""),
            }
        elif isinstance(msg, SystemMessage):
            return {"role": "system", "content": str(msg.content)}
        else:
            return {"role": "user", "content": str(msg.content)}

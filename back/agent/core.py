"""
ReAct Agent 核心编排层

ReActAgent 是整个 Agent 系统的入口类，职责：
  1. 生命周期管理（初始化组件、加载工具、释放资源）
  2. 请求编排（run / resume 的主流程控制）
  3. 会话 CRUD（供 API 路由层调用的公共查询方法）

具体的流式事件转换、中断检测、消息格式化等逻辑
分别委托给 stream.py、interrupt.py、formatter.py。
"""

import logging
from typing import AsyncGenerator, List, Dict, Any, Optional

from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from config import settings
from entity.tool.tool_info import ToolInfo
from tools.registry import ToolRegistry
from tools.mcp_loader import load_mcp_tools
from conversation import ConversationStore, create_conversation_store
from checkpoint import CheckpointStore, create_checkpoint_store
from agent.graph import build_agent_graph, DEFAULT_SYSTEM_PROMPT
from agent.stream import stream_agent_events
from agent.interrupt import (
    detect_interrupt,
    extract_pending_actions_from_state,
    auto_reject_pending_tools,
)
from agent.formatter import format_message

logger = logging.getLogger(__name__)


class ReActAgent:
    """
    ReAct 智能体（基于 LangGraph）

    核心组件：
      - tool_registry: 工具注册表（管理所有可用工具 + 审批策略）
      - registry: 会话存储（策略模式，支持内存 / MySQL 等后端）
      - checkpoint_store: 检查点存储（策略模式，支持内存 / MySQL 等后端）
      - checkpointer: LangGraph BaseCheckpointSaver（对话状态管理）
    """

    # ============================================
    # 生命周期
    # ============================================

    def __init__(self):
        """初始化 ReAct Agent 的所有组件"""
        logger.info("=" * 50)
        logger.info("[Agent] 正在初始化 ReAct Agent 组件...")
        self.tool_registry = ToolRegistry()
        self.tool_registry.register_builtin_tools()
        logger.info("[Agent] 内置工具已注册")
        self.registry: ConversationStore = create_conversation_store()
        self.checkpoint_store: CheckpointStore = create_checkpoint_store()
        self.checkpointer = None  # 在 initialize() 中赋值
        logger.info("[Agent] 组件初始化完成")

    async def initialize(self) -> None:
        """异步初始化：存储后端 + MCP 工具加载"""
        await self.registry.initialize()
        logger.info("[Agent] 会话存储后端初始化完成")

        await self.checkpoint_store.initialize()
        self.checkpointer = self.checkpoint_store.get_checkpointer()
        logger.info("[Agent] 检查点存储后端初始化完成 (类型: %s)",
                     type(self.checkpointer).__name__)

        logger.info("[Agent] 开始加载 MCP 工具（路径: %s）...", settings.MCP_CONFIG_PATH)
        mcp_tools = await load_mcp_tools(settings.MCP_CONFIG_PATH)
        if mcp_tools:
            self.tool_registry.register_mcp_tools(mcp_tools)
            tool_names = [t.name for t, _ in mcp_tools]
            logger.info("[Agent] MCP 工具加载完成，共 %d 个: %s", len(mcp_tools), tool_names)
        else:
            logger.info("[Agent] 未找到 MCP 工具（mcp_servers.json 为空或不存在）")

    async def reload_mcp_tools(self) -> Dict[str, Any]:
        """热重载 MCP 工具（清除旧工具 → 加载新工具）"""
        logger.info("[MCP] 开始热重载 MCP 工具...")
        cleared = self.tool_registry.clear_mcp_tools()
        logger.info("[MCP] 已清除 %d 个旧的 MCP 工具", cleared)

        mcp_tools = await load_mcp_tools(settings.MCP_CONFIG_PATH)
        if mcp_tools:
            self.tool_registry.register_mcp_tools(mcp_tools)
            tool_names = [t.name for t, _ in mcp_tools]
            logger.info("[MCP] 已加载 %d 个新的 MCP 工具: %s", len(mcp_tools), tool_names)
        else:
            logger.info("[MCP] 未找到新的 MCP 工具")

        total = len(self.tool_registry.get_all_tools())
        logger.info("[MCP] 重载完成 | 清除=%d | 加载=%d | 总计=%d",
                    cleared, len(mcp_tools) if mcp_tools else 0, total)
        return {"cleared": cleared, "loaded": len(mcp_tools), "total": total}

    async def close(self) -> None:
        """关闭 Agent，释放资源（应用关闭时调用）"""
        await self.registry.close()
        await self.checkpoint_store.close()
        logger.info("[Agent] 存储后端已关闭")

    # ============================================
    # 主入口：处理新消息
    # ============================================

    async def run(
        self, request: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理一次聊天请求，通过 async generator 产出 SSE 事件。

        流程：
          1. 会话管理（创建/定位会话）
          2. 准备工具 + 清理过期工具调用
          3. 构建 Agent 图并流式执行
          4. 检测 HITL 中断 → yield approval_required / done

        Yields:
            SSE 事件字典（start / token / thinking / tool_result / approval_required / done / error）
        """
        user_message: str = request["message"]
        conversation_id: Optional[str] = request.get("conversation_id")
        selected_tools: List[str] = request.get("selected_tools", [])

        logger.info("=" * 60)
        logger.info("[Run] ===== 新的聊天请求开始 =====")
        logger.info("[Run] 用户消息: %r | conversation_id=%s | selected_tools=%s",
                    user_message, conversation_id, selected_tools or "(全部)")

        # ---- Step 1: 会话管理 ----
        if not conversation_id or not await self.registry.conversation_exists(conversation_id):
            conversation_id = await self.registry.create_conversation()
            title = user_message[:20] + ("..." if len(user_message) > 20 else "")
            await self.registry.update_title(conversation_id, title)
            logger.info("[Run][Step1] 创建新会话: %s (标题: %r)", conversation_id, title)
        else:
            logger.info("[Run][Step1] 使用已有会话: %s", conversation_id)

        yield {"type": "start", "data": {"conversation_id": conversation_id}}

        # ---- Step 2: 准备工具 + 清理过期工具调用 ----
        tools = self.tool_registry.get_langchain_tools(selected_tools)
        interrupt_on = self.tool_registry.get_interrupt_on_map(selected_tools)
        logger.info("[Run][Step2] 工具: %s | 需审批: %s",
                    [t.name for t in tools], list(interrupt_on.keys()) or "(无)")

        cleaned = await auto_reject_pending_tools(
            self.tool_registry, self.checkpointer, conversation_id
        )
        if cleaned:
            logger.warning("[Run][Step2] 检测到未完成的工具调用，已自动清理")

        # ---- Step 3: 构建 Agent 图并流式执行 ----
        agent_graph = build_agent_graph(
            tools=tools,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            checkpointer=self.checkpointer,
            interrupt_on=interrupt_on,
        )
        config = {
            "recursion_limit": settings.MAX_ITERATIONS * 2 + 5,
            "configurable": {"thread_id": conversation_id},
        }

        try:
            event_count = 0
            async for event in stream_agent_events(
                agent_graph,
                {"messages": [HumanMessage(content=user_message)]},
                config,
            ):
                event_count += 1
                yield event
            logger.info("[Run][Step3] 流式执行结束，共产出 %d 个事件", event_count)

            # ---- Step 4: 检查 HITL 中断 ----
            interrupt_info = await detect_interrupt(agent_graph, conversation_id)
            if interrupt_info is not None:
                action_names = [a["name"] for a in interrupt_info["actions"]]
                logger.info("[Run][Step4] HITL 中断触发，需审批: %s", action_names)
                yield {
                    "type": "approval_required",
                    "data": {
                        "conversation_id": conversation_id,
                        "actions": interrupt_info["actions"],
                    },
                }
                return

            # 无中断：正常完成
            await self.registry.touch(conversation_id)
            final_content = await self._extract_final_reply(agent_graph, conversation_id)
            yield {
                "type": "done",
                "data": {"conversation_id": conversation_id, "reply": final_content},
            }
            logger.info("[Run] ===== 聊天请求完成 =====")

        except GraphRecursionError:
            logger.warning("[Run] GraphRecursionError: 达到最大迭代次数 (%d)",
                           settings.MAX_ITERATIONS)
            fallback = "抱歉，我需要更多步骤来回答这个问题，请尝试简化你的问题。"
            yield {"type": "token", "data": {"content": fallback}}
            yield {"type": "done", "data": {"conversation_id": conversation_id, "reply": fallback}}

        except Exception as e:
            logger.exception("[Run] Agent 执行异常")
            yield {"type": "error", "data": {"content": f"Agent 执行异常: {e}"}}

    # ============================================
    # 审批恢复
    # ============================================

    async def resume(
        self, conversation_id: str, decisions: List[Dict[str, Any]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        接收人工审批决策，恢复被 HITL 中断的 Agent 执行。

        决策类型：
          - approve: 按原参数执行工具
          - edit: 用修改后的参数执行工具
          - reject: 跳过执行，将拒绝原因作为工具结果返回给 LLM
          - respond: 人工消息直接作为工具返回值

        Yields:
            SSE 事件字典（与 run 相同的事件类型）
        """
        logger.info("=" * 60)
        logger.info("[Resume] ===== 审批恢复请求开始 =====")
        logger.info("[Resume] conversation_id=%s | 收到 %d 个决策",
                    conversation_id, len(decisions))

        tools = self.tool_registry.get_langchain_tools()
        interrupt_on = self.tool_registry.get_interrupt_on_map()
        agent_graph = build_agent_graph(
            tools=tools,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            checkpointer=self.checkpointer,
            interrupt_on=interrupt_on,
        )
        config = {
            "recursion_limit": settings.MAX_ITERATIONS * 2 + 5,
            "configurable": {"thread_id": conversation_id},
        }

        resume_input = Command(resume={"decisions": decisions})

        try:
            event_count = 0
            async for event in stream_agent_events(agent_graph, resume_input, config):
                event_count += 1
                yield event
            logger.info("[Resume] 流式执行结束，共产出 %d 个事件", event_count)

            # 检查是否再次触发中断
            interrupt_info = await detect_interrupt(agent_graph, conversation_id)
            if interrupt_info is not None:
                action_names = [a["name"] for a in interrupt_info["actions"]]
                logger.info("[Resume] 再次触发 HITL 中断，需审批: %s", action_names)
                yield {
                    "type": "approval_required",
                    "data": {
                        "conversation_id": conversation_id,
                        "actions": interrupt_info["actions"],
                    },
                }
                return

            # 执行完毕
            await self.registry.touch(conversation_id)
            final_content = await self._extract_final_reply(agent_graph, conversation_id)
            yield {
                "type": "done",
                "data": {"conversation_id": conversation_id, "reply": final_content},
            }
            logger.info("[Resume] ===== 审批恢复完成 =====")

        except GraphRecursionError:
            logger.warning("[Resume] GraphRecursionError: 达到最大迭代次数")
            fallback = "抱歉，我需要更多步骤来回答这个问题，请尝试简化你的问题。"
            yield {"type": "token", "data": {"content": fallback}}
            yield {"type": "done", "data": {"conversation_id": conversation_id, "reply": fallback}}

        except Exception as e:
            logger.exception("[Resume] Agent resume 异常")
            yield {"type": "error", "data": {"content": f"Agent 恢复执行异常: {e}"}}

    # ============================================
    # 会话 CRUD（供 API 路由层调用）
    # ============================================

    def get_tool_info_list(self) -> List[ToolInfo]:
        """获取所有可用工具的前端展示信息"""
        return self.tool_registry.get_tool_info_list()

    async def get_conversations(self) -> List[Dict[str, Any]]:
        """获取所有会话概要列表"""
        return await self.registry.get_conversations()

    async def get_history(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定会话的完整历史。

        如果 checkpointer 中有挂起的 HITL 审批（页面刷新恢复场景），
        还会返回 pending_actions 字段，前端据此恢复审批面板。
        """
        meta = await self.registry.get_conversation(conversation_id)
        if meta is None:
            return None

        try:
            tools = self.tool_registry.get_langchain_tools()
            interrupt_on = self.tool_registry.get_interrupt_on_map()
            agent_graph = build_agent_graph(
                tools=tools,
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                checkpointer=self.checkpointer,
                interrupt_on=interrupt_on,
            )
            state = await agent_graph.aget_state(
                {"configurable": {"thread_id": conversation_id}}
            )
            messages = [format_message(msg) for msg in state.values.get("messages", [])]
            pending_actions = extract_pending_actions_from_state(state)
        except Exception:
            logger.warning("无法从 checkpointer 获取会话 %s 的历史", conversation_id)
            messages = []
            pending_actions = None

        result = {
            "id": meta["id"],
            "title": meta["title"],
            "messages": messages,
            "created_at": meta["created_at"],
            "updated_at": meta["updated_at"],
            "pinned_at": meta.get("pinned_at"),
        }
        if pending_actions:
            result["pending_actions"] = pending_actions
        return result

    async def delete_conversation(self, conversation_id: str) -> bool:
        """删除指定会话（元数据 + 对话上下文）"""
        await self.checkpointer.adelete_thread(conversation_id)
        return await self.registry.delete_conversation(conversation_id)

    async def clear_conversation(self, conversation_id: str) -> bool:
        """清空指定会话的消息历史（保留会话本身）"""
        if not await self.registry.conversation_exists(conversation_id):
            return False
        await self.checkpointer.adelete_thread(conversation_id)
        return True

    async def delete_messages(
        self, conversation_id: str, message_ids: List[str]
    ) -> Optional[int]:
        """
        删除指定消息及其之后的所有消息（级联删除）。

        Returns:
            None — 会话不存在
            0    — 会话存在，但未找到匹配的消息
            >0   — 实际删除的消息数量
        """
        if not await self.registry.conversation_exists(conversation_id):
            logger.warning("[DeleteMessages] 会话 %s 不存在", conversation_id)
            return None

        tools = self.tool_registry.get_langchain_tools()
        interrupt_on = self.tool_registry.get_interrupt_on_map()
        agent_graph = build_agent_graph(
            tools=tools,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            checkpointer=self.checkpointer,
            interrupt_on=interrupt_on,
        )

        config = {"configurable": {"thread_id": conversation_id}}
        state = await agent_graph.aget_state(config)
        messages = state.values.get("messages", [])

        if not messages:
            return 0

        # 找到最早匹配的消息索引
        target_ids = set(message_ids)
        earliest_idx = -1
        for i, msg in enumerate(messages):
            if msg.id in target_ids:
                earliest_idx = i
                break

        if earliest_idx == -1:
            logger.warning("[DeleteMessages] 会话 %s 中未找到匹配的消息 ID: %s",
                           conversation_id, message_ids)
            return 0

        messages_to_remove = messages[earliest_idx:]
        remove_ops = [RemoveMessage(id=msg.id) for msg in messages_to_remove]
        logger.info("[DeleteMessages] 会话 %s: 从索引 %d 开始删除 %d 条消息",
                    conversation_id, earliest_idx, len(messages_to_remove))

        await agent_graph.aupdate_state(config, {"messages": remove_ops})
        return len(messages_to_remove)

    async def rename_conversation(self, conversation_id: str, title: str) -> bool:
        """重命名指定会话"""
        if not await self.registry.conversation_exists(conversation_id):
            return False
        await self.registry.update_title(conversation_id, title)
        return True

    async def pin_conversation(self, conversation_id: str) -> bool:
        """顶置指定会话"""
        return await self.registry.pin(conversation_id)

    async def unpin_conversation(self, conversation_id: str) -> bool:
        """取消顶置指定会话"""
        return await self.registry.unpin(conversation_id)

    # ============================================
    # 内部辅助
    # ============================================

    async def _extract_final_reply(self, agent_graph, conversation_id: str) -> str:
        """从 checkpointer 状态中提取 LLM 的最终回复文本"""
        try:
            state = await agent_graph.aget_state(
                {"configurable": {"thread_id": conversation_id}}
            )
            for msg in reversed(state.values.get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                    return msg.content if isinstance(msg.content, str) else str(msg.content)
        except Exception as e:
            logger.warning("[FinalReply] 无法提取最终回复: %s", e)
        return ""

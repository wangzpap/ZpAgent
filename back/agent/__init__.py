"""
ReAct Agent 核心引擎（基于 LangGraph）

使用 langchain.agents.create_agent 构建 ReAct 智能体，替代手动实现的 ReAct 循环。
通过 astream_events(version="v2") 实现逐 token 流式输出，保持与前端兼容的 SSE 事件格式。

架构概览：
  - agent/graph.py: 使用 create_agent 构建 LangGraph 状态图（含 HITL 中间件）
  - agent/__init__.py: 编排层，负责会话管理、流式事件适配、中断恢复
  - conversation/: 会话元数据存储（策略模式，支持内存 / MySQL 后端）
  - checkpoint/: 对话检查点存储（策略模式，支持内存 / MySQL 后端）
  - tools/: 工具注册表 + 内置工具（含审批策略配置）

会话记忆机制（双层架构）：
  - CheckpointStore：框架层，LangGraph 自动管理对话状态（内存 / MySQL）
  - ConversationStore：应用层，管理会话元数据（内存 / MySQL）

人机交互（Human-in-the-Loop）：
  通过 HumanInTheLoopMiddleware 中间件实现按工具粒度的审批控制：
    1. LLM 产生 tool_calls 后，中间件检查哪些工具需要审批
    2. 需要审批的工具触发 interrupt()，暂停图执行
    3. run() 检测到中断后，提取 ActionRequest 信息，yield approval_required 事件
    4. 前端展示审批面板，用户做出决策（同意/拒绝/编辑参数）
    5. resume() 接收决策，通过 Command(resume=...) 恢复图执行
    6. 恢复后的流式输出与正常对话共享同一套事件处理逻辑
"""

import logging
from typing import AsyncGenerator, List, Dict, Any, Optional

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
    RemoveMessage,
)
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from config import settings
from tools.registry import ToolRegistry
from tools.mcp_loader import load_mcp_tools
from conversation import ConversationStore, create_conversation_store
from checkpoint import CheckpointStore, create_checkpoint_store
from agent.graph import build_agent_graph, DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ReActAgent:
    """
    ReAct 智能体（基于 LangGraph）

    核心组件：
      - tool_registry: 工具注册表（管理所有可用工具 + 审批策略）
      - registry: 会话存储（策略模式，支持内存 / MySQL 等后端）
      - checkpoint_store: 检查点存储（策略模式，支持内存 / 文件等后端）
      - checkpointer: LangGraph BaseCheckpointSaver（对话状态管理）
    """

    def __init__(self):
        """初始化 ReAct Agent 的所有组件"""
        logger.info("=" * 50)
        logger.info("[Agent] 正在初始化 ReAct Agent 组件...")
        self.tool_registry = ToolRegistry()
        self.tool_registry.register_builtin_tools()
        logger.info("[Agent] 内置工具已注册")
        # 工厂方法：根据配置创建会话存储后端（内存 or MySQL）
        self.registry: ConversationStore = create_conversation_store()
        # 工厂方法：根据配置创建检查点存储后端（内存 or MySQL）
        self.checkpoint_store: CheckpointStore = create_checkpoint_store()
        # checkpointer 在 initialize() 中赋值（MySQL 后端需要先建立连接）
        self.checkpointer = None
        logger.info("[Agent] 组件初始化完成")

    async def initialize(self) -> None:
        """异步初始化：初始化会话存储后端 + 检查点存储后端 + 加载 MCP 工具"""
        # 初始化会话存储后端（MySQL 后端会在此创建连接池和建表；内存后端为空操作）
        await self.registry.initialize()
        logger.info("[Agent] 会话存储后端初始化完成")

        # 初始化检查点存储后端（MySQL 后端会在此创建连接和建表；内存后端为空操作）
        await self.checkpoint_store.initialize()
        # initialize() 之后才能获取 checkpointer（MySQL 后端需要先建立连接）
        self.checkpointer = self.checkpoint_store.get_checkpointer()
        logger.info("[Agent] 检查点存储后端初始化完成 (类型: %s)",
                     type(self.checkpointer).__name__)

        logger.info("[Agent] 开始加载 MCP 工具（路径: %s）...", settings.MCP_CONFIG_PATH)
        mcp_tools = await load_mcp_tools(settings.MCP_CONFIG_PATH)
        if mcp_tools:
            self.tool_registry.register_mcp_tools(mcp_tools)
            logger.info("[Agent] MCP 工具加载完成，共加载 %d 个工具: %s",
                        len(mcp_tools), [t.name for t in mcp_tools])
        else:
            logger.info("[Agent] 未找到 MCP 工具（mcp_servers.json 为空或不存在）")

    async def reload_mcp_tools(self) -> Dict[str, Any]:
        """热重载 MCP 工具"""
        logger.info("[MCP] 开始热重载 MCP 工具...")
        cleared = self.tool_registry.clear_mcp_tools()
        logger.info("[MCP] 已清除 %d 个旧的 MCP 工具", cleared)
        mcp_tools = await load_mcp_tools(settings.MCP_CONFIG_PATH)
        if mcp_tools:
            self.tool_registry.register_mcp_tools(mcp_tools)
            logger.info("[MCP] 已加载 %d 个新的 MCP 工具: %s",
                        len(mcp_tools), [t.name for t in mcp_tools])
        else:
            logger.info("[MCP] 未找到新的 MCP 工具")
        total = len(self.tool_registry.get_all_tools())
        logger.info("[MCP] 重载完成 | 清除=%d | 加载=%d | 总计=%d",
                    cleared, len(mcp_tools) if mcp_tools else 0, total)
        return {
            "cleared": cleared,
            "loaded": len(mcp_tools),
            "total": total,
        }

    # ============================================
    # 共享：流式事件处理（run 和 resume 共用）
    # ============================================
    async def _stream_agent_events(
        self,
        agent_graph,
        input_data: dict,
        config: dict,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        遍历 Agent 图的 astream_events 流，将内部事件转换为前端 SSE 格式

        这是 run()（新消息）和 resume()（审批恢复）共享的核心流式处理逻辑。
        每次 yield 一个 SSE 事件字典，由 API 层转为 SSE 文本推送给前端。

        处理的事件类型：
          - on_chat_model_start → 重置迭代计数
          - on_chat_model_stream → yield token 事件（流式文本）
          - on_chat_model_end → 缓存 tool_calls
          - on_tool_start → yield thinking 事件（工具开始调用）
          - on_tool_end → yield tool_result 事件（工具执行完毕）

        当 HITL 中间件触发 interrupt 时，astream_events 会正常结束（不抛异常），
        此时需要由调用方（run/resume）检查 aget_state 来检测中断。

        Args:
            agent_graph: 编译好的 LangGraph 状态图
            input_data: 传给 astream_events 的输入（新消息或 Command）
            config: 包含 thread_id 等配置信息

        Yields:
            SSE 事件字典（token / thinking / tool_result）
        """
        # ---- 流式追踪变量 ----
        iteration = 0
        pending_tool_runs: Dict[str, Dict[str, Any]] = {}
        pending_ai_tool_calls: List[Dict[str, Any]] = []
        consumed_tc_indices: set = set()
        token_count = 0  # 统计本轮 token 数量

        logger.debug("[Stream] 开始监听 astream_events (v2)...")

        async for event in agent_graph.astream_events(
            input_data, version="v2", config=config,
        ):
            kind = event.get("event")

            # ---- LLM 调用开始 → 重置迭代状态 ----
            if kind == "on_chat_model_start":
                iteration += 1
                pending_ai_tool_calls = []
                consumed_tc_indices = set()
                token_count = 0
                logger.info("[Stream][迭代 %d] ▶ LLM 推理开始（第 %d 轮 ReAct 循环）",
                            iteration, iteration)

            # ---- 流式文本 token → 实时推送 ----
            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    token_count += 1
                    # 每 50 个 token 打一条进度日志，避免刷屏
                    if token_count % 50 == 1:
                        logger.debug("[Stream][迭代 %d]   流式输出 token #%d: %r",
                                     iteration, token_count, chunk.content)
                    yield {"type": "token", "data": {"content": chunk.content}}

            # ---- LLM 调用结束 → 缓存 tool_calls ----
            elif kind == "on_chat_model_end":
                ai_msg: AIMessage = event["data"]["output"]
                if ai_msg.tool_calls:
                    pending_ai_tool_calls = ai_msg.tool_calls
                    tc_summary = [
                        f"{tc['name']}({tc.get('args', {})})" for tc in ai_msg.tool_calls
                    ]
                    logger.info(
                        "[Stream][迭代 %d] ◼ LLM 推理完成 | 产出 %d 个 token | "
                        "请求调用 %d 个工具: %s",
                        iteration, token_count, len(ai_msg.tool_calls), tc_summary,
                    )
                else:
                    logger.info(
                        "[Stream][迭代 %d] ◼ LLM 推理完成 | 产出 %d 个 token | "
                        "无工具调用（纯文本回复）",
                        iteration, token_count,
                    )

            # ---- 工具开始执行 → 推送 thinking 事件 ----
            elif kind == "on_tool_start":
                run_id = event.get("run_id", "")
                tool_name = event.get("name", "")
                tool_input = event.get("data", {}).get("input", {})

                logger.info(
                    "[Stream][迭代 %d] 🔧 工具开始执行: %s | 输入参数: %s",
                    iteration, tool_name, tool_input,
                )

                # 从缓存的 AI tool_calls 中匹配参数和 call_id
                tool_args: dict = {}
                call_id = ""
                for i, tc in enumerate(pending_ai_tool_calls):
                    if tc["name"] == tool_name and i not in consumed_tc_indices:
                        tool_args = tc["args"]
                        call_id = tc.get("id", "")
                        consumed_tc_indices.add(i)
                        break
                if not tool_args:
                    tool_args = tool_input

                pending_tool_runs[run_id] = {
                    "step": iteration,
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "tool_args": tool_args,
                    "call_id": call_id,
                }

                yield {
                    "type": "thinking",
                    "data": {
                        "step": iteration,
                        "tool": tool_name,
                        "call_id": call_id,
                        "args": tool_args,
                        "observation": None,
                    },
                }

            # ---- 工具执行完成 → 推送 tool_result 事件 ----
            elif kind == "on_tool_end":
                run_id = event.get("run_id", "")
                info = pending_tool_runs.pop(run_id, None)
                output = event.get("data", {}).get("output")
                if hasattr(output, "content"):
                    observation = str(output.content)
                else:
                    observation = str(output) if output else ""

                if info:
                    logger.info(
                        "[Stream][迭代 %d] ✅ 工具执行完成: %s | "
                        "结果（前100字）: %r",
                        iteration, info["tool_name"],
                        observation[:100] + "..." if len(observation) > 100 else observation,
                    )
                    yield {
                        "type": "tool_result",
                        "data": {
                            "tool": info["tool_name"],
                            "call_id": info["call_id"],
                            "args": info["tool_args"],
                            "observation": observation,
                        },
                    }

        logger.debug("[Stream] astream_events 流结束，共经历 %d 轮迭代", iteration)

    async def _detect_interrupt(
        self, agent_graph, conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        检测图执行是否因 HITL 中间件而中断

        当 HumanInTheLoopMiddleware 对某个工具调用触发 interrupt() 后，
        astream_events 会正常结束。此时通过 aget_state 检查是否有挂起的任务，
        如果有 interrupt 信息则提取 ActionRequest 数据返回给前端。

        Args:
            agent_graph: 编译好的 LangGraph 状态图
            conversation_id: 会话 ID（用于查找 checkpointer 状态）

        Returns:
            中断信息字典（含 actions 列表），无中断时返回 None
        """
        try:
            state = await agent_graph.aget_state(
                {"configurable": {"thread_id": conversation_id}}
            )
        except Exception as e:
            logger.warning("[Interrupt] 获取状态失败: %s", e)
            return None

        # 遍历所有挂起的任务，查找 interrupt 信息
        task_count = len(state.tasks or [])
        logger.debug("[Interrupt] 检查 checkpointer 状态: %d 个挂起任务", task_count)
        for task in (state.tasks or []):
            for intr in (task.interrupts or []):
                value = intr.value
                # HITL 中间件的 interrupt value 是 HITLRequest 对象
                # 包含 action_requests（待审批的工具调用）和 review_configs（允许的决策类型）
                if hasattr(value, "action_requests"):
                    actions = []
                    for ar in value.action_requests:
                        # 找到对应的 review_config 获取允许的决策类型
                        allowed = ["approve"]
                        if hasattr(value, "review_configs"):
                            for rc in value.review_configs:
                                if rc.action_name == ar.name:
                                    allowed = rc.allowed_decisions
                                    break
                        actions.append({
                            "name": ar.name,
                            "args": ar.args,
                            "description": ar.description if hasattr(ar, "description") else "",
                            "allowed_decisions": allowed,
                        })
                    logger.info("[Interrupt] 检测到 HITL 中断: %d 个待审批 action(s)",
                                len(actions))
                    return {"actions": actions}

                # 兼容：如果 interrupt value 是字典格式
                if isinstance(value, dict) and "action_requests" in value:
                    actions = []
                    for ar in value["action_requests"]:
                        actions.append({
                            "name": ar.get("name", ""),
                            "args": ar.get("args", {}),
                            "description": ar.get("description", ""),
                            "allowed_decisions": ["approve", "edit", "reject"],
                        })
                    logger.info("[Interrupt] 检测到 HITL 中断（dict格式）: %d 个 action(s)",
                                len(actions))
                    return {"actions": actions}

        logger.debug("[Interrupt] 无 HITL 中断")
        return None

    @staticmethod
    def _extract_pending_actions_from_state(state) -> Optional[List[Dict[str, Any]]]:
        """
        从已有的 checkpointer state 中提取挂起的 HITL 审批信息

        与 _detect_interrupt() 不同，此方法直接接收 state 对象（不重复调用 aget_state），
        用于 get_history() 在加载会话历史时顺便检查是否有未处理的审批。
        这样页面刷新后，前端加载历史消息时就能恢复审批面板。

        Args:
            state: aget_state() 返回的 StateSnapshot 对象

        Returns:
            待审批的 actions 列表，无挂起审批时返回 None
        """
        for task in (state.tasks or []):
            for intr in (task.interrupts or []):
                value = intr.value
                # HITLRequest 对象（含 action_requests 和 review_configs）
                if hasattr(value, "action_requests"):
                    actions = []
                    for ar in value.action_requests:
                        allowed = ["approve"]
                        if hasattr(value, "review_configs"):
                            for rc in value.review_configs:
                                if rc.action_name == ar.name:
                                    allowed = rc.allowed_decisions
                                    break
                        actions.append({
                            "name": ar.name,
                            "args": ar.args,
                            "description": ar.description if hasattr(ar, "description") else "",
                            "allowed_decisions": allowed,
                        })
                    return actions

                # 兼容：字典格式的 interrupt value
                if isinstance(value, dict) and "action_requests" in value:
                    actions = []
                    for ar in value["action_requests"]:
                        actions.append({
                            "name": ar.get("name", ""),
                            "args": ar.get("args", {}),
                            "description": ar.get("description", ""),
                            "allowed_decisions": ["approve", "edit", "reject"],
                        })
                    return actions

        return None

    async def _auto_reject_pending_tools(
        self, conversation_id: str
    ) -> bool:
        """
        处理挂起的工具调用（用户发新消息时的兜底处理）

        场景：用户在审批面板弹出后没有处理审批，而是直接发了新消息。
        此时 checkpointer 中有一条 assistant 消息含 tool_calls 但没有对应的
        tool 结果，LLM API 会报错 "tool_calls must be followed by tool messages"。

        消息裁剪方案（保留对话历史）：
          1. 从 checkpoint 读取完整消息列表
          2. 收集所有已有 ToolMessage 响应的 tool_call_id
          3. 从后往前找最后一个有 **未响应** tool_calls 的 AIMessage
             （已完成的工具调用有对应 ToolMessage，不算未完成）
          4. 将该消息及其之后的所有消息全部裁掉
          5. 用 RemoveMessage 写回，保留中断前的所有对话历史

        Args:
            conversation_id: 会话 ID

        Returns:
            是否有挂起的中断被处理
        """
        try:
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
                logger.debug("[AutoReject] 会话 %s 无消息历史，跳过检查", conversation_id)
                return False

            logger.debug("[AutoReject] 会话 %s 当前有 %d 条消息", conversation_id, len(messages))

            # 收集所有已有 ToolMessage 响应的 tool_call_id
            responded_tool_call_ids = set()
            for msg in messages:
                if isinstance(msg, ToolMessage) and msg.tool_call_id:
                    responded_tool_call_ids.add(msg.tool_call_id)
            logger.debug("[AutoReject] 已有 %d 个工具响应", len(responded_tool_call_ids))

            # 从后往前找最后一个有未响应 tool_calls 的 AIMessage
            # 已完成的工具调用（有对应 ToolMessage）不算未完成
            interrupted_index = None
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    unmatched = [
                        tc for tc in msg.tool_calls
                        if tc["id"] not in responded_tool_call_ids
                    ]
                    if unmatched:
                        interrupted_index = i
                        unmatched_names = [tc["name"] for tc in unmatched]
                        logger.info(
                            "[AutoReject] 发现未响应的工具调用 @ 消息[%d]: %s",
                            i, unmatched_names,
                        )
                    else:
                        # 这条 AI 消息的所有 tool_calls 都已有 ToolMessage 响应
                        # 说明这是一个已完成的 ReAct 步骤，后面不会再有更早的未完成步骤
                        break

            if interrupted_index is None:
                logger.debug("[AutoReject] 无未完成的工具调用")
                return False

            # 裁剪：保留中断步骤之前的所有消息
            # interrupted_index 处的 AIMessage（含未完成的 tool_calls）及其后面的
            # 所有消息全部删除
            messages_to_remove = messages[interrupted_index:]

            logger.warning(
                "[AutoReject] 会话 %s: 保留前 %d 条消息，删除 %d 条未完成的步骤 "
                "（避免 LLM API 因 tool_calls 无响应而报错）",
                conversation_id,
                interrupted_index,
                len(messages_to_remove),
            )

            # 使用 RemoveMessage 显式删除未完成步骤的消息
            remove_ops = [RemoveMessage(id=msg.id) for msg in messages_to_remove]
            await agent_graph.aupdate_state(config, {"messages": remove_ops})
            logger.info("[AutoReject] 消息裁剪完成")

            return True

        except Exception as e:
            logger.warning("[AutoReject] 处理挂起工具调用失败: %s", e)
            return False

    # ============================================
    # 主入口：处理新消息
    # ============================================
    async def run(
        self, request: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理一次聊天请求，通过 async generator 产出 SSE 事件

        流程：
          1. 会话管理（创建/定位会话）
          2. 构建 Agent 图（含 HITL 中间件）
          3. 流式执行并产出 SSE 事件
          4. 检测是否触发 HITL 中断 → yield approval_required 事件
          5. 无中断 → yield done 事件

        Yields:
            SSE 事件字典（start / token / thinking / tool_result / approval_required / done / error）
        """
        user_message: str = request["message"]
        conversation_id: Optional[str] = request.get("conversation_id")
        selected_tools: List[str] = request.get("selected_tools", [])

        logger.info("=" * 60)
        logger.info("[Run] ===== 新的聊天请求开始 =====")
        logger.info("[Run] 用户消息: %r", user_message)
        logger.info("[Run] conversation_id=%s | selected_tools=%s",
                    conversation_id, selected_tools or "(全部)")

        # ---- Step 1: 会话管理 ----
        is_new_conversation = False
        if not conversation_id or not await self.registry.conversation_exists(
            conversation_id
        ):
            conversation_id = await self.registry.create_conversation()
            title = user_message[:20] + ("..." if len(user_message) > 20 else "")
            await self.registry.update_title(conversation_id, title)
            is_new_conversation = True
            logger.info("[Run][Step1] 创建新会话: %s (标题: %r)", conversation_id, title)
        else:
            logger.info("[Run][Step1] 使用已有会话: %s", conversation_id)

        yield {"type": "start", "data": {"conversation_id": conversation_id}}

        # ---- Step 2: 准备工具 + 构建 HITL interrupt_on 配置 ----
        tools = self.tool_registry.get_langchain_tools(selected_tools)
        # 从工具注册表获取当前选中工具的审批策略
        # 只有 policy 不为 False 的工具会出现在 interrupt_on 中
        interrupt_on = self.tool_registry.get_interrupt_on_map(selected_tools)

        tool_names = [t.name for t in tools]
        logger.info("[Run][Step2] 准备工具: %s | 需审批的工具: %s",
                    tool_names, list(interrupt_on.keys()) or "(无)")

        # ---- Step 2.5: 处理挂起的 HITL 中断 ----
        # 用户可能在上次审批未处理的情况下直接发了新消息，
        # 此时 checkpointer 中有未完成的 tool_calls，需要先自动拒绝，
        # 否则 LLM API 会因消息历史不完整而报错
        cleaned = await self._auto_reject_pending_tools(conversation_id)
        if cleaned:
            logger.warning("[Run][Step2.5] 检测到未完成的工具调用，已自动清理（消息裁剪）")
        else:
            logger.debug("[Run][Step2.5] 无未完成的工具调用，跳过清理")

        # ---- Step 3: 构建 Agent 图并流式执行 ----
        logger.info("[Run][Step3] 开始构建 Agent 图并流式执行...")
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
        logger.debug("[Run][Step3] config: recursion_limit=%d, thread_id=%s",
                     config["recursion_limit"], conversation_id)

        try:
            event_count = 0
            async for event in self._stream_agent_events(
                agent_graph,
                {"messages": [HumanMessage(content=user_message)]},
                config,
            ):
                event_count += 1
                yield event

            logger.info("[Run][Step3] 流式执行结束，共产出 %d 个事件", event_count)

            # ---- Step 4: 检查是否因 HITL 中断而停止 ----
            logger.info("[Run][Step4] 检查是否触发 HITL 中断...")
            interrupt_info = await self._detect_interrupt(agent_graph, conversation_id)
            if interrupt_info is not None:
                action_names = [a["name"] for a in interrupt_info["actions"]]
                logger.info(
                    "[Run][Step4] *** HITL 中断触发 *** 需审批的工具: %s",
                    action_names,
                )
                # 有工具需要审批 → yield approval_required 事件，流结束
                yield {
                    "type": "approval_required",
                    "data": {
                        "conversation_id": conversation_id,
                        "actions": interrupt_info["actions"],
                    },
                }
                logger.info("[Run] ===== 聊天请求结束（等待审批）=====")
                return  # 不 yield done，等 resume 完成后继续

            # ---- 无中断：获取最终回复 → yield done ----
            logger.info("[Run][Step4] 无中断，Agent 已正常完成")
            await self.registry.touch(conversation_id)
            final_content = await self._extract_final_reply(
                agent_graph, conversation_id
            )
            logger.info("[Run] 最终回复（前100字）: %r",
                        final_content[:100] + "..." if len(final_content) > 100 else final_content)
            yield {
                "type": "done",
                "data": {
                    "conversation_id": conversation_id,
                    "reply": final_content,
                },
            }
            logger.info("[Run] ===== 聊天请求完成 =====")

        except GraphRecursionError:
            logger.warning(
                "[Run] GraphRecursionError: 达到最大迭代次数 (%d)，强制结束",
                settings.MAX_ITERATIONS,
            )
            fallback = "抱歉，我需要更多步骤来回答这个问题，请尝试简化你的问题。"
            yield {"type": "token", "data": {"content": fallback}}
            yield {
                "type": "done",
                "data": {"conversation_id": conversation_id, "reply": fallback},
            }

        except Exception as e:
            logger.exception("[Run] Agent 执行异常")
            yield {"type": "error", "data": {"content": f"Agent 执行异常: {e}"}}

    # ============================================
    # 审批恢复：接收决策并继续执行
    # ============================================
    async def resume(
        self, conversation_id: str, decisions: List[Dict[str, Any]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        接收人工审批决策，恢复被 HITL 中断的 Agent 执行

        当前端用户在审批面板做出决策后调用此方法。
        通过 Command(resume=...) 将决策传回 LangGraph 中间件，
        中间件根据决策类型处理工具调用：
          - approve: 按原参数执行工具
          - edit: 用修改后的参数执行工具
          - reject: 跳过执行，将拒绝原因作为工具结果返回给 LLM
          - respond: 人工消息直接作为工具返回值

        恢复后 Agent 继续 ReAct 循环（可能产生更多工具调用或最终回答）。
        如果恢复后再次触发中断，会再次 yield approval_required 事件。

        Args:
            conversation_id: 会话 ID（对应 checkpointer 中的 thread_id）
            decisions: 人工决策列表，每项格式：
                {"type": "approve"}
                {"type": "edit", "edited_action": {"name": "...", "args": {...}}}
                {"type": "reject", "message": "拒绝原因"}
                {"type": "respond", "message": "人工回复内容"}

        Yields:
            SSE 事件字典（与 run 相同的事件类型）
        """
        # 构建 agent graph（需要相同的工具列表和 checkpointer）
        # 获取当前会话上次使用的工具（从 checkpointer 状态恢复）
        # 简化处理：使用全部已注册工具
        logger.info("=" * 60)
        logger.info("[Resume] ===== 审批恢复请求开始 =====")
        logger.info("[Resume] conversation_id=%s | 收到 %d 个决策",
                    conversation_id, len(decisions))
        for i, d in enumerate(decisions):
            logger.info("[Resume]   决策[%d]: type=%s | 详情: %s",
                        i, d.get("type"), d)

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

        # 通过 Command(resume=...) 传入人工决策，恢复图执行
        resume_input = Command(resume={"decisions": decisions})
        logger.info("[Resume] 通过 Command(resume=...) 恢复 Agent 执行...")

        try:
            event_count = 0
            async for event in self._stream_agent_events(
                agent_graph, resume_input, config,
            ):
                event_count += 1
                yield event

            logger.info("[Resume] 流式执行结束，共产出 %d 个事件", event_count)

            # 再次检查是否触发新的中断（LLM 可能又请求了需要审批的工具）
            logger.info("[Resume] 检查是否触发新的 HITL 中断...")
            interrupt_info = await self._detect_interrupt(agent_graph, conversation_id)
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
                logger.info("[Resume] ===== 审批恢复结束（等待下一轮审批）=====")
                return

            # 执行完毕
            logger.info("[Resume] Agent 已正常完成执行")
            await self.registry.touch(conversation_id)
            final_content = await self._extract_final_reply(
                agent_graph, conversation_id
            )
            logger.info("[Resume] 最终回复（前100字）: %r",
                        final_content[:100] + "..." if len(final_content) > 100 else final_content)
            yield {
                "type": "done",
                "data": {
                    "conversation_id": conversation_id,
                    "reply": final_content,
                },
            }
            logger.info("[Resume] ===== 审批恢复完成 =====")

        except GraphRecursionError:
            logger.warning("[Resume] GraphRecursionError: 达到最大迭代次数")
            fallback = "抱歉，我需要更多步骤来回答这个问题，请尝试简化你的问题。"
            yield {"type": "token", "data": {"content": fallback}}
            yield {
                "type": "done",
                "data": {"conversation_id": conversation_id, "reply": fallback},
            }

        except Exception as e:
            logger.exception("[Resume] Agent resume 异常")
            yield {"type": "error", "data": {"content": f"Agent 恢复执行异常: {e}"}}

    # ============================================
    # 辅助方法
    # ============================================
    async def _extract_final_reply(
        self, agent_graph, conversation_id: str
    ) -> str:
        """从 checkpointer 状态中提取 LLM 的最终回复文本"""
        try:
            state = await agent_graph.aget_state(
                {"configurable": {"thread_id": conversation_id}}
            )
            msg_count = len(state.values.get("messages", []))
            for msg in reversed(state.values.get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                    content = msg.content if isinstance(msg.content, str) else str(msg.content)
                    logger.debug(
                        "[FinalReply] 从 %d 条消息中提取最终回复（长度: %d 字符）",
                        msg_count, len(content),
                    )
                    return content
            logger.warning("[FinalReply] 未找到最终回复消息（共 %d 条消息）", msg_count)
        except Exception as e:
            logger.warning("[FinalReply] 无法提取最终回复: %s", e)
        return ""

    # ============================================
    # 公共查询方法（供 API 路由层调用）
    # ============================================
    async def close(self) -> None:
        """
        关闭 Agent，释放资源（会话存储连接池、检查点存储连接等）

        在应用关闭时（lifespan 阶段）调用。
        内存后端的 close() 为空操作，MySQL/文件后端会关闭连接。
        """
        await self.registry.close()
        await self.checkpoint_store.close()
        logger.info("[Agent] 存储后端已关闭")

    def get_tool_info_list(self) -> List[Dict[str, Any]]:
        """获取所有可用工具的前端展示信息"""
        return self.tool_registry.get_tool_info_list()

    async def get_conversations(self) -> List[Dict[str, Any]]:
        """获取所有会话概要列表"""
        return await self.registry.get_conversations()

    async def get_history(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定会话的完整历史

        返回消息列表和元数据。如果 checkpointer 中该会话有挂起的 HITL 审批
        （页面刷新后会话恢复场景），还会返回 pending_actions 字段，
        前端据此恢复审批面板。
        """
        meta = await self.registry.get_conversation(conversation_id)
        if meta is None:
            return None
        try:
            # 使用完整工具列表构建图，确保 HITL 中间件配置一致，
            # 否则 aget_state 无法正确解析 checkpointer 中的中断信息
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
            messages = [
                self._format_message(msg)
                for msg in state.values.get("messages", [])
            ]
            # 检测是否有挂起的 HITL 中断（用于页面刷新后恢复审批面板）
            pending_actions = self._extract_pending_actions_from_state(state)
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
        }
        if pending_actions:
            result["pending_actions"] = pending_actions
        return result

    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        删除指定会话（元数据 + 对话上下文一起删除）

        同时清理两个存储后端：
          1. conversation store: 删除会话元数据（标题、时间戳）
          2. checkpoint store:   删除对话上下文（消息历史、图状态）
        """
        # 先删 checkpoint 数据（消息历史），确保即使后面元数据删除失败，
        # 也不会留下孤立的对话上下文
        await self.checkpointer.adelete_thread(conversation_id)
        # 再删会话元数据
        return await self.registry.delete_conversation(conversation_id)

    async def clear_conversation(self, conversation_id: str) -> bool:
        """清空指定会话的消息历史（保留会话本身）"""
        if not await self.registry.conversation_exists(conversation_id):
            return False
        await self.checkpointer.adelete_thread(conversation_id)
        return True

    @staticmethod
    def _format_message(msg) -> Dict[str, Any]:
        """将 LangChain Message 对象格式化为前端展示用的字典"""
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

"""
ReAct Agent 核心引擎（基于 LangGraph）

使用 langchain.agents.create_agent 构建 ReAct 智能体，替代手动实现的 ReAct 循环。
通过 astream_events(version="v2") 实现逐 token 流式输出，保持与前端兼容的 SSE 事件格式。

架构概览：
  - agent/graph.py: 使用 create_agent 构建 LangGraph 状态图
  - agent/__init__.py: 编排层，负责会话管理、流式事件适配
  - conversation/: 会话元数据注册表（ConversationRegistry）
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
# Python 类型注解：
#   AsyncGenerator: 异步生成器类型，用于标注 async for ... yield 的函数
#   Dict / List / Any: 字典/列表/任意类型
#   Optional: 可选类型（值可能为 None）
from typing import AsyncGenerator, List, Dict, Any, Optional

# ---- LangChain 消息类型 ----
# LangChain 定义了标准化的消息类，对应 OpenAI API 中的四种角色：
#   HumanMessage  → role=user（用户发送的消息）
#   AIMessage     → role=assistant（LLM 的回复，可携带 tool_calls）
#   ToolMessage   → role=tool（工具执行后的结果，携带 tool_call_id 关联）
#   SystemMessage → role=system（系统提示词，设定 LLM 的角色和行为）
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
# InMemorySaver: 内存版检查点保存器（对话状态存在内存中，重启后丢失）
from langgraph.checkpoint.memory import InMemorySaver
# GraphRecursionError: LangGraph 状态图达到最大迭代次数时抛出的异常
# 防止 LLM 进入无限工具调用循环（类似 Java 的 StackOverflowError 防护）
from langgraph.errors import GraphRecursionError

from config import settings
from tools.registry import ToolRegistry
from tools.mcp_loader import load_mcp_tools
from conversation import ConversationRegistry
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
        """
        初始化 ReAct Agent 的所有组件

        注意：Python 的 __init__ 不能是 async 的（不支持 await），
        所以涉及异步操作（如加载 MCP 工具）的逻辑放在 initialize() 中。
        """
        # 工具注册表：注册并管理所有可用工具（内置 + MCP）
        # 使用注册表模式集中管理，方便增删查
        self.tool_registry = ToolRegistry()
        # 注册内置工具（get_location, get_datetime, get_weather）
        self.tool_registry.register_builtin_tools()
        # 会话元数据注册表（应用层：管理会话列表、标题，供前端 UI 展示）
        # 注意：消息内容本身由下面的 checkpointer 管理，这里只存标题等元数据
        self.registry = ConversationRegistry()
        # LangGraph checkpointer：框架层的对话状态管理器
        # 作用：每次 LLM 执行后自动保存对话状态到内存
        # 所有 graph 实例共享同一个 checkpointer，通过 thread_id 区分不同会话
        # 类比：类似数据库的连接池对象，所有会话共用一个，通过 ID 区分
        self.checkpointer = InMemorySaver()

    async def initialize(self) -> None:
        """
        异步初始化：加载 MCP 工具等需要异步操作的外部工具

        为什么单独定义这个方法而不在 __init__ 中加载？
          因为 Python 的 __init__ 不能是 async 的（不能用 await），
          而 MCP 工具加载需要网络通信（异步操作），所以拆成两步：
          1. __init__()  → 同步初始化（创建注册表等）
          2. await initialize()  → 异步初始化（加载 MCP 工具）

        在 FastAPI lifespan 启动时调用。
        """
        # 从 mcp_servers.json 配置文件中加载所有 MCP 服务器的工具
        mcp_tools = await load_mcp_tools(settings.MCP_CONFIG_PATH)
        if mcp_tools:
            # 将加载到的 MCP 工具批量注册到工具注册表
            self.tool_registry.register_mcp_tools(mcp_tools)
            logger.info("已加载 %d 个 MCP 工具", len(mcp_tools))

    async def reload_mcp_tools(self) -> Dict[str, Any]:
        """
        热重载 MCP 工具：清除旧的 MCP 工具后重新从配置文件加载

        由 POST /api/tools/reload 接口调用，修改 mcp_servers.json 后
        无需重启服务即可刷新 MCP 工具列表。

        Returns:
            包含 cleared（清除数量）、loaded（加载数量）、total（总数）的结果信息
        """
        # Step 1: 清除所有 MCP 工具（保留内置工具）
        cleared = self.tool_registry.clear_mcp_tools()
        logger.info("已清除 %d 个旧的 MCP 工具", cleared)

        # Step 2: 重新从配置文件加载 MCP 工具
        mcp_tools = await load_mcp_tools(settings.MCP_CONFIG_PATH)
        if mcp_tools:
            self.tool_registry.register_mcp_tools(mcp_tools)

        return {
            "cleared": cleared,
            "loaded": len(mcp_tools),
            "total": len(self.tool_registry.get_all_tools()),
        }

    # ============================================
    # 主入口：处理聊天请求并产出 SSE 事件流
    # ============================================
    async def run(
        self, request: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理一次聊天请求，通过 async generator 产出 SSE 事件

        这是一个「异步生成器」函数（async + yield），是 Python 中处理流式输出的核心模式。
        与普通函数的区别：
          - 普通函数：return 返回一个值后结束
          - 生成器函数：yield 可以多次产出值，每次 yield 后函数暂停，下次迭代时继续
          - async generator：异步版的生成器，配合 async for 使用，适合流式场景
        类比：类似 Java 的 Iterator/Stream，或 Go 的 channel

        Args:
            request: 聊天请求字典，包含 message、conversation_id、selected_tools

        Yields:
            SSE 事件字典，type 字段标识事件类型：
            - start:       对话开始（包含 conversation_id）
            - thinking:    ReAct 推理步骤（工具开始调用时立即推送，observation=None）
            - tool_result: 工具执行完毕（推送结果 observation）
            - token:       流式文本 token
            - done:        对话结束（包含最终回复）
            - error:       错误信息
        """
        # 从请求字典中提取各字段（Python 字典取值方式）
        user_message: str = request["message"]           # 必有字段，直接用 []
        conversation_id: Optional[str] = request.get("conversation_id")  # 可选字段，用 get() 安全取值
        selected_tools: List[str] = request.get("selected_tools", [])     # 默认为空列表

        # ---- Step 1: 会话管理 ----
        # 如果没有传入 conversation_id，或者传入的 ID 不存在，则创建新会话
        if not conversation_id or not await self.registry.conversation_exists(
            conversation_id
        ):
            conversation_id = await self.registry.create_conversation()
            # 用用户消息的前20个字符作为会话标题（类似微信聊天列表的标题）
            title = user_message[:20] + ("..." if len(user_message) > 20 else "")
            await self.registry.update_title(conversation_id, title)

        # 第一个 yield：告诉前端"对话已开始"，并返回会话 ID
        yield {"type": "start", "data": {"conversation_id": conversation_id}}

        # ---- Step 2: 准备工具 ----
        # 根据前端选择的工具名称，从注册表中获取对应的 LangChain Tool 对象
        tools = self.tool_registry.get_langchain_tools(selected_tools)

        logger.info(
            "收到请求: message=%r, selected_tools=%s, resolved_tools=%s",
            user_message, selected_tools, [t.name for t in tools],
        )

        # ---- Step 3: 构建 Agent 图并流式执行 ----
        # 每次请求都构建一个新的 agent graph（因为工具列表可能不同）
        # 但所有 graph 共享同一个 checkpointer，通过 thread_id 关联同一会话的历史
        agent_graph = build_agent_graph(
            tools=tools,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            checkpointer=self.checkpointer,
        )

        # ---- 流式追踪变量 ----
        # 这些变量用于追踪 LangGraph 事件流中的状态，以便组装成前端需要的 SSE 格式
        iteration = 0            # 当前是第几次 LLM 推理（ReAct 的一轮迭代）
        final_content = ""       # LLM 的最终回答文本
        # pending_tool_runs: 记录"已开始但未结束"的工具调用
        #   key = run_id（LangGraph 为每次工具调用分配的唯一标识）
        #   value = 工具调用信息字典（步骤号、工具名、输入参数）
        #   用途：on_tool_start 时存入，on_tool_end 时取出，将两者配对
        pending_tool_runs: Dict[str, Dict[str, Any]] = {}
        # pending_ai_tool_calls: 缓存最近一次 LLM 输出中的 tool_calls
        #   用途：on_tool_end 事件中没有参数信息，需要从 AI 消息的 tool_calls 中查找
        pending_ai_tool_calls: List[Dict[str, Any]] = []
        # consumed_tc_indices: 记录已被 on_tool_start 消费的 tool_call 索引
        # 不能直接 pop 原始列表，因为 ai_msg.tool_calls 是 checkpointer 中
        # AIMessage 的同一对象引用，修改它会破坏对话历史，导致第二轮 LLM 调用时报错：
        # "Messages with role 'tool' must be a response to a preceding message with 'tool_calls'"
        consumed_tc_indices: set = set()

        try:
            # ---- 核心：通过 astream_events 流式执行 Agent 图 ----
            # astream_events 是 LangGraph 的流式执行 API（version="v2"）
            # 它会逐个产出事件字典，涵盖 Agent 执行过程中的每一步：
            #   on_chat_model_start → LLM 开始推理
            #   on_chat_model_stream → LLM 流式输出 token
            #   on_chat_model_end → LLM 推理结束（可能产生 tool_calls）
            #   on_tool_start → 开始执行工具
            #   on_tool_end → 工具执行完成
            #
            # async for 是 Python 的异步迭代语法：
            #   每产出一个事件，循环体就执行一次，可以实时处理每个事件
            async for event in agent_graph.astream_events(
                # 关键：仅传入当前用户消息，checkpointer 自动拼接历史消息
                # 不需要手动传递完整的对话历史，框架通过 thread_id 自动管理
                {"messages": [HumanMessage(content=user_message)]},
                version="v2",
                config={
                    # recursion_limit: 状态图最大迭代次数（超过后抛出 GraphRecursionError）
                    # 乘以 2 是因为 ReAct 的一轮迭代包含 model 节点 + tools 节点两步
                    "recursion_limit": settings.MAX_ITERATIONS * 2 + 5,
                    # thread_id: checkpointer 通过它关联同一会话的所有历史
                    # 同一个 conversation_id 的多次请求共享对话上下文
                    "configurable": {"thread_id": conversation_id},
                },
            ):
                # event 是一个字典，"event" 字段标识事件类型
                kind = event.get("event")

                # ---- 事件1: LLM 调用开始 → 重置迭代状态 ----
                if kind == "on_chat_model_start":
                    iteration += 1          # ReAct 迭代计数 +1
                    pending_ai_tool_calls = []  # 清空上一轮的 tool_calls 缓存
                    consumed_tc_indices = set()  # 清空已消费索引

                # ---- 事件2: 流式文本 token → 实时推送给前端 ----
                # 这是实现"打字机效果"的关键：LLM 每生成一个 token 就立即推送
                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]  # chunk 是 AIMessageChunk（部分消息）
                    if chunk.content:  # 只有有实际文本内容时才推送
                        yield {
                            "type": "token",
                            "data": {"content": chunk.content},
                        }

                # ---- 事件3: LLM 调用结束 → 缓存 tool_calls 供后续关联 ----
                elif kind == "on_chat_model_end":
                    ai_msg: AIMessage = event["data"]["output"]
                    # tool_calls 是 LLM 决定要调用的工具列表
                    # 格式如: [{"name": "get_weather", "args": {"city": "杭州"}, "id": "call_xxx"}]
                    if ai_msg.tool_calls:
                        pending_ai_tool_calls = ai_msg.tool_calls

                # ---- 事件4: 工具开始执行 → 立即推送工具信息给前端 ----
                # 这样前端可以立刻看到"正在调用 xxx 工具"，而不用等工具执行完毕
                # 后续迭代可在此基础上引入人机协同（用户批准工具执行）
                elif kind == "on_tool_start":
                    run_id = event.get("run_id", "")
                    tool_name = event.get("name", "")
                    tool_input = event.get("data", {}).get("input", {})

                    # 从缓存的 AI tool_calls 中匹配参数和唯一 call_id
                    # 注意：LLM 可能在同一轮中对同一工具发起多次调用（如查杭州天气 + 查北京天气），
                    # 用 consumed_tc_indices 跳过已消费的条目，避免同名重复匹配
                    # 不能用 pop 修改原始列表，否则会破坏 checkpointer 中的 AIMessage
                    tool_args: dict = {}
                    call_id = ""
                    for i, tc in enumerate(pending_ai_tool_calls):
                        if tc["name"] == tool_name and i not in consumed_tc_indices:
                            tool_args = tc["args"]
                            call_id = tc.get("id", "")
                            consumed_tc_indices.add(i)  # 标记为已消费
                            break
                    if not tool_args:
                        tool_args = tool_input

                    # 暂存工具调用信息（含 call_id），等待 on_tool_end 配对
                    pending_tool_runs[run_id] = {
                        "step": iteration,
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "tool_args": tool_args,
                        "call_id": call_id,
                    }

                    # 立即推送 thinking 事件（observation=None 表示尚未返回结果）
                    # 前端收到后可立即展示"正在调用 xxx 工具..."的加载状态
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

                # ---- 事件5: 工具执行完成 → 推送工具结果给前端 ----
                elif kind == "on_tool_end":
                    run_id = event.get("run_id", "")
                    # pop(): 从字典中取出并删除，配对 start 和 end 事件
                    info = pending_tool_runs.pop(run_id, None)

                    # 提取工具的输出结果（观察结果）
                    # LangChain 的工具输出可能是 ToolMessage 对象，也可能是普通值
                    output = event.get("data", {}).get("output")
                    if hasattr(output, "content"):
                        # hasattr: 检查对象是否有某个属性（Python 的鸭子类型哲学）
                        observation = str(output.content)
                    else:
                        observation = str(output) if output else ""

                    if info:
                        # yield tool_result 事件：告诉前端"工具执行完毕，这是结果"
                        # call_id 与 thinking 事件中的 call_id 一致，前端据此配对
                        yield {
                            "type": "tool_result",
                            "data": {
                                "tool": info["tool_name"],
                                "call_id": info["call_id"],
                                "args": info["tool_args"],
                                "observation": observation,
                            },
                        }

            # ---- 流结束：从 checkpointer 状态中获取最终回复 ----
            # aget_state: 获取 checkpointer 中保存的最新对话状态
            # 包含该会话的所有历史消息（包括本次对话新增的）
            state = await agent_graph.aget_state(
                {"configurable": {"thread_id": conversation_id}}
            )
            final_content = ""
            # 从消息列表的末尾往前找，找到最后一条不含 tool_calls 的 AIMessage
            # 这就是 LLM 的最终回答（不含工具调用的纯文本回复）
            for msg in reversed(state.values.get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                    # isinstance: Python 的类型检查（类似 Java 的 instanceof）
                    final_content = (
                        msg.content if isinstance(msg.content, str)
                        else str(msg.content)
                    )
                    break

            # 更新会话的 updated_at 时间戳（让它在会话列表中排到前面）
            await self.registry.touch(conversation_id)

        except GraphRecursionError:
            # ReAct 循环达到最大迭代次数 → 提示用户简化问题
            fallback = "抱歉，我需要更多步骤来回答这个问题，请尝试简化你的问题。"
            yield {"type": "token", "data": {"content": fallback}}
            final_content = fallback

        except Exception as e:
            # 捕获所有其他异常（Exception 是所有常规异常的基类）
            logger.exception("Agent 执行异常")  # exception() 会自动记录堆栈信息
            yield {
                "type": "error",
                "data": {"content": f"Agent 执行异常: {e}"},
            }
            return  # return 会终止生成器，后续不再 yield

        # ---- Step 4: 发送完成事件 ----
        # 告诉前端"对话已结束"，携带会话 ID 和最终回复
        yield {
            "type": "done",
            "data": {
                "conversation_id": conversation_id,
                "reply": final_content,
            },
        }

    # ============================================
    # 公共查询方法（供 API 路由层调用）
    # ============================================
    def get_tool_info_list(self) -> List[Dict[str, Any]]:
        """
        获取所有可用工具的前端展示信息

        Returns:
            工具信息列表，每项包含 name（名称）、description（描述）、parameters（参数 Schema）
        """
        return self.tool_registry.get_tool_info_list()

    async def get_conversations(self) -> List[Dict[str, Any]]:
        """
        获取所有会话概要列表

        Returns:
            会话列表，每项包含 id、title、created_at、updated_at
            按 updated_at 倒序排列（最近更新的在前）
        """
        return await self.registry.get_conversations()

    async def get_history(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定会话的完整历史

        消息来源：LangGraph checkpointer（存储了所有对话消息）
        元数据来源：ConversationRegistry（存储了标题、时间戳）
        两者组合后返回完整的会话信息。

        Args:
            conversation_id: 会话 ID

        Returns:
            包含会话元数据和消息历史的字典；会话不存在时返回 None
        """
        # 先从应用层注册表获取会话元数据
        meta = await self.registry.get_conversation(conversation_id)
        if meta is None:
            return None

        # 再从 LangGraph checkpointer 状态中读取消息历史
        try:
            # 构建临时 graph 以访问 checkpointer 中的状态
            # 这里 tools=[] 因为只是读历史，不需要执行工具
            agent_graph = build_agent_graph(
                tools=[],
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                checkpointer=self.checkpointer,
            )
            # aget_state: 异步获取 checkpointer 中指定 thread_id 的最新状态
            state = await agent_graph.aget_state(
                {"configurable": {"thread_id": conversation_id}}
            )
            # 将 LangChain Message 对象转换为前端可展示的字典格式
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
        """
        删除指定会话

        注意：目前只删除 ConversationRegistry 中的元数据，
        checkpointer 中的消息历史不会被删除（内存中仍存在，直到进程重启）。

        Args:
            conversation_id: 要删除的会话 ID

        Returns:
            True 表示删除成功，False 表示会话不存在
        """
        return await self.registry.delete_conversation(conversation_id)

    async def clear_conversation(self, conversation_id: str) -> bool:
        """
        清空指定会话的消息历史（保留会话本身）

        通过 InMemorySaver.adelete_thread 删除 checkpointer 中该会话的所有
        checkpoint 数据，使 LLM 丧失该会话的上下文记忆。
        会话元数据（标题、时间戳）保留在 ConversationRegistry 中，
        前端侧边栏的会话列表不受影响。

        清空后用户再发消息时，Agent 会以空白上下文开始对话。

        Args:
            conversation_id: 要清空的会话 ID

        Returns:
            True 表示清空成功，False 表示会话不存在
        """
        if not await self.registry.conversation_exists(conversation_id):
            return False
        await self.checkpointer.adelete_thread(conversation_id)
        return True

    @staticmethod
    def _format_message(msg) -> Dict[str, Any]:
        """
        将 LangChain Message 对象格式化为前端展示用的字典

        @staticmethod 表示这是一个静态方法：
          - 不需要 self 参数（不访问实例属性）
          - 可以通过类名直接调用：ReActAgent._format_message(msg)
          - 适合纯粹的数据转换逻辑

        转换映射：
          - HumanMessage  → role=user（用户消息）
          - AIMessage     → role=assistant（AI 回复，可携带 tool_calls）
          - ToolMessage   → role=tool（工具执行结果）
          - SystemMessage → role=system（系统提示词）

        Args:
            msg: LangChain 的 Message 对象（HumanMessage / AIMessage / ToolMessage / SystemMessage）

        Returns:
            前端可展示的字典，包含 role 和 content 字段
        """
        # isinstance() 检查对象类型，类似 Java 的 instanceof
        if isinstance(msg, HumanMessage):
            return {"role": "user", "content": str(msg.content)}
        elif isinstance(msg, AIMessage):
            # 构建基础结果字典
            result: Dict[str, Any] = {
                "role": "assistant",
                "content": str(msg.content) if msg.content else "",
            }
            # AIMessage 可能携带 tool_calls（LLM 请求调用工具）
            # 格式: [{"id": "call_xxx", "name": "get_weather", "args": {"city": "杭州"}}]
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
                # getattr(obj, attr, default): 安全获取属性值，不存在时返回 default
                "tool_call_id": getattr(msg, "tool_call_id", ""),
            }
        elif isinstance(msg, SystemMessage):
            return {"role": "system", "content": str(msg.content)}
        else:
            # 未知消息类型：兜底处理，当作用户消息返回
            return {"role": "user", "content": str(msg.content)}

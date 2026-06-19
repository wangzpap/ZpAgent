"""
LangGraph Agent 图工厂

使用 langchain.agents.create_agent 构建 ReAct 智能体图，
替代手动实现的 ReAct 循环。

核心优势：
  - 框架级 ReAct 循环（推理 → 工具调用 → 观察 → 循环 → 最终回答）
  - 内置 ToolNode 并行执行工具
  - 使用 InMemorySaver checkpointer 自动管理对话状态（跨请求记忆）
  - 支持 interrupt_before / interrupt_after（human-in-the-loop）
  - 与 astream_events(v2) 天然兼容，支持逐 token 流式输出

对话记忆：
  通过 InMemorySaver checkpointer + thread_id 自动管理，无需手动传递消息历史。
  参考: https://langchain-doc.cn/v1/python/langchain/short-term-memory.html
"""

import logging
# Python 类型注解导入：
#   List: 列表类型，如 List[str] 表示字符串列表
#   Optional: 可选类型，Optional[X] 等价于 X | None（值可以是 X 或 None）
#   Sequence: 序列类型（List/Tuple 等的抽象父类）
from typing import List, Optional, Sequence

# ---- LangChain / LangGraph 相关导入 ----
# create_agent: LangChain 的高级工厂函数，一键创建完整的 ReAct Agent 状态图
#   内部自动创建: model 节点（LLM推理）+ tools 节点（工具执行）+ 条件边（循环判断）
from langchain.agents import create_agent
# BaseTool: LangChain 工具的基类，所有工具（@tool 装饰器创建的、MCP 加载的）都是 BaseTool 的子类
from langchain.tools import BaseTool
# InMemorySaver: LangGraph 的内存检查点保存器
#   作用：每次 LLM 执行后自动保存对话状态到内存
#   效果：同一个 thread_id 的多次请求自动共享对话历史（跨请求记忆）
#   缺点：进程重启后丢失，生产环境可换成 SqliteSaver / PostgresSaver
from langgraph.checkpoint.memory import InMemorySaver
# CompiledStateGraph: LangGraph 编译后的状态图
#   状态图 = 节点（Node）+ 边（Edge）组成的有向图
#   "编译"意味着图的结构已经确定，可以直接传入输入数据执行
#   可以理解为：状态机 / 有限自动机
from langgraph.graph.state import CompiledStateGraph

from llm import create_llm

# Python 标准库的日志记录器，比 print 更适合生产环境
# 支持日志级别（DEBUG/INFO/WARNING/ERROR）和格式化输出
logger = logging.getLogger(__name__)

# 默认系统提示词：告诉 LLM 它的角色和行为准则
DEFAULT_SYSTEM_PROMPT = "你是一个智能助手。"


def build_agent_graph(
    tools: Optional[Sequence[BaseTool]] = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    checkpointer=None,
    interrupt_before: Optional[List[str]] = None,
) -> CompiledStateGraph:
    """
    构建 ReAct Agent 图（工厂函数）

    这个函数的职责是将 LLM + 工具 + 检查点保存器 组装成一个可执行的 LangGraph 状态图。
    构建出的状态图内部包含以下节点和流转逻辑：

        ┌────────────────────────────────────────────┐
        │  model 节点: LLM 接收消息并推理              │
        │      ↓                                     │
        │  条件边判断: LLM 是否产生了 tool_calls？      │
        │      ├── 是 → tools 节点: 执行工具调用       │
        │      │         ↓                           │
        │      │       回到 model 节点（继续推理）      │
        │      └── 否 → 结束（输出最终回答）            │
        └────────────────────────────────────────────┘

    Args:
        tools: 可用工具列表。为空时 Agent 仅做纯文本对话（图中不包含 tools 节点）。
        system_prompt: 系统提示词，作为首条 SystemMessage 注入 LLM 上下文。
        checkpointer: LangGraph 检查点保存器。默认使用 InMemorySaver（内存实现），
            通过 thread_id 自动管理对话状态，实现跨请求的会话记忆。
            可替换为 SqliteSaver / PostgresSaver 实现持久化。
        interrupt_before: 在指定节点执行前中断图执行（human-in-the-loop）。
            例如 ["tools"] 表示每次执行工具前暂停，等人类确认。

    Returns:
        编译好的 LangGraph 状态图，可直接调用 astream_events 流式执行。
    """
    # 将 Sequence 类型转为 list（因为 create_agent 需要 list 类型）
    tool_list = list(tools) if tools else []

    # 默认使用 InMemorySaver：自动管理对话状态（跨请求记忆）
    # 所有通过同一个 checkpointer 创建的 graph 实例共享状态数据
    if checkpointer is None:
        checkpointer = InMemorySaver()

    # create_agent: LangChain 提供的高级工厂函数
    # 内部做了很多事情：
    #   1. 创建 model 节点：绑定 LLM 和工具（bind_tools）
    #   2. 创建 tools 节点：ToolNode 负责实际执行工具调用
    #   3. 创建条件边：根据 LLM 输出判断是否需要调用工具
    #   4. 注入 system_prompt 为第一条 SystemMessage
    #   5. 绑定 checkpointer 用于状态持久化
    #   6. 编译整个图并返回
    agent = create_agent(
        model=create_llm(),
        tools=tool_list,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
    )

    logger.debug(
        "Agent 图已构建: tools=%d, checkpointer=%s",
        len(tool_list),
        # type().__name__ 获取对象的类名（如 "InMemorySaver"）
        type(checkpointer).__name__,
    )

    return agent

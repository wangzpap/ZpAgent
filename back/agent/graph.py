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
from typing import List, Optional, Sequence

from langchain.agents import create_agent
from langchain.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from llm import create_llm

logger = logging.getLogger(__name__)

# 默认系统提示词
DEFAULT_SYSTEM_PROMPT = "你是一个智能助手。"


def build_agent_graph(
    tools: Optional[Sequence[BaseTool]] = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    checkpointer=None,
    interrupt_before: Optional[List[str]] = None,
) -> CompiledStateGraph:
    """
    构建 ReAct Agent 图

    使用 langchain.agents.create_agent 创建编译好的状态图，
    支持工具调用循环、检查点持久化和中断点配置。

    Args:
        tools: 可用工具列表。为空时 Agent 仅做纯文本对话（无工具节点）。
        system_prompt: 系统提示词，作为首条 SystemMessage 注入 LLM 上下文。
        checkpointer: LangGraph 检查点保存器。默认使用 InMemorySaver（内存实现），
            通过 thread_id 自动管理对话状态，实现跨请求的会话记忆。
            可替换为 SqliteSaver / PostgresSaver 实现持久化。
        interrupt_before: 在指定节点执行前中断（human-in-the-loop）。

    Returns:
        编译好的 LangGraph 状态图，可直接调用 astream_events。
    """
    tool_list = list(tools) if tools else []

    # 默认使用 InMemorySaver：自动管理对话状态（跨请求记忆）
    if checkpointer is None:
        checkpointer = InMemorySaver()

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
        type(checkpointer).__name__,
    )

    return agent

"""
LangGraph Agent 图工厂

使用 langchain.agents.create_agent 构建 ReAct 智能体图，
替代手动实现的 ReAct 循环。

核心优势：
  - 框架级 ReAct 循环（推理 → 工具调用 → 观察 → 循环 → 最终回答）
  - 内置 ToolNode 并行执行工具
  - 使用 InMemorySaver checkpointer 自动管理对话状态（跨请求记忆）
  - HumanInTheLoopMiddleware 实现按工具粒度的审批控制
  - 与 astream_events(v2) 天然兼容，支持逐 token 流式输出

人机交互（Human-in-the-Loop）：
  通过 HumanInTheLoopMiddleware 中间件实现：
    - 每个工具可独立配置审批策略（自动执行 / 需要审批 / 精细控制）
    - LLM 产生 tool_calls 后，中间件自动判断哪些需要人工审批
    - 需要审批的工具触发 interrupt()，暂停图执行，等待前端提交决策
    - 前端通过 Command(resume=...) 恢复执行
"""

import logging
from typing import List, Optional, Sequence, Dict, Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from llm import create_llm

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = "你是一个智能助手。"


def build_agent_graph(
    tools: Optional[Sequence[BaseTool]] = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    checkpointer=None,
    interrupt_before: Optional[List[str]] = None,
    interrupt_on: Optional[Dict[str, Any]] = None,
) -> CompiledStateGraph:
    """
    构建 ReAct Agent 图（工厂函数）

    将 LLM + 工具 + 检查点保存器 + HITL 中间件 组装成可执行的 LangGraph 状态图。

    状态图内部流转：
        model 节点 → 条件边（有 tool_calls?）→ tools 节点 → 回到 model → ...
                                        ↘ 无 → 结束

    Args:
        tools: 可用工具列表。为空时 Agent 仅做纯文本对话。
        system_prompt: 系统提示词。
        checkpointer: LangGraph 检查点保存器。默认 InMemorySaver。
        interrupt_before: 图级别中断（在指定节点前暂停），用于粗粒度控制。
        interrupt_on: HITL 中间件的 interrupt_on 配置字典。
            key=工具名称, value=审批策略：
              - True: 需要审批，支持全部决策类型
              - dict: 精细配置，如 {"allowed_decisions": ["approve", "reject"]}
            不在字典中的工具自动执行。

    Returns:
        编译好的 LangGraph 状态图
    """
    tool_list = list(tools) if tools else []

    if checkpointer is None:
        checkpointer = InMemorySaver()

    logger.info(
        "[Graph] 开始构建 Agent 图 | tools=%d | checkpointer=%s",
        len(tool_list),
        type(checkpointer).__name__,
    )
    if tool_list:
        logger.debug(
            "[Graph] 工具列表: %s",
            [t.name for t in tool_list],
        )

    # ---- 构建中间件列表 ----
    # HumanInTheLoopMiddleware：当 interrupt_on 非空时启用
    # 中间件在 LLM 产出 tool_calls 后（after_model 钩子）检查每个工具调用，
    # 对需要审批的工具触发 interrupt()，暂停图执行等待人工决策
    middleware_list = []
    if interrupt_on:
        middleware_list.append(
            HumanInTheLoopMiddleware(
                interrupt_on=interrupt_on,
                description_prefix="以下工具调用需要您的审批确认",
            )
        )
        logger.info(
            "[Graph] HITL 中间件已启用，需审批的工具: %s",
            list(interrupt_on.keys()),
        )
    else:
        logger.debug("[Graph] 无 HITL 审批配置，所有工具将自动执行")

    agent = create_agent(
        model=create_llm(),
        tools=tool_list,
        system_prompt=system_prompt,
        middleware=middleware_list,
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
    )

    logger.info(
        "[Graph] Agent 图构建完成 | tools=%d | middleware=%d",
        len(tool_list),
        len(middleware_list),
    )

    return agent

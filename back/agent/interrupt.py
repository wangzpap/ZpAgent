"""
HITL（Human-in-the-Loop）中断处理

职责：
  1. 检测图执行是否因 HITL 中间件而中断（detect_interrupt）
  2. 从已有 state 中提取挂起的审批信息（extract_pending_actions_from_state）
  3. 清理过期的未完成工具调用（auto_reject_pending_tools）

中断流程：
  LLM 产生 tool_calls → 中间件触发 interrupt() → astream_events 正常结束
  → 调用方通过 aget_state 检测到中断 → 提取 ActionRequest → 前端展示审批面板
"""

import logging
from typing import Dict, Any, List, Optional

from langchain_core.messages import AIMessage, ToolMessage, RemoveMessage

from agent.graph import build_agent_graph, DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


async def detect_interrupt(
    agent_graph, conversation_id: str
) -> Optional[Dict[str, Any]]:
    """
    检测图执行是否因 HITL 中间件而中断。

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

    actions = _parse_interrupt_actions(state)
    if actions:
        logger.info("[Interrupt] 检测到 HITL 中断: %d 个待审批 action(s)", len(actions))
        return {"actions": actions}

    logger.debug("[Interrupt] 无 HITL 中断")
    return None


def extract_pending_actions_from_state(state) -> Optional[List[Dict[str, Any]]]:
    """
    从已有的 checkpointer state 中提取挂起的 HITL 审批信息。

    与 detect_interrupt() 不同，此函数直接接收 state 对象（不重复调用 aget_state），
    用于 get_history() 在加载会话历史时顺便检查是否有未处理的审批。
    这样页面刷新后，前端加载历史消息时就能恢复审批面板。

    Args:
        state: aget_state() 返回的 StateSnapshot 对象

    Returns:
        待审批的 actions 列表，无挂起审批时返回 None
    """
    return _parse_interrupt_actions(state) or None


async def auto_reject_pending_tools(
    tool_registry,
    checkpointer,
    conversation_id: str,
) -> bool:
    """
    处理挂起的工具调用（用户发新消息时的兜底清理）。

    场景：用户在审批面板弹出后没有处理审批，而是直接发了新消息。
    此时 checkpointer 中有一条 AIMessage 含 tool_calls 但没有对应的
    ToolMessage 响应，LLM API 会报错 "tool_calls must be followed by tool messages"。

    消息裁剪方案（保留对话历史）：
      1. 从 checkpoint 读取完整消息列表
      2. 收集所有已有 ToolMessage 响应的 tool_call_id
      3. 从后往前找最后一个有未响应 tool_calls 的 AIMessage
      4. 将该消息及其之后的所有消息全部裁掉（RemoveMessage 墓碑）
      5. 保留中断前的所有对话历史

    Args:
        tool_registry: 工具注册表（用于构建 graph）
        checkpointer: LangGraph checkpointer 实例
        conversation_id: 会话 ID

    Returns:
        是否有挂起的中断被处理
    """
    try:
        tools = tool_registry.get_langchain_tools()
        interrupt_on = tool_registry.get_interrupt_on_map()
        agent_graph = build_agent_graph(
            tools=tools,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            checkpointer=checkpointer,
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
                    # 所有 tool_calls 都已有响应，后面不会再有更早的未完成步骤
                    break

        if interrupted_index is None:
            logger.debug("[AutoReject] 无未完成的工具调用")
            return False

        # 裁剪：删除中断步骤及其之后的所有消息
        messages_to_remove = messages[interrupted_index:]
        logger.warning(
            "[AutoReject] 会话 %s: 保留前 %d 条消息，删除 %d 条未完成的步骤",
            conversation_id, interrupted_index, len(messages_to_remove),
        )

        remove_ops = [RemoveMessage(id=msg.id) for msg in messages_to_remove]
        await agent_graph.aupdate_state(config, {"messages": remove_ops})
        logger.info("[AutoReject] 消息裁剪完成")
        return True

    except Exception as e:
        logger.warning("[AutoReject] 处理挂起工具调用失败: %s", e)
        return False


# ============================================
# 内部工具函数
# ============================================

def _parse_interrupt_actions(state) -> List[Dict[str, Any]]:
    """
    从 state 的挂起任务中解析 HITL interrupt 的 action 列表。

    兼容两种 interrupt value 格式：
      - HITLRequest 对象（含 action_requests + review_configs 属性）
      - 字典格式（含 "action_requests" 键）
    """
    for task in (state.tasks or []):
        for intr in (task.interrupts or []):
            value = intr.value

            # HITLRequest 对象格式
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

            # 字典格式（兼容）
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

    return []

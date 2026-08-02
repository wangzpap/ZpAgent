"""
流式事件适配层

将 LangGraph astream_events(v2) 的内部事件流转换为前端兼容的 SSE 事件字典。
run()（新消息）和 resume()（审批恢复）共享此逻辑。

事件映射：
  on_chat_model_start  → 重置迭代计数（内部状态）
  on_chat_model_stream → yield token 事件（流式文本）
  on_chat_model_end    → 缓存 tool_calls（内部状态）
  on_tool_start        → yield thinking 事件（工具开始调用）
  on_tool_end          → yield tool_result 事件（工具执行完毕）

当 HITL 中间件触发 interrupt 时，astream_events 会正常结束（不抛异常），
由调用方（core.py 的 run/resume）通过 aget_state 检测中断。
"""

import logging
import time
from typing import AsyncGenerator, Dict, Any, List

from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


async def stream_agent_events(
    agent_graph,
    input_data: dict,
    config: dict,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    遍历 Agent 图的 astream_events 流，将内部事件转换为前端 SSE 格式。

    每次 yield 一个 SSE 事件字典，由 API 层转为 SSE 文本推送给前端。

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
    token_count = 0

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
                # 工具开始执行的高精度时间戳。选用 time.perf_counter()（单调递增、
                # 纳秒级精度、不受系统时钟回拨影响），是测量时间间隔的首选时钟。
                # 该值随 run_id 存入 pending_tool_runs，on_tool_end 通过同一 run_id
                # 取回并做差，即可得到本次工具的真实执行耗时（含并发场景下互不串扰）。
                "start_ts": time.perf_counter(),
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

            # 判定工具是否成功：LangGraph ToolNode 默认 handle_tool_errors=True，
            # 工具抛错会被捕获并产出 status="error" 的 ToolMessage（仍走 on_tool_end，
            # 错误文本作为 observation 回传给 LLM）。因此这里以 output.status 为准：
            # 显式为 "error" 记为失败，其余（"success" 或无该属性）一律视为成功。
            tool_ok = getattr(output, "status", "success") != "error"

            if info:
                # 计算工具执行耗时（单位毫秒）：on_tool_end 与 on_tool_start 的
                # perf_counter 差值 ×1000，round 取整避免浮点噪声。start_ts 理论上
                # 必然存在（on_tool_start 已写入），此处仍做 None 防御，缺失时下发
                # None，前端据此隐藏耗时而非显示错误值。
                start_ts = info.get("start_ts")
                duration_ms = (
                    round((time.perf_counter() - start_ts) * 1000)
                    if start_ts is not None else None
                )
                logger.info(
                    "[Stream][迭代 %d] %s 工具执行完成: %s | 耗时 %sms | "
                    "结果（前100字）: %r",
                    iteration, "✅" if tool_ok else "❌",
                    info["tool_name"], duration_ms,
                    observation[:100] + "..." if len(observation) > 100 else observation,
                )
                yield {
                    "type": "tool_result",
                    "data": {
                        "tool": info["tool_name"],
                        "call_id": info["call_id"],
                        "args": info["tool_args"],
                        "observation": observation,
                        # step（ReAct 轮次）与 duration_ms（耗时）随结果一并下发，
                        # 前端工具卡片据此渲染步骤编号徽标与耗时标签。
                        "step": info.get("step"),
                        "duration_ms": duration_ms,
                        # ok：工具是否成功。前端据此切换状态点颜色（成功绿/失败红）。
                        "ok": tool_ok,
                    },
                }

    logger.debug("[Stream] astream_events 流结束，共经历 %d 轮迭代", iteration)

"""
API 路由（统一入口）

合并聊天（SSE 流式输出）、消息历史查询、会话管理和工具列表的所有接口。
所有路由统一使用 /api 前缀。

接口列表：
  POST /api/chat                      — 聊天（SSE 流式输出）
  GET  /api/messages/{conversation_id} — 获取会话消息历史
  GET  /api/conversations              — 获取所有会话列表
  GET  /api/conversations/{id}         — 获取会话详情
  DELETE /api/conversations/{id}       — 删除会话
  GET  /api/tools                      — 获取可用工具列表
"""

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

from models import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ============================================
# 聊天接口（SSE 流式输出）
# ============================================
@router.post("/chat")
async def chat(request: ChatRequest, req: Request):
    """
    聊天接口 — 通过 Server-Sent Events 流式返回 Agent 响应

    SSE 事件类型：
      - start:    对话开始（包含 conversation_id）
      - token:    流式文本 token
      - thinking: ReAct 推理步骤（工具调用/观察结果）
      - done:     对话结束
      - error:    错误信息
    """
    agent = req.app.state.agent

    async def event_stream():
        """将 Agent 的事件字典转换为 SSE 格式字符串"""
        try:
            async for event in agent.run(request.model_dump()):
                event_type = event["type"]
                event_data = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: {event_type}\ndata: {event_data}\n\n"
        except Exception as e:
            logger.exception("聊天流异常")
            error_data = json.dumps(
                {"content": f"服务内部错误: {e}"}, ensure_ascii=False
            )
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


# ============================================
# 消息历史
# ============================================
@router.get("/messages/{conversation_id}")
async def get_messages(conversation_id: str, req: Request):
    """获取指定会话的消息历史，不存在时返回错误信息"""
    agent = req.app.state.agent
    history = await agent.get_history(conversation_id)
    if history is None:
        return {"error": "会话不存在", "conversation_id": conversation_id}
    return history


# ============================================
# 会话管理
# ============================================
@router.get("/conversations")
async def list_conversations(req: Request):
    """获取所有会话列表（按更新时间倒序）"""
    agent = req.app.state.agent
    return await agent.get_conversations()


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, req: Request):
    """获取指定会话的详细信息（包含消息历史），不存在返回 404"""
    agent = req.app.state.agent
    conversation = await agent.get_history(conversation_id)
    if conversation is None:
        return JSONResponse(
            status_code=404,
            content={"error": "会话不存在", "conversation_id": conversation_id},
        )
    return conversation


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, req: Request):
    """删除指定会话，不存在返回 404"""
    agent = req.app.state.agent
    success = await agent.delete_conversation(conversation_id)
    if not success:
        return JSONResponse(
            status_code=404,
            content={"error": "会话不存在", "conversation_id": conversation_id},
        )
    return {"success": True}


# ============================================
# 工具列表
# ============================================
@router.get("/tools")
async def list_tools(req: Request):
    """获取所有可用工具列表（名称、描述、参数 Schema）"""
    agent = req.app.state.agent
    return agent.get_tool_info_list()

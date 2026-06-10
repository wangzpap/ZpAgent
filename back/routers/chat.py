"""
聊天路由

提供聊天（SSE 流式输出）和消息历史查询接口。
聊天接口通过 Server-Sent Events 实时推送 Agent 的思考过程和回复内容。
"""

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from models import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest, req: Request):
    """
    聊天接口（SSE 流式输出）

    前端通过 POST 发送消息，后端通过 Server-Sent Events 流式返回：
      - event: start    → 对话开始（包含 conversation_id）
      - event: token    → 流式文本 token
      - event: thinking → ReAct 推理步骤（工具调用/观察结果）
      - event: done     → 对话结束
      - event: error    → 错误信息
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
            # 捕获未预期的异常，向前端发送错误事件
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


@router.get("/messages/{conversation_id}")
async def get_messages(conversation_id: str, req: Request):
    """
    获取指定会话的消息历史

    Returns:
        会话详情（含消息列表），不存在时返回 404
    """
    agent = req.app.state.agent
    history = await agent.get_history(conversation_id)
    if history is None:
        return {"error": "会话不存在", "conversation_id": conversation_id}
    return history

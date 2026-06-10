"""
会话管理路由

提供会话的 CRUD 操作和工具列表查询接口。
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["conversations"])


@router.get("/conversations")
async def list_conversations(req: Request):
    """
    获取所有会话列表（按更新时间倒序）

    Returns:
        会话概要列表
    """
    agent = req.app.state.agent
    return await agent.get_conversations()


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, req: Request):
    """
    获取指定会话的详细信息（包含消息历史）

    Returns:
        会话详情，不存在时返回 404
    """
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
    """
    删除指定会话

    Returns:
        操作结果，不存在时返回 404
    """
    agent = req.app.state.agent
    success = await agent.delete_conversation(conversation_id)
    if not success:
        return JSONResponse(
            status_code=404,
            content={"error": "会话不存在", "conversation_id": conversation_id},
        )
    return {"success": True}


@router.get("/tools")
async def list_tools(req: Request):
    """
    获取所有可用工具列表

    返回工具的名称、描述和参数 Schema，供前端展示和选择。
    """
    agent = req.app.state.agent
    return agent.get_tool_info_list()

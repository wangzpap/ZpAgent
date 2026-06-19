"""
API 路由（统一入口）

合并聊天（SSE 流式输出）、消息历史查询、会话管理和工具列表的所有接口。
所有路由统一使用 /api 前缀。

FastAPI 路由体系说明：
  - APIRouter: 路由组，可以把相关的接口归到一起（类似 Java 的 Controller）
  - @router.post/get/delete: 路由装饰器，自动将函数注册为 API 端点
  - Request 参数: FastAPI 自动注入的请求对象，包含 app.state 等上下文
  - StreamingResponse: 流式响应，逐块推送数据给客户端（SSE 需要）

接口列表：
  POST /api/chat                      — 聊天（SSE 流式输出）
  GET  /api/messages/{conversation_id} — 获取会话消息历史
  GET  /api/conversations              — 获取所有会话列表
  GET  /api/conversations/{id}         — 获取会话详情
  DELETE /api/conversations/{id}       — 删除会话
  DELETE /api/conversations/{id}/messages — 清空会话消息历史
  GET  /api/tools                      — 获取可用工具列表
  POST /api/tools/reload               — 热重载 MCP 工具
"""

import json
import logging

# APIRouter: FastAPI 的路由分组工具（类似 Express 的 Router 或 Spring 的 @RequestMapping 前缀）
# Request: FastAPI 的请求对象，可以访问 app.state 等上下文数据
from fastapi import APIRouter, Request
# StreamingResponse: 流式 HTTP 响应，服务器可以逐块推送数据（而非一次性返回）
# JSONResponse: 普通 JSON 响应，用于返回错误信息
from fastapi.responses import StreamingResponse, JSONResponse

# ChatRequest: Pydantic 模型，FastAPI 会自动将 JSON 请求体解析为这个模型
# 如果请求数据不符合模型定义（如缺少必填字段），FastAPI 自动返回 422 错误
from models import ChatRequest

logger = logging.getLogger(__name__)

# 创建路由组，prefix="/api" 表示所有路由都挂在 /api 路径下
# 例如 @router.post("/chat") 的实际 URL 是 /api/chat
router = APIRouter(prefix="/api")


# ============================================
# 聊天接口（SSE 流式输出）
# ============================================
@router.post("/chat")
async def chat(request: ChatRequest, req: Request):
    """
    聊天接口 — 通过 Server-Sent Events (SSE) 流式返回 Agent 响应

    SSE (Server-Sent Events) 是什么？
      - 一种服务器向客户端单向推送数据的技术
      - 基于 HTTP 长连接，比 WebSocket 简单（不需要双向通信）
      - 格式: "event: 事件类型\\ndata: JSON数据\\n\\n"
      - 前端用 EventSource 或 fetch + ReadableStream 接收

    SSE 事件类型：
      - start:       对话开始（包含 conversation_id）
      - token:       流式文本 token（AI 每生成一个词就推送一次）
      - thinking:    工具开始调用时立即推送（tool + args，observation 为空）
      - tool_result: 工具执行完毕后推送结果（observation）
      - done:        对话结束（包含完整的最终回复）
      - error:       错误信息
    """
    # req.app.state 就是 main.py 中 lifespan 函数里挂载的全局状态
    # agent 实例在应用启动时创建，所有请求共享同一个 agent
    agent = req.app.state.agent

    async def event_stream():
        """
        异步生成器：将 Agent 的事件字典转换为 SSE 格式字符串

        这是一个嵌套的异步生成器函数：
          - 外层 chat() 是 FastAPI 路由处理函数
          - 内层 event_stream() 负责逐条生成 SSE 事件
          - StreamingResponse 会不断从生成器取数据，实时推送给客户端

        SSE 协议格式（每条消息）：
          event: 事件类型\n
          data: JSON数据\n
          \n

        例如：
          event: token
          data: {"content": "你好"}

          event: token
          data: {"content": "世界"}
        """
        try:
            # agent.run() 是一个 async generator，每次 yield 一个事件字典
            async for event in agent.run(request.model_dump()):
                # model_dump(): Pydantic 方法，将模型转为字典（类似 Java 的 toJson()）
                event_type = event["type"]
                # json.dumps 将字典转为 JSON 字符串
                # ensure_ascii=False 允许中文等非 ASCII 字符直接输出（不转义为 \uXXXX）
                event_data = json.dumps(event["data"], ensure_ascii=False)
                # yield: 产出数据并暂停，等待 StreamingResponse 消费后继续
                # 末尾两个 \n 是 SSE 协议要求的消息分隔符
                yield f"event: {event_type}\ndata: {event_data}\n\n"
        except Exception as e:
            logger.exception("聊天流异常")  # exception() 自动记录堆栈跟踪
            error_data = json.dumps(
                {"content": f"服务内部错误: {e}"}, ensure_ascii=False
            )
            yield f"event: error\ndata: {error_data}\n\n"

    # StreamingResponse: 流式响应
    # media_type="text/event-stream": 告诉浏览器这是 SSE 流
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",   # 禁止缓存（SSE 必须实时推送）
            "Connection": "keep-alive",     # 保持长连接
            "X-Accel-Buffering": "no",      # 禁用 Nginx 代理缓冲（否则前端可能收不到实时数据）
        },
    )


# ============================================
# 消息历史
# ============================================
@router.get("/messages/{conversation_id}")
async def get_messages(conversation_id: str, req: Request):
    """
    获取指定会话的消息历史

    {conversation_id} 是路径参数（类似 Spring 的 @PathVariable）
    FastAPI 会自动从 URL 中提取并传入函数参数。

    Returns:
        会话历史字典（包含消息列表）或错误信息
    """
    agent = req.app.state.agent
    history = await agent.get_history(conversation_id)
    if history is None:
        return {"error": "会话不存在", "conversation_id": conversation_id}
    return history


# ============================================
# 会话管理（CRUD 操作）
# ============================================
@router.get("/conversations")
async def list_conversations(req: Request):
    """
    获取所有会话列表（按更新时间倒序）

    前端会话列表页面调用此接口获取会话概要。
    """
    agent = req.app.state.agent
    return await agent.get_conversations()


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, req: Request):
    """
    获取指定会话的详细信息（包含完整消息历史）

    前端点击某个会话后调用此接口加载完整对话内容。
    不存在时返回 HTTP 404 状态码。
    """
    agent = req.app.state.agent
    conversation = await agent.get_history(conversation_id)
    if conversation is None:
        # JSONResponse: 手动构建 JSON 响应，可指定 HTTP 状态码
        # 404 = Not Found，告诉前端"资源不存在"
        return JSONResponse(
            status_code=404,
            content={"error": "会话不存在", "conversation_id": conversation_id},
        )
    return conversation


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, req: Request):
    """
    删除指定会话

    前端用户左滑/右键删除会话时调用。
    不存在时返回 HTTP 404 状态码。
    """
    agent = req.app.state.agent
    success = await agent.delete_conversation(conversation_id)
    if not success:
        return JSONResponse(
            status_code=404,
            content={"error": "会话不存在", "conversation_id": conversation_id},
        )
    return {"success": True}


@router.delete("/conversations/{conversation_id}/messages")
async def clear_conversation_messages(conversation_id: str, req: Request):
    """
    清空指定会话的消息历史（保留会话本身）

    删除 checkpointer 中该会话的所有对话上下文，使 LLM 丧失记忆。
    会话条目保留在侧边栏列表中，标题不变。
    不存在时返回 HTTP 404 状态码。
    """
    agent = req.app.state.agent
    success = await agent.clear_conversation(conversation_id)
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
    """
    获取所有可用工具列表

    返回每个工具的名称、描述和参数 Schema，供前端工具选择面板使用。
    """
    agent = req.app.state.agent
    return agent.get_tool_info_list()


@router.post("/tools/reload")
async def reload_tools(req: Request):
    """
    热重载 MCP 工具

    重新读取 mcp_servers.json 配置文件，清除旧的 MCP 工具并加载新的。
    修改 MCP 配置后调用此接口即可生效，无需重启服务。

    使用场景：
      1. 编辑 mcp_servers.json 添加/修改/删除 MCP 服务器配置
      2. 调用 POST /api/tools/reload
      3. 新的工具列表立即生效

    Returns:
        JSON 响应：
        {
            "success": true,
            "cleared": 2,   // 被清除的旧 MCP 工具数量
            "loaded": 3,    // 新加载的 MCP 工具数量
            "total": 5      // 当前工具总数（内置 + MCP）
        }
    """
    agent = req.app.state.agent
    result = await agent.reload_mcp_tools()
    return {
        "success": True,
        "cleared": result["cleared"],   # 被清除的旧 MCP 工具数量
        "loaded": result["loaded"],     # 新加载的 MCP 工具数量
        "total": result["total"],       # 当前工具总数（内置 + MCP）
    }

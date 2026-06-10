"""
ZpAgent 后端入口

基于 FastAPI + LangChain 1.2 构建的 ReAct 智能体服务。

启动方式:
    cd back
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

API 文档:
    启动后访问 http://localhost:8000/docs 查看 Swagger UI
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent import ReActAgent
from config import settings
from routers.chat import router as chat_router
from routers.conversations import router as conversations_router


# ============================================
# 应用生命周期管理
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期钩子
    - startup: 初始化 ReAct Agent 实例（LLM、工具注册表、记忆存储）
    - shutdown: 清理资源
    """
    app.state.agent = ReActAgent()
    tools_info = app.state.agent.get_tool_info_list()
    tool_names = ", ".join(t["name"] for t in tools_info)

    print("=" * 55)
    print("  ZpAgent 智能体服务已启动")
    print(f"  模型:     {settings.MODEL_NAME}")
    print(f"  API:      {settings.BASE_URL}")
    print(f"  工具:     {tool_names}")
    print(f"  文档:     http://localhost:{settings.PORT}/docs")
    print("=" * 55)

    yield

    print("ZpAgent 服务已关闭")


# ============================================
# 创建 FastAPI 应用
# ============================================
app = FastAPI(
    title="ZpAgent API",
    description="基于 LangChain 1.2 + ReAct 范式的智能体服务",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件
# 开发环境允许所有来源；生产环境请限制为具体域名
_is_dev = os.getenv("ENV", "development") == "development"
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        ["*"]
        if _is_dev
        else [os.getenv("FRONTEND_URL", "http://localhost:5173")]
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_router)
app.include_router(conversations_router)


@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "service": "ZpAgent", "version": "1.0.0"}


# ============================================
# 直接运行时启动服务
# ============================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=_is_dev,  # 仅开发环境启用热重载
    )

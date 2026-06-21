"""
ZpAgent 后端入口

基于 FastAPI + LangChain + LangGraph 构建的 ReAct 智能体服务。
使用 langchain.agents.create_agent 管理 ReAct 循环，替代手动实现。

启动方式:
    cd back
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

API 文档:
    启动后访问 http://localhost:8000/docs 查看 Swagger UI
"""

import logging
import os
# asynccontextmanager 是 Python 的异步上下文管理器装饰器
# 它允许我们用 async/await + yield 来定义"进入前做什么、退出后做什么"
# 类似 Java 的 try-with-resources 或 Go 的 defer
from contextlib import asynccontextmanager

from fastapi import FastAPI
# CORSMiddleware 是 FastAPI 的跨域中间件
# 中间件（Middleware）= 在请求到达路由处理函数之前/之后执行的代码
# 类似 Java Servlet 的 Filter 或 Go 的 HTTP Middleware
from fastapi.middleware.cors import CORSMiddleware

from agent import ReActAgent
from config import settings
from routers.api import router

logger = logging.getLogger(__name__)

# ---- 全局日志配置 ----
# 必须在 import agent 等模块之前执行，否则子模块的 logger 会继承默认的 WARNING 级别
# 格式: [时间] [级别] [模块名] 消息内容
# 示例: [2026-06-21 14:30:12] [INFO ] [agent          ] 收到请求: message='...'
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)-5s] [%(name)-14s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# 降低第三方库的日志级别，避免刷屏（只看 WARNING 及以上）
for _noisy in ("httpx", "httpcore", "openai", "urllib3", "asyncio", "langchain", "langgraph"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# os.getenv(key, default) 从系统环境变量中读取值，读不到则用 default
# 这里判断当前是否为开发环境，用于控制 CORS 策略和热重载
_is_dev = os.getenv("ENV", "development") == "development"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期钩子：启动时初始化 Agent，关闭时清理资源

    工作原理（Python 异步上下文管理器）：
      1. yield 之前的代码 → 应用启动时执行（类似 Java 的 @PostConstruct）
      2. yield 本身 → 应用运行期间，控制权交给 FastAPI
      3. yield 之后的代码 → 应用关闭时执行（类似 Java 的 @PreDestroy）
    """
    # 创建 Agent 实例并挂载到 app.state（FastAPI 的全局状态对象）
    # app.state 可以在任何路由处理函数中通过 request.app.state 访问
    app.state.agent = ReActAgent()
    # 异步初始化：加载 MCP 工具等外部资源
    # 注意：__init__() 不能是 async 的，所以需要单独定义 initialize() 方法
    await app.state.agent.initialize()

    # get_tool_info_list() 返回所有工具的名称和描述信息
    tools_info = app.state.agent.get_tool_info_list()
    # Python 列表推导式 + join：从工具信息列表中提取名称，用逗号拼接
    tool_names = ", ".join(t["name"] for t in tools_info)

    print("=" * 55)
    print("  ZpAgent 智能体服务已启动")
    print(f"  模型:     {settings.MODEL_NAME}")
    print(f"  API:      {settings.BASE_URL}")
    print(f"  工具:     {tool_names}")
    print(f"  文档:     http://localhost:{settings.PORT}/docs")
    print("=" * 55)
    logger.info("ZpAgent 服务启动完成，日志级别: DEBUG，已加载 %d 个工具", len(tools_info))

    # yield 是 Python 生成器的关键字，这里表示"暂停，把控制权交还给 FastAPI"
    # 当 FastAPI 关闭时，会继续执行 yield 后面的代码
    yield

    logger.info("ZpAgent 服务正在关闭...")
    print("ZpAgent 服务已关闭")


# 创建 FastAPI 应用实例
# title/description/version: 自动生成 Swagger API 文档时使用
# lifespan: 绑定上面定义的生命周期钩子，让 FastAPI 在启动/关闭时执行我们的初始化/清理逻辑
app = FastAPI(
    title="ZpAgent API",
    description="基于 LangChain + LangGraph 的 ReAct 智能体服务",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS（跨域资源共享）中间件
# 浏览器的安全策略默认禁止前端（如 localhost:5173）访问后端（如 localhost:8000）
# CORS 中间件通过添加 HTTP 响应头来告诉浏览器"允许跨域"
app.add_middleware(
    CORSMiddleware,
    # 开发环境允许所有来源（"*"），生产环境只允许指定的前端域名
    allow_origins=(
        ["*"] if _is_dev
        else [os.getenv("FRONTEND_URL", "http://localhost:5173")]
    ),
    allow_credentials=True,   # 允许携带 Cookie
    allow_methods=["*"],      # 允许所有 HTTP 方法（GET, POST, DELETE 等）
    allow_headers=["*"],      # 允许所有 HTTP 请求头
)

# 注册路由：把 routers/api.py 中定义的所有 API 路由挂载到这个 FastAPI 应用上
# 类似 Express.js 的 app.use('/api', router) 或 Spring 的 @RequestMapping
app.include_router(router)


@app.get("/api/health")
async def health_check():
    """
    健康检查接口

    @app.get 是 FastAPI 的路由装饰器，等价于 Spring 的 @GetMapping("/api/health")
    async def 表示这是一个异步函数，FastAPI 会自动用异步方式调用它
    """
    return {"status": "ok", "service": "ZpAgent", "version": "1.0.0"}


# Python 的入口判断：仅当直接运行本文件时才执行（被 import 时不执行）
# 类似 Java 的 public static void main(String[] args)
if __name__ == "__main__":
    import uvicorn
    # uvicorn 是 ASGI 服务器（类似 Tomcat 之于 Java / Gin 之于 Go）
    # "main:app" 表示从 main.py 文件中找到名为 app 的 FastAPI 实例
    # reload=True 表示文件修改时自动重启服务（仅开发环境使用）
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=_is_dev,
    )

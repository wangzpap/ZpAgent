"""
MCP 工具加载器

从本地 JSON 配置文件读取 MCP 服务器连接信息，
通过 langchain-mcp-adapters 的 MultiServerMCPClient 加载远程 MCP 工具，
使其与内置工具同级注册到 ToolRegistry 中。

什么是 MCP (Model Context Protocol)？
  - 一种标准化的协议，让 AI Agent 能调用外部工具/服务
  - 类似 REST API 的标准化版本，专为 LLM 工具调用设计
  - MCP 服务器 = 一个提供工具的外部服务（可以是本地进程或远程服务）
  - langchain-mcp-adapters: LangChain 提供的 MCP 适配器，将 MCP 工具转为 LangChain Tool

支持的 transport 类型（通信方式）：
  - stdio:           本地进程通信（需要 command + args，如启动一个本地 Python 脚本）
  - sse:             Server-Sent Events（需要 url，HTTP 长连接方式）
  - streamable_http: Streamable HTTP（需要 url，标准 HTTP 请求方式）
  - websocket:       WebSocket（需要 url，双向通信方式）
"""

import json
import logging
# pathlib: Python 现代路径操作库，比 os.path 更直观
# Path(__file__).resolve().parent.parent 可以优雅地获取上上级目录
from pathlib import Path
from typing import Any, Dict, List, Tuple

from langchain.tools import BaseTool

logger = logging.getLogger(__name__)


async def load_mcp_tools(config_path: str) -> List[Tuple[BaseTool, str]]:
    """
    从 MCP 配置文件加载所有 MCP 服务器提供的工具

    加载流程：
      1. 读取 mcp_servers.json 配置文件
      2. 校验配置格式（每个服务器必须有 transport 字段）
      3. 逐个服务器建立连接并加载工具
      4. 单个服务器失败不影响其他服务器（容错设计）

    Args:
        config_path: mcp_servers.json 的路径（相对于 back/ 目录）

    Returns:
        (BaseTool, server_name) 元组列表，server_name 标识工具来源的 MCP 服务器，
        加载失败返回空列表
    """
    # 延迟导入（lazy import）：在函数内部才 import，而不是文件顶部
    # 好处：
    #   1. 减少模块加载时间（只在实际使用时才加载）
    #   2. 避免循环导入问题
    #   3. 如果不需要 MCP 功能，即使没安装这个包也不会报错
    from langchain_mcp_adapters.client import MultiServerMCPClient

    # Path(__file__) → 当前文件的路径
    # .resolve()     → 转为绝对路径（消除相对路径和符号链接）
    # .parent.parent → 向上两级目录（从 tools/ 到 back/）
    back_dir = Path(__file__).resolve().parent.parent
    # / 运算符: pathlib 的路径拼接，等价于 os.path.join()，但语法更优雅
    full_path = back_dir / config_path

    if not full_path.exists():
        logger.info("MCP 配置文件不存在: %s，跳过 MCP 工具加载", full_path)
        return []

    # 读取并解析 JSON 配置文件
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            # json.load(): 从文件对象中读取并解析 JSON
            # raw_config 的格式如：
            # {
            #     "server_name": {"transport": "stdio", "command": "python", "args": ["server.py"]},
            #     "another_server": {"transport": "sse", "url": "http://..."}
            # }
            raw_config: Dict[str, Any] = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        # json.JSONDecodeError: JSON 格式错误（如缺少逗号、引号不匹配）
        # IOError: 文件读取错误（如权限不足、文件损坏）
        # 多个异常类型可以用元组 () 包裹来同时捕获
        logger.error("读取 MCP 配置文件失败: %s", e)
        return []

    if not raw_config:
        logger.info("MCP 配置文件为空，跳过加载")
        return []

    # 校验并过滤配置：只保留格式正确的服务器配置
    connections: Dict[str, Any] = {}
    for server_name, server_config in raw_config.items():
        # .items() 同时遍历字典的 key 和 value（类似 Java 的 entrySet()）
        if not isinstance(server_config, dict) or "transport" not in server_config:
            # 配置必须是字典且包含 transport 字段
            logger.warning("MCP 服务器 '%s' 配置格式不正确，已跳过", server_name)
            continue  # 跳过当前循环迭代，处理下一个服务器
        connections[server_name] = server_config

    if not connections:
        logger.info("没有有效的 MCP 服务器配置，跳过加载")
        return []

    # 逐个服务器加载工具（容错设计：单个失败不影响其他）
    all_tools: List[Tuple[BaseTool, str]] = []
    for server_name, server_config in connections.items():
        # MultiServerMCPClient: langchain-mcp-adapters 提供的 MCP 客户端
        # 支持同时连接多个 MCP 服务器，这里每次只连一个（方便错误处理）
        client = MultiServerMCPClient({server_name: server_config})
        try:
            # get_tools(): 异步调用，连接 MCP 服务器并获取工具列表
            # 返回的每个工具都是 BaseTool 子类，可以直接被 LangGraph Agent 使用
            tools = await client.get_tools()
            for t in tools:
                all_tools.append((t, server_name))  # 保留工具与来源服务器的映射
            logger.info(
                "MCP 服务器 '%s' 加载成功，获取 %d 个工具",
                server_name, len(tools),
            )
            for t in tools:
                logger.debug("  MCP 工具: %s - %s", t.name, t.description)
        except Exception as e:
            # 单个服务器加载失败只记录警告，不中断整体加载流程
            logger.warning(
                "MCP 服务器 '%s' 加载失败，已跳过: %s", server_name, e
            )

    if all_tools:
        logger.info("共加载 %d 个 MCP 工具", len(all_tools))

    return all_tools

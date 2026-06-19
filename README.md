# ZpAgent - ReAct 智能体项目

基于 **LangChain 1.2 + LangGraph + FastAPI + Vue 3** 构建的 ReAct 范式智能体，支持 SSE 流式输出、动态工具多选和多轮会话记忆。

## 项目架构

```
ZpAgent-Python/
├── back/                            # 后端（Python + FastAPI + LangChain + LangGraph）
│   ├── main.py                      # FastAPI 应用入口
│   ├── config.py                    # 配置管理（pydantic-settings）
│   ├── .env                         # 环境变量（API Key 等，不提交 Git）
│   ├── agent/
│   │   ├── __init__.py              # ReAct Agent 编排层（流式事件 + 会话管理）
│   │   └── graph.py                 # LangGraph Agent 图工厂（create_agent）
│   ├── llm/
│   │   └── __init__.py              # LLM 客户端（ChatOpenAI）
│   ├── tools/
│   │   ├── __init__.py              # LangChain @tool 导出
│   │   ├── builtin_tools.py         # 内置工具（位置/时间/天气）
│   │   └── registry.py             # 工具注册表
│   ├── conversation/
│   │   └── __init__.py              # 会话注册表（ConversationRegistry）
│   ├── models/
│   │   └── __init__.py              # Pydantic 数据模型
│   ├── routers/
│   │   └── api.py                   # 统一 API 路由（聊天 + 会话管理 + 工具）
│   └── requirements.txt             # Python 依赖
│
└── front/                           # 前端（Vue 3 + Vite）
    ├── package.json
    ├── vite.config.js               # Vite 配置（含 SSE 代理）
    ├── index.html
    └── src/
        ├── main.js
        ├── App.vue                  # 根组件（全局状态管理）
        ├── style.css                # 全局样式
        ├── api/
        │   └── index.js             # API 封装（REST + SSE 流式）
        ├── views/
        │   └── ChatView.vue         # 聊天主视图
        └── components/
            ├── ChatMessage.vue      # 消息组件（含 ReAct 思考过程）
            ├── ConversationList.vue # 侧边栏会话列表
            └── ToolSelector.vue     # 工具多选栏
```

## 技术栈

| 层面 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 后端框架 | FastAPI | 0.115+ | 高性能异步 Web 框架 |
| AI 框架 | LangChain | 1.2+ | LLM 调用 + 工具绑定 + astream_events 流式 |
| Agent 引擎 | LangGraph | 1.2+ | ReAct 状态图 + InMemorySaver checkpointer |
| LLM API | OpenAI 兼容 | — | DeepSeek / 智谱 / Moonshot / OpenAI 等 |
| 流式传输 | SSE | — | Server-Sent Events 逐 token 实时输出 |
| 前端框架 | Vue 3 + Vite | 3.5+ / 5.4+ | Composition API + 快速热更新 |
| 会话记忆 | LangGraph InMemorySaver | — | 框架原生 checkpointer，通过 thread_id 管理对话状态 |

## 会话记忆机制

项目采用 **双层架构** 实现会话记忆，各司其职：

```
┌──────────────────────────────────────────────────────────────┐
│                     会话记忆 = 两层协作                       │
├─────────────────────────┬────────────────────────────────────┤
│  ConversationRegistry   │  LangGraph checkpointer            │
│  ─────────────────────  │  ────────────────────────           │
│  应用层：会话元数据      │  框架层：对话状态管理               │
│  - 会话列表/创建/删除   │  - 通过 thread_id 关联对话          │
│  - 标题管理             │  - 自动拼接历史上下文给 LLM         │
│  - asyncio.Lock 并发安全│  - 跨请求状态持久化                 │
│                         │  - 支持 human-in-the-loop           │
└─────────────────────────┴────────────────────────────────────┘
```

- **LangGraph checkpointer（InMemorySaver）**：框架层自动管理对话状态。每次请求只需传入当前用户消息 + `thread_id`，框架自动从 checkpointer 中取出该会话的完整历史并拼接上下文，无需手动传递消息。
- **ConversationRegistry**：应用层管理会话元数据（标题、时间戳），供前端 UI 展示会话列表。消息历史通过 `agent.aget_state()` 从 checkpointer 中读取。

> 参考文档：[LangChain Short-Term Memory](https://langchain-doc.cn/v1/python/langchain/short-term-memory.html)

## 环境要求

| 工具 | 最低版本 | 说明 |
|------|----------|------|
| Python | 3.10+ | LangChain 1.2 要求 |
| Node.js | 18+ | Vue 3 + Vite 构建 |
| npm | 9+ | 前端包管理 |

## 启动步骤

### 第一步：克隆项目并配置

```bash
cd ZpAgent-Python
```

### 第二步：启动后端

```bash
cd back

# 1. 创建 Python 虚拟环境
python3 -m venv venv

# 2. 激活虚拟环境
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# 3. 安装 Python 依赖
pip install -r requirements.txt

# 4. 配置环境变量
#    编辑 back/.env，将 API_KEY=your-api-key-here 改为你的实际 Key

# 5. 启动后端服务
python main.py
```

启动成功后会看到：

```
=======================================================
  ZpAgent 智能体服务已启动
  模型:     deepseek-v4-flash
  API:      https://api.deepseek.com
  工具:     get_location, get_datetime, get_weather
  文档:     http://localhost:8000/docs
=======================================================
```

> 后端运行在 **http://localhost:8000**
> API 文档（Swagger UI）：**http://localhost:8000/docs**

### 第三步：启动前端

```bash
cd front

# 1. 安装前端依赖
npm install

# 2. 启动开发服务器
npm run dev
```

> 前端运行在 **http://localhost:5173**
> Vite 已配置 `/api` 代理到后端 8000 端口，无需额外配置

### 第四步：开始使用

1. 浏览器打开 **http://localhost:5173**
2. 在底部输入框输入消息，按 Enter 发送
3. 通过工具栏选择需要启用的工具（默认 3 个内置工具）
4. 观察 Agent 的 ReAct 推理过程（工具调用 → 观察结果 → 最终回答）

## 环境变量说明

在 `back/.env` 中配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `API_KEY` | LLM API 密钥（必填） | — |
| `BASE_URL` | API 基础地址 | `https://api.deepseek.com` |
| `MODEL_NAME` | 模型名称 | `deepseek-v4-flash` |
| `TEMPERATURE` | 生成温度（0~2） | `0.7` |
| `MAX_COMPLETION_TOKENS` | 最大生成 token 数 | `2048` |
| `REQUEST_TIMEOUT` | LLM 请求超时（秒） | `60` |
| `MAX_RETRIES` | LLM 请求重试次数 | `2` |
| `MAX_ITERATIONS` | ReAct 最大迭代次数 | `10` |
| `HOST` | 服务监听地址 | `0.0.0.0` |
| `PORT` | 服务端口 | `8000` |

## ReAct 循环原理

```
用户输入
  │
  ▼
┌─────────────────────────────────────────────────┐
│  LangGraph Agent（create_agent + InMemorySaver） │
│  checkpointer 自动通过 thread_id 加载对话历史    │
│  LLM 推理（astream_events v2 流式）              │
│  逐 token 输出 + 检测 tool_calls                 │
└──────────────┬──────────────────────────────────┘
               │
     ┌─────────┴──────────┐
     │                    │
  有 tool_calls       无 tool_calls
     │                    │
     ▼                    ▼
 ToolNode 并行执行      输出最终答案
     │                    │
     ▼                    ▼
 观察结果 → 回到 LLM   checkpointer 保存状态
```

## 内置工具

| 工具标识 | 功能说明 |
|----------|----------|
| `get_location` | 查询用户当前位置（模拟数据） |
| `get_datetime` | 查询当前日期、时间、星期 |
| `get_weather` | 根据城市和日期查询天气（模拟数据，支持 8 个主要城市） |

## 扩展指南

### 添加新工具

在 `back/tools/builtin_tools.py` 中用 `@tool` 装饰器定义：

```python
from langchain.tools import tool

@tool
def my_new_tool(param: str) -> str:
    """工具描述（LangChain 自动提取为 description）。

    Args:
        param: 参数描述（自动生成为 JSON Schema）
    """
    return "执行结果"
```

然后将 `my_new_tool` 加入文件底部的 `BUILTIN_TOOLS` 列表，前端会自动识别。

### 持久化会话记忆

当前使用 `InMemorySaver`（内存实现），服务重启后会话丢失。如需持久化，在 `agent/graph.py` 中替换 checkpointer：

```python
# SQLite 持久化
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")

# PostgreSQL 持久化
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string("postgresql://...")
```

## API 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat` | 聊天（SSE 流式输出） |
| `GET` | `/api/messages/{id}` | 获取会话消息历史 |
| `GET` | `/api/conversations` | 获取所有会话列表 |
| `GET` | `/api/conversations/{id}` | 获取会话详情 |
| `DELETE` | `/api/conversations/{id}` | 删除会话 |
| `GET` | `/api/tools` | 获取可用工具列表 |
| `GET` | `/api/health` | 健康检查 |

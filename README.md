# ZpAgent - ReAct 智能体项目

基于 **LangChain 1.2 + FastAPI + Vue 3** 构建的 ReAct 范式智能体，支持 SSE 流式输出、动态工具多选和多轮会话记忆。

## 项目架构

```
ZpAgent-Python/
├── back/                            # 后端（Python + FastAPI + LangChain）
│   ├── main.py                      # FastAPI 应用入口
│   ├── config.py                    # 配置管理（pydantic-settings）
│   ├── .env                         # 环境变量（API Key 等，不提交 Git）
│   ├── agent/
│   │   └── __init__.py              # ReAct Agent 核心引擎（流式 + 并行工具）
│   ├── llm/
│   │   └── __init__.py              # LLM 客户端（ChatOpenAI）
│   ├── tools/
│   │   ├── __init__.py              # LangChain @tool 导出
│   │   ├── builtin_tools.py         # 内置工具（天气/计算/日期/文本）
│   │   └── registry.py             # 工具注册表
│   ├── memory/
│   │   └── __init__.py              # 会话记忆（抽象基类 + 内存实现）
│   ├── models/
│   │   └── __init__.py              # Pydantic 数据模型
│   ├── routers/
│   │   ├── chat.py                  # 聊天路由（SSE 流式）
│   │   └── conversations.py         # 会话管理路由
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
| LLM API | OpenAI 兼容 | — | DeepSeek / 智谱 / Moonshot / OpenAI 等 |
| 流式传输 | SSE | — | Server-Sent Events 逐 token 实时输出 |
| 前端框架 | Vue 3 + Vite | 3.5+ / 5.4+ | Composition API + 快速热更新 |
| 会话记忆 | 内存存储 | — | 抽象基类设计，可扩展至数据库 |

## 环境要求

| 工具 | 最低版本 | 说明 |
|------|----------|------|
| Python | 3.10+ | LangChain 1.2 要求 |
| Node.js | 18+ | Vue 3 + Vite 构建 |
| npm | 9+ | 前端包管理 |

## 启动步骤

### 第一步：克隆项目并配置

```bash
# 进入项目目录
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
#    项目中已有 .env 文件，只需将 API_KEY 替换为你的 DeepSeek API Key：
#    编辑 back/.env，将 API_KEY=your-api-key-here 改为你的实际 Key
#
#    如果是首次使用，可从模板创建：
#    cp .env.example .env

# 5. 启动后端服务
python main.py
```

启动成功后会看到：

```
=======================================================
  ZpAgent 智能体服务已启动
  模型:     deepseek-v4-flash
  API:      https://api.deepseek.com
  工具:     weather, calculator, get_datetime, text_tool
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

启动成功后会看到：

```
  VITE v5.4.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
```

> 前端运行在 **http://localhost:5173**
> Vite 已配置 `/api` 代理到后端 8000 端口，无需额外配置

### 第四步：开始使用

1. 浏览器打开 **http://localhost:5173**
2. 在顶部工具栏勾选需要启用的工具（默认全选）
3. 在底部输入框输入消息，按 Enter 发送
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
┌──────────────────────────────────┐
│  LLM 推理（astream_events 流式）  │
│  逐 token 输出 + 检测 tool_calls │
└──────────────┬───────────────────┘
               │
     ┌─────────┴──────────┐
     │                    │
  有 tool_calls       无 tool_calls
     │                    │
     ▼                    ▼
 并行执行工具          输出最终答案
 (asyncio.gather)         │
     │                    ▼
     ▼                  结束
 观察结果 → 回到 LLM 继续推理
```

## 内置工具

| 工具标识 | 名称 | 功能说明 |
|----------|------|----------|
| `weather` | 天气查询 | 查询城市天气（模拟数据，可替换为真实 API） |
| `calculator` | 计算器 | 基于 AST 安全解析的数学表达式计算 |
| `get_datetime` | 日期时间 | 获取当前日期、时间、星期 |
| `text_tool` | 文本处理 | 字数统计 / 大小写转换 / 文本反转 |

## 扩展指南

### 添加新工具

在 `back/tools/builtin_tools.py` 中用 `@tool` 装饰器定义：

```python
from langchain_core.tools import tool

@tool
def my_new_tool(param: str) -> str:
    """工具描述（LangChain 自动提取为 description）。

    Args:
        param: 参数描述（自动生成为 JSON Schema）
    """
    return "执行结果"
```

然后将 `my_new_tool` 加入文件底部的 `BUILTIN_TOOLS` 列表，前端会自动识别。

### 扩展记忆存储

实现 `back/memory/__init__.py` 中的 `BaseMemory` 抽象类：

```python
class PostgresMemory(BaseMemory):
    async def create_conversation(self) -> str: ...
    async def get_messages(self, conversation_id) -> list: ...
    async def add_message(self, conversation_id, message) -> None: ...
    async def get_conversations(self) -> list: ...
    async def get_conversation(self, conversation_id) -> dict | None: ...
    async def delete_conversation(self, conversation_id) -> bool: ...
    async def conversation_exists(self, conversation_id) -> bool: ...
    async def update_title(self, conversation_id, title) -> None: ...
```

在 `agent/__init__.py` 中将 `InMemoryStore()` 替换为你的实现即可。

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

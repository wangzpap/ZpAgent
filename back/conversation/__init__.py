"""
会话存储模块（策略模式）

提供应用层的会话元数据管理，支持多种存储后端。
通过策略模式（Strategy Pattern）实现"一个接口、多个实现"，
上层业务代码只依赖抽象基类 ConversationStore，不关心底层存储细节。

架构设计：
  ┌─────────────────────────────────────┐
  │   ConversationStore (抽象基类)        │  ← 策略接口
  │   ├── create_conversation()          │
  │   ├── get_conversations()            │
  │   ├── get_conversation(id)           │
  │   ├── delete_conversation(id)        │
  │   ├── conversation_exists(id)        │
  │   ├── update_title(id, title)        │
  │   └── touch(id)                      │
  └──────────┬──────────────┬───────────┘
             │              │
  ┌──────────▼──────┐  ┌───▼────────────────┐
  │ InMemoryStore   │  │ MySQLStore         │   ← 具体策略
  │ (开发/测试)      │  │ (生产/持久化)        │
  └─────────────────┘  └────────────────────┘

使用方式：
    from conversation import create_conversation_store, ConversationStore

    # 根据配置自动选择存储后端（工厂方法）
    store: ConversationStore = create_conversation_store()
    await store.initialize()

    # 使用统一的接口操作会话
    conv_id = await store.create_conversation()
    conversations = await store.get_conversations()

切换后端：
    在 .env 文件中设置：
      CONVERSATION_BACKEND=memory    # 内存（默认，开发用）
      CONVERSATION_BACKEND=mysql     # MySQL（生产用，需配置连接信息）

双层架构说明：
  - LangGraph checkpointer（InMemorySaver）: 框架层，自动管理对话状态和消息历史
  - ConversationStore（本模块）: 应用层，管理会话元数据（标题、时间戳等）

  对话消息的存取完全由 LangGraph checkpointer 负责，
  本模块仅维护会话列表和标题等 UI 展示所需的元数据。
"""

import logging

# 导入抽象基类和所有具体实现
from conversation.base import ConversationStore
from conversation.memory_store import InMemoryConversationStore
from conversation.mysql_store import MySQLConversationStore

logger = logging.getLogger(__name__)

# __all__: 定义 from conversation import * 时导出的符号列表
# 这是 Python 模块的公共 API 声明，类似 Java 的 package-info 或 Go 的 export
__all__ = [
    "ConversationStore",           # 抽象基类（策略接口）
    "InMemoryConversationStore",   # 内存实现（具体策略 A）
    "MySQLConversationStore",      # MySQL 实现（具体策略 B）
    "create_conversation_store",   # 工厂函数
]


def create_conversation_store() -> ConversationStore:
    """
    工厂函数：根据配置创建具体的会话存储实例

    工厂模式（Factory Pattern）是什么？
      - 一种创建型设计模式，将对象创建的逻辑封装在一个函数中
      - 调用方不需要知道具体创建哪个类的实例，只需调用工厂函数
      - 类似 Java 的 Factory Bean 或 Go 的 NewXxx() 构造函数

    读取配置项 CONVERSATION_BACKEND 决定使用哪种后端：
      - "memory"（默认）: 内存存储，开发调试用，重启丢失
      - "mysql": MySQL 存储，生产环境用，数据持久化

    Returns:
        ConversationStore 的具体实例

    Raises:
        ValueError: 配置了不支持的后端类型时抛出

    使用示例：
        store = create_conversation_store()
        # 等价于：
        #   if backend == "memory": store = InMemoryConversationStore()
        #   elif backend == "mysql": store = MySQLConversationStore(...)
    """
    # 延迟导入 settings，避免模块加载时的循环依赖
    # 延迟导入（Lazy Import）：在函数内部 import，而非模块顶部
    # 好处：避免循环 import、减少模块加载时间
    from config import settings

    backend = settings.CONVERSATION_BACKEND.lower()
    logger.info("[ConversationStore] 创建存储后端: %s", backend)

    if backend == "memory":
        return InMemoryConversationStore()

    elif backend == "mysql":
        return MySQLConversationStore(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            db=settings.MYSQL_DATABASE,
        )

    else:
        # 未知后端类型，抛出明确的错误信息帮助排查
        raise ValueError(
            f"不支持的会话存储后端: '{backend}'。"
            f"可选值: 'memory'（内存）, 'mysql'（MySQL）。"
            f"请在 .env 文件中设置 CONVERSATION_BACKEND=memory 或 CONVERSATION_BACKEND=mysql"
        )

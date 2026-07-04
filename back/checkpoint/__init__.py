"""
对话检查点存储模块（策略模式）

提供对话上下文（消息历史 + 图状态）的持久化管理，支持多种存储后端。
通过策略模式（Strategy Pattern）实现"一个接口、多个实现"，
上层业务代码只依赖抽象基类 CheckpointStore，不关心底层存储细节。

架构设计：
  ┌─────────────────────────────────────┐
  │   CheckpointStore (抽象基类)          │  ← 策略接口
  │   ├── initialize()                   │
  │   ├── get_checkpointer()             │
  │   └── close()                        │
  └──────────┬──────────────┬───────────┘
             │              │
  ┌──────────▼──────┐  ┌───▼─────────────────┐
  │ MemoryStore     │  │ MySQLStore          │   ← 具体策略
  │ (InMemorySaver) │  │ (AIOMySQLSaver)     │
  │ 开发/测试        │  │ 生产/持久化           │
  └─────────────────┘  └─────────────────────┘

使用方式：
    from checkpoint import create_checkpoint_store, CheckpointStore

    store: CheckpointStore = create_checkpoint_store()
    await store.initialize()
    checkpointer = store.get_checkpointer()

切换后端：
    在 .env 文件中设置：
      CHECKPOINT_BACKEND=memory    # 内存（默认，开发用）
      CHECKPOINT_BACKEND=mysql     # MySQL 持久化（生产用，复用 MYSQL_* 配置）
"""

import logging

# 导入抽象基类和所有具体实现
from checkpoint.base import CheckpointStore
from checkpoint.memory_store import InMemoryCheckpointStore
from checkpoint.mysql_store import MySQLCheckpointStore

logger = logging.getLogger(__name__)

# __all__: 定义 from checkpoint import * 时导出的符号列表
__all__ = [
    "CheckpointStore",             # 抽象基类（策略接口）
    "InMemoryCheckpointStore",     # 内存实现（具体策略 A）
    "MySQLCheckpointStore",        # MySQL 实现（具体策略 B）
    "create_checkpoint_store",     # 工厂函数
]


def create_checkpoint_store() -> CheckpointStore:
    """
    工厂函数：根据配置创建具体的检查点存储实例

    读取配置项 CHECKPOINT_BACKEND 决定使用哪种后端：
      - "memory"（默认）: 内存存储，开发调试用，重启丢失
      - "mysql": MySQL 存储，生产环境用，数据持久化
                 复用 MYSQL_HOST/MYSQL_PORT 等配置（与 conversation 模块共用同一个 MySQL 实例）

    Returns:
        CheckpointStore 的具体实例

    Raises:
        ValueError: 配置了不支持的后端类型时抛出
    """
    # 延迟导入 settings，避免模块加载时的循环依赖
    from config import settings

    backend = settings.CHECKPOINT_BACKEND.lower()
    logger.info("[CheckpointStore] 创建存储后端: %s", backend)

    if backend == "memory":
        return InMemoryCheckpointStore()

    elif backend == "mysql":
        # 复用 conversation 模块的 MySQL 配置（同一个数据库实例）
        return MySQLCheckpointStore(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            db=settings.MYSQL_DATABASE,
        )

    else:
        raise ValueError(
            f"不支持的检查点存储后端: '{backend}'。"
            f"可选值: 'memory'（内存）, 'mysql'（MySQL 持久化）。"
            f"请在 .env 文件中设置 CHECKPOINT_BACKEND=memory 或 CHECKPOINT_BACKEND=mysql"
        )

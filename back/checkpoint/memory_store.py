"""
内存对话检查点存储（InMemoryCheckpointStore）

策略模式中的"具体策略 A"：使用 LangGraph 内置的 InMemorySaver，
将对话上下文（消息历史 + 图状态）存储在内存中。

优点：
  - 零依赖，开箱即用（无需数据库或文件系统）
  - 读写速度极快（纯内存操作）
  - 适合开发调试和单机部署

缺点：
  - 数据不持久化，服务重启后所有对话上下文丢失
  - 不支持多进程 / 多实例共享数据

工作原理：
  InMemorySaver 是 LangGraph 框架提供的内存检查点保存器，
  内部使用 Python 字典保存每个 thread_id 对应的完整对话状态。
  LangGraph 在每轮对话结束后自动调用 put() 保存检查点，
  下次对话时通过 get_tuple() 恢复之前的状态（实现跨请求记忆）。
"""

import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from checkpoint.base import CheckpointStore

logger = logging.getLogger(__name__)


class InMemoryCheckpointStore(CheckpointStore):
    """
    基于内存的对话检查点存储实现

    直接包装 LangGraph 的 InMemorySaver，无任何额外依赖。
    所有对话数据存在进程内存中，服务关闭即丢失。

    使用方式：
        store = InMemoryCheckpointStore()
        # initialize() 和 close() 均为空操作（无需生命周期管理）
        checkpointer = store.get_checkpointer()
    """

    def __init__(self):
        """初始化 InMemorySaver 实例"""
        # InMemorySaver(): LangGraph 内置的内存检查点保存器
        # 内部维护一个 defaultdict 来存储每个 thread 的检查点数据
        self._saver = InMemorySaver()
        logger.debug("[MemoryCheckpointStore] InMemorySaver 已创建")

    def get_checkpointer(self) -> BaseCheckpointSaver:
        """
        获取 InMemorySaver 实例

        Returns:
            LangGraph InMemorySaver 实例
        """
        return self._saver

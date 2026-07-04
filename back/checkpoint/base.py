"""
对话检查点存储抽象基类（策略接口）

定义对话上下文（消息历史 + 图状态）持久化的统一接口。
所有具体实现（内存、文件等）必须继承此类。

这是策略模式（Strategy Pattern）中的"抽象策略"角色，
与 conversation/ 模块的 ConversationStore 策略模式平行。

两者的分工：
  ┌─────────────────────────────────┬───────────────────────────────┐
  │  conversation/ ConversationStore │  checkpoint/ CheckpointStore   │
  ├─────────────────────────────────┼───────────────────────────────┤
  │  应用层：会话元数据               │  框架层：对话上下文             │
  │  标题、创建时间、更新时间          │  消息历史、图状态、中断信息     │
  │  自研 CRUD 接口                  │  LangGraph BaseCheckpointSaver │
  └─────────────────────────────────┴───────────────────────────────┘

设计意图：
  - LangGraph 的 checkpointer 负责自动管理对话状态（消息历史的保存和恢复）
  - 不同的 CheckpointStore 实现决定了对话上下文的持久化方式
  - 内存方案：零依赖、速度快，但重启丢失
  - 文件方案：基于 SQLite，对话数据持久化到本地文件，重启可恢复
"""

from abc import ABC, abstractmethod

# BaseCheckpointSaver: LangGraph 的检查点保存器基类
# 所有 LangGraph checkpointer（InMemorySaver、SqliteSaver 等）都继承自它
# 它定义了 put / get_tuple / list 等方法，LangGraph 框架内部调用这些方法来
# 自动保存和恢复对话状态（消息列表、工具调用记录、中断信息等）
from langgraph.checkpoint.base import BaseCheckpointSaver


class CheckpointStore(ABC):
    """
    对话检查点存储抽象基类（策略接口）

    定义了对话上下文持久化的全部操作：创建 checkpointer、生命周期管理。
    上层业务代码（Agent）只依赖此抽象基类，不关心底层存储细节。

    使用方式：
        store: CheckpointStore = create_checkpoint_store()
        await store.initialize()
        checkpointer = store.get_checkpointer()
        # ... 将 checkpointer 传给 LangGraph build_agent_graph() ...
        await store.close()

    扩展方式：
        # 新增 PostgreSQL 后端只需：
        class PostgresCheckpointStore(CheckpointStore):
            def get_checkpointer(self) -> BaseCheckpointSaver: ...
            # ... 实现所有抽象方法 ...
    """

    # ---- 初始化 / 销毁 ----

    async def initialize(self) -> None:
        """
        异步初始化钩子（可选覆写）

        用于执行需要 await 的初始化操作，如创建数据库连接、建表等。
        默认实现为空（no-op），内存后端无需覆写。

        在应用启动时（lifespan 阶段）调用。
        """
        pass

    async def close(self) -> None:
        """
        异步关闭钩子（可选覆写）

        用于清理资源，如关闭数据库连接。
        默认实现为空（no-op），内存后端无需覆写。

        在应用关闭时（lifespan 阶段）调用。
        """
        pass

    # ---- 核心方法 ----

    @abstractmethod
    def get_checkpointer(self) -> BaseCheckpointSaver:
        """
        获取 LangGraph checkpointer 实例

        返回的 checkpointer 会被传给 build_agent_graph()，
        LangGraph 框架通过它自动管理对话状态的保存和恢复。

        Returns:
            BaseCheckpointSaver 的实例（InMemorySaver / AsyncSqliteSaver 等）
        """
        ...

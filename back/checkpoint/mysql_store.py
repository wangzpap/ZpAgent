"""
MySQL 对话检查点存储实现（MySQLCheckpointStore）

策略模式中的"具体策略 B"：使用 LangGraph 官方的 AIOMySQLSaver，
将对话上下文（消息历史 + 图状态）持久化到 MySQL 数据库。

优点：
  - 数据持久化，服务重启后对话上下文不丢失
  - 支持多进程 / 多实例共享数据（适合生产环境部署）
  - 复用已有的 MySQL 配置（与 conversation/ 模块共用同一个 MySQL 实例）

缺点：
  - 需要额外部署 MySQL 数据库
  - 读写延迟比内存方案高（网络 IO）

实现要点：
  - 使用 AIOMySQLSaver（LangGraph 官方 MySQL checkpointer）
  - 基于 aiomysql 异步连接，不阻塞事件循环
  - setup() 自动创建 LangGraph 所需的表和索引（幂等操作）
  - 连接在 initialize() 中创建，在 close() 中释放
"""

import logging

import aiomysql
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.mysql.aio import AIOMySQLSaver

from checkpoint.base import CheckpointStore

logger = logging.getLogger(__name__)


class MySQLCheckpointStore(CheckpointStore):
    """
    基于 MySQL 的对话检查点存储实现

    使用 LangGraph 官方的 AIOMySQLSaver 将对话状态持久化到 MySQL。
    与 conversation/mysql_store.py 共用同一个 MySQL 实例和配置。

    使用方式：
        store = MySQLCheckpointStore(host="localhost", port=3306, ...)
        await store.initialize()   # 创建连接池 + 自动建表
        checkpointer = store.get_checkpointer()
        # ... 使用 checkpointer ...
        await store.close()        # 关闭连接池
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        user: str = "root",
        password: str = "",
        db: str = "zpagent",
        pool_minsize: int = 1,
        pool_maxsize: int = 5,
        pool_recycle: int = 3600,
    ):
        """
        初始化 MySQL 检查点存储后端

        Args:
            host:          MySQL 服务器地址（默认 localhost）
            port:          MySQL 端口（默认 3306）
            user:          数据库用户名
            password:      数据库密码
            db:            数据库名称（默认 zpagent，与 conversation 模块共用）
            pool_minsize:  连接池最小连接数（默认 1）
            pool_maxsize:  连接池最大连接数（默认 5）
            pool_recycle:  连接回收时间（秒，默认 3600）。超过该时间未使用的连接
                           会被连接池自动回收，避免 MySQL 因 wait_timeout 关闭连接后
                           再使用时报 `Not connected` 错误。
        """
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._db = db
        self._pool_minsize = pool_minsize
        self._pool_maxsize = pool_maxsize
        self._pool_recycle = pool_recycle
        self._pool: aiomysql.Pool | None = None
        self._saver: AIOMySQLSaver | None = None

    def _ensure_saver(self) -> AIOMySQLSaver:
        """
        确保 AIOMySQLSaver 已初始化（防御性编程）

        Returns:
            已初始化的 AIOMySQLSaver 实例

        Raises:
            RuntimeError: 尚未调用 initialize() 时抛出
        """
        if self._saver is None:
            raise RuntimeError(
                "MySQLCheckpointStore 尚未初始化。"
                "请先调用 await store.initialize() 创建数据库连接。"
            )
        return self._saver

    # ---- 生命周期 ----

    async def initialize(self) -> None:
        """
        异步初始化：创建 MySQL 连接 + 自动建表

        流程：
          1. aiomysql.connect: 异步创建 MySQL 连接
          2. AIOMySQLSaver.setup(): 自动创建 LangGraph 所需的表和索引

        setup() 做了什么？
          AIOMySQLSaver 内部定义了 checkpoints / checkpoint_writes /
          checkpoint_blobs 等表的 CREATE TABLE IF NOT EXISTS 语句。
          setup() 执行这些 SQL，幂等操作（已存在则跳过）。
        """
        logger.info("[MySQLCheckpointStore] 正在连接 MySQL (%s:%d/%s)...",
                     self._host, self._port, self._db)

        # aiomysql.create_pool(): 异步创建 MySQL 连接池
        # pool_recycle: 连接回收时间（秒），超过该时间未使用的连接会被自动回收，
        # 防止 MySQL wait_timeout 关闭连接后复用时报 "Not connected"
        self._pool = await aiomysql.create_pool(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            db=self._db,
            autocommit=True,
            charset="utf8mb4",
            minsize=self._pool_minsize,
            maxsize=self._pool_maxsize,
            pool_recycle=self._pool_recycle,
        )
        logger.info("[MySQLCheckpointStore] MySQL 连接池已创建 (size=%d-%d, recycle=%ds)",
                     self._pool_minsize, self._pool_maxsize, self._pool_recycle)

        # 创建 AIOMySQLSaver 并执行建表
        # AIOMySQLSaver 支持传入 Connection 或 Pool；传入 Pool 时会自动 acquire()
        self._saver = AIOMySQLSaver(self._pool)
        await self._saver.setup()
        logger.info("[MySQLCheckpointStore] 检查点表已就绪")

    async def close(self) -> None:
        """
        异步关闭：释放 MySQL 连接池

        pool.close() 关闭连接池，wait_closed() 等待所有连接释放完毕。
        """
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            self._saver = None
            logger.info("[MySQLCheckpointStore] MySQL 连接池已关闭")

    # ---- 核心方法 ----

    def get_checkpointer(self) -> BaseCheckpointSaver:
        """
        获取 AIOMySQLSaver 实例

        Returns:
            LangGraph AIOMySQLSaver 实例（已初始化，可直接使用）
        """
        return self._ensure_saver()

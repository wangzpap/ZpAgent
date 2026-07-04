"""
MySQL 会话存储实现（MySQLConversationStore）

策略模式中的"具体策略 B"：将会话元数据持久化到 MySQL 数据库。

优点：
  - 数据持久化，服务重启后会话不丢失
  - 支持多进程 / 多实例共享数据（适合生产环境部署）

缺点：
  - 需要额外部署 MySQL 数据库
  - 读写延迟比内存方案高（网络 IO）

实现要点：
  - 使用 aiomysql 异步连接池（Connection Pool），避免阻塞事件循环
  - 连接池在 initialize() 中创建，在 close() 中释放
  - 所有 SQL 操作通过参数化查询（%s 占位符）防止 SQL 注入
  - 建表使用 CREATE TABLE IF NOT EXISTS，幂等操作（重复执行不报错）

数据库表结构：
  CREATE TABLE conversations (
      id           VARCHAR(36)   PRIMARY KEY,   -- UUID 格式，如 "550e8400-..."
      title        VARCHAR(255)  NOT NULL,       -- 会话标题
      created_at   VARCHAR(30)   NOT NULL,       -- ISO 格式时间字符串
      updated_at   VARCHAR(30)   NOT NULL        -- ISO 格式时间字符串
  );
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# aiomysql: Python 的异步 MySQL 驱动库
# 类似 Java 的 HikariCP 连接池，提供异步的连接获取和释放
# pip install aiomysql
import aiomysql

from conversation.base import ConversationStore

logger = logging.getLogger(__name__)


class MySQLConversationStore(ConversationStore):
    """
    基于 MySQL 的会话存储实现

    通过 aiomysql 连接池与 MySQL 数据库交互，实现会话元数据的持久化管理。

    连接池（Connection Pool）是什么？
      - 预先创建一组数据库连接并复用，避免每次查询都建立新连接
      - 建立 MySQL 连接的开销较大（TCP 握手 + 认证），连接池可以显著降低延迟
      - 类似 Java 的 HikariCP / Druid 连接池

    使用方式：
        store = MySQLConversationStore(host="localhost", port=3306, ...)
        await store.initialize()   # 创建连接池 + 建表
        # ... 正常使用 CRUD 方法 ...
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
    ):
        """
        初始化 MySQL 存储后端

        Args:
            host:         MySQL 服务器地址（默认 localhost）
            port:         MySQL 端口（默认 3306）
            user:         数据库用户名
            password:     数据库密码
            db:           数据库名称（默认 zpagent）
            pool_minsize: 连接池最小连接数（空闲时保留的连接数）
            pool_maxsize: 连接池最大连接数（并发请求时的连接上限）
        """
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._db = db
        self._pool_minsize = pool_minsize
        self._pool_maxsize = pool_maxsize
        # 连接池引用，在 initialize() 中创建，close() 中释放
        self._pool: Optional[aiomysql.Pool] = None

    # ---- 建表 SQL ----
    # CREATE TABLE IF NOT EXISTS: 幂等操作，表已存在则跳过，不会报错
    # VARCHAR(36): UUID 格式固定 36 字符（如 "550e8400-e29b-41d4-a716-446655440000"）
    # VARCHAR(255): 标题最大长度，255 是 MySQL 中 VARCHAR 的常见上限
    # VARCHAR(30): ISO 时间字符串最长不超过 30 字符（如 "2024-06-17T14:30:00.123456"）
    _CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS conversations (
            id           VARCHAR(36)   PRIMARY KEY,
            title        VARCHAR(255)  NOT NULL    DEFAULT '新对话',
            created_at   VARCHAR(30)   NOT NULL,
            updated_at   VARCHAR(30)   NOT NULL,
            INDEX idx_updated_at (updated_at DESC)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
    """

    def _ensure_pool(self) -> aiomysql.Pool:
        """
        确保连接池已初始化（防御性编程）

        如果 CRUD 方法在 initialize() 之前被误调用，抛出明确的错误信息，
        而非晦涩的 AttributeError: 'NoneType' object has no attribute 'acquire'

        Returns:
            已初始化的连接池实例

        Raises:
            RuntimeError: 连接池尚未初始化时抛出
        """
        if self._pool is None:
            raise RuntimeError(
                "MySQLConversationStore 尚未初始化。"
                "请先调用 await store.initialize() 创建数据库连接池。"
            )
        return self._pool

    # ---- 初始化 / 销毁 ----

    async def initialize(self) -> None:
        """
        异步初始化：创建数据库连接池 + 自动建表

        在应用启动时（lifespan 阶段）调用。
        aiomysql.create_pool() 会异步创建连接池，不会阻塞事件循环。
        """
        logger.info("[MySQLStore] 正在创建 MySQL 连接池 (%s:%d/%s)...",
                     self._host, self._port, self._db)
        self._pool = await aiomysql.create_pool(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            db=self._db,
            minsize=self._pool_minsize,
            maxsize=self._pool_maxsize,
            # autocommit=True: 每条 SQL 自动提交（无需手动 commit）
            # 如果不设置，默认 autocommit=False，需要手动 conn.commit()
            autocommit=True,
            # charset: 使用 utf8mb4 支持完整的 Unicode（包括 emoji）
            charset="utf8mb4",
        )
        logger.info("[MySQLStore] 连接池创建成功 (min=%d, max=%d)",
                     self._pool_minsize, self._pool_maxsize)

        # 自动建表（幂等操作：CREATE TABLE IF NOT EXISTS）
        # self._ensure_pool().acquire(): 从连接池获取一个连接（用完自动归还）
        async with self._ensure_pool().acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(self._CREATE_TABLE_SQL)
                logger.info("[MySQLStore] conversations 表已就绪")

    async def close(self) -> None:
        """
        异步关闭：释放数据库连接池

        在应用关闭时（lifespan 阶段）调用。
        pool.close() 关闭所有空闲连接，pool.wait_closed() 等待正在使用的连接归还。
        """
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            logger.info("[MySQLStore] 连接池已关闭")
            self._pool = None

    # ---- 核心 CRUD 操作 ----

    async def create_conversation(self) -> str:
        """
        创建新会话并写入 MySQL，返回会话 ID

        SQL 说明：
          INSERT INTO conversations (id, title, created_at, updated_at)
          VALUES (%s, %s, %s, %s)
          - %s 是 aiomysql 的参数化占位符，防止 SQL 注入
          - 实际值通过第二个参数元组传入

        Returns:
            新创建的会话 ID（UUID 格式字符串）
        """
        conv_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # pool.acquire() 的异步上下文管理器用法：
        #   从连接池借出一个连接，使用完毕后自动归还
        #   类似 Java 的 try-with-resources 或 Go 的 defer conn.Close()
        async with self._ensure_pool().acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO conversations (id, title, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s)",
                    (conv_id, "新对话", now, now),
                )
        return conv_id

    async def get_conversations(self) -> List[Dict[str, Any]]:
        """
        获取所有会话概要列表（按更新时间倒序）

        SQL 说明：
          SELECT id, title, created_at, updated_at
          FROM conversations
          ORDER BY updated_at DESC
          - DESC: 降序排列（最新的排在最前面）

        Returns:
            会话概要字典列表
        """
        async with self._ensure_pool().acquire() as conn:
            # aiomysql.DictCursor: 返回字典格式的结果（而非默认的元组）
            # 例如: {"id": "xxx", "title": "新对话", ...} 而非 ("xxx", "新对话", ...)
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT id, title, created_at, updated_at "
                    "FROM conversations "
                    "ORDER BY updated_at DESC"
                )
                # fetchall(): 获取所有查询结果行
                rows = await cur.fetchall()
                return [dict(row) for row in rows]

    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个会话的元数据

        SQL 说明：
          SELECT ... FROM conversations WHERE id = %s
          - WHERE 子句按主键精确查找，时间复杂度 O(1)
          - fetchone(): 只取一行结果（不存在时返回 None）

        Args:
            conversation_id: 会话 ID

        Returns:
            会话信息字典或 None
        """
        async with self._ensure_pool().acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT id, title, created_at, updated_at "
                    "FROM conversations WHERE id = %s",
                    (conversation_id,),
                )
                row = await cur.fetchone()
                if row:
                    return dict(row)
        return None

    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        删除指定会话

        SQL 说明：
          DELETE FROM conversations WHERE id = %s
          - cur.rowcount: 返回受影响的行数
          - rowcount > 0 表示至少删除了一行（即会话存在）
          - rowcount == 0 表示没有匹配的行（即会话不存在）

        Args:
            conversation_id: 要删除的会话 ID

        Returns:
            True 表示删除成功，False 表示会话不存在
        """
        async with self._ensure_pool().acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM conversations WHERE id = %s",
                    (conversation_id,),
                )
                return cur.rowcount > 0

    async def conversation_exists(self, conversation_id: str) -> bool:
        """
        检查会话是否存在

        SQL 优化：
          SELECT 1 ... LIMIT 1
          - SELECT 1: 不查询具体列，只检查是否有匹配行（性能最优）
          - LIMIT 1: 找到第一行就停止扫描（即使有多行匹配也只返回一行）
          - 比 SELECT COUNT(*) 更高效（COUNT 需要扫描所有匹配行）

        Args:
            conversation_id: 要检查的会话 ID

        Returns:
            True 表示存在，False 表示不存在
        """
        async with self._ensure_pool().acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM conversations WHERE id = %s LIMIT 1",
                    (conversation_id,),
                )
                return (await cur.fetchone()) is not None

    async def update_title(self, conversation_id: str, title: str) -> None:
        """
        更新会话标题

        SQL 说明：
          UPDATE conversations SET title = %s WHERE id = %s
          - SET title = %s: 只更新 title 列，不影响其他列

        Args:
            conversation_id: 会话 ID
            title: 新的标题文本
        """
        async with self._ensure_pool().acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE conversations SET title = %s WHERE id = %s",
                    (title, conversation_id),
                )

    async def touch(self, conversation_id: str) -> None:
        """
        更新会话的 updated_at 时间戳为当前时间

        SQL 说明：
          UPDATE conversations SET updated_at = %s WHERE id = %s
          - 只更新 updated_at 列，用于排序时反映"最后活跃时间"

        Args:
            conversation_id: 会话 ID
        """
        now = datetime.now().isoformat()
        async with self._ensure_pool().acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE conversations SET updated_at = %s WHERE id = %s",
                    (now, conversation_id),
                )

"""
配置管理模块

使用 pydantic-settings 的 BaseSettings 实现配置管理，
自动从环境变量 / .env 文件加载配置，并提供类型校验和范围校验。
支持兼容 OpenAI 格式的第三方 API（DeepSeek、智谱、Moonshot 等）。
"""

import os
# Pydantic 是 Python 的数据校验库（类似 Java 的 Bean Validation / Go 的 validator）
# Field: 定义字段的默认值、描述、校验规则（如范围限制）
# field_validator: 装饰器，为特定字段添加自定义校验逻辑
from pydantic import Field, field_validator
# BaseSettings: Pydantic 的配置管理基类，自动从环境变量 / .env 文件读取配置
# SettingsConfigDict: 配置 BaseSettings 行为的字典类型（如指定 .env 文件路径）
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用配置类

    继承 BaseSettings 后，每个类属性会自动尝试从以下来源读取值（优先级从高到低）：
      1. 系统环境变量（如 export API_KEY=xxx）
      2. .env 文件中的键值对
      3. Field() 中定义的 default 默认值

    读取后会自动进行类型转换和校验（如 str→float、范围检查）。
    """

    # ---- BaseSettings 的元配置 ----
    # model_config 是 Pydantic v2 的类级别配置，控制 BaseSettings 的行为
    model_config = SettingsConfigDict(
        # os.path.join 拼接路径：__file__ 是当前文件路径，dirname 取其目录
        # 最终效果：在 back/ 目录下查找 .env 文件
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略 .env 中未在本类定义的变量，避免报错
    )

    # ---- LLM 配置（兼容 OpenAI 格式的 API） ----
    # Field() 的参数说明：
    #   default: 默认值（读不到环境变量时使用）
    #   description: 字段描述（自动生成文档时使用）
    #   ge / gt / le / lt: 范围校验（ge=大于等于, gt=大于, le=小于等于, lt=小于）
    API_KEY: str = Field(default="", description="LLM API 密钥")
    BASE_URL: str = Field(
        default="https://api.deepseek.com", description="API 基础地址"
    )
    MODEL_NAME: str = Field(default="deepseek-v4-flash", description="模型名称")
    # TEMPERATURE: float 类型注解 + ge/le 范围校验 → 值必须在 0.0~2.0 之间
    TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0, description="生成温度 (0~2)")
    MAX_COMPLETION_TOKENS: int = Field(
        default=2048, gt=0, le=128000, description="最大生成 token 数"
    )
    REQUEST_TIMEOUT: int = Field(default=60, gt=0, description="LLM 请求超时时间（秒）")
    MAX_RETRIES: int = Field(default=2, ge=0, description="LLM 请求最大重试次数")

    # ---- Agent 配置 ----
    MAX_ITERATIONS: int = Field(
        default=10, gt=0, le=50, description="ReAct 最大迭代次数"
    )
    MCP_CONFIG_PATH: str = Field(
        default="mcp_servers.json",
        description="MCP 服务器配置文件路径（相对于 back/ 目录）",
    )

    # ---- 服务配置 ----
    HOST: str = Field(default="0.0.0.0", description="服务监听地址")
    PORT: int = Field(default=8000, gt=0, le=65535, description="服务端口")

    # ---- 对话检查点存储后端配置（策略模式：memory / mysql） ----
    # CHECKPOINT_BACKEND: 选择对话上下文（消息历史 + 图状态）的存储方式
    #   - "memory": InMemorySaver（默认），开发调试用，重启丢失
    #   - "mysql":  AIOMySQLSaver（MySQL），生产环境用，数据持久化
    CHECKPOINT_BACKEND: str = Field(
        default="memory",
        description="检查点存储后端: 'memory'（内存）或 'mysql'（持久化）",
    )
    # 注意: MySQL 后端复用 MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DATABASE 配置

    # ---- 会话存储后端配置（策略模式：memory / mysql） ----
    # CONVERSATION_BACKEND: 选择会话元数据的存储方式
    #   - "memory": 内存字典（默认），开发调试用，重启丢失
    #   - "mysql":  MySQL 数据库，生产环境用，数据持久化
    CONVERSATION_BACKEND: str = Field(
        default="memory",
        description="会话存储后端: 'memory'（内存）或 'mysql'（持久化）",
    )
    # MySQL 连接配置（CONVERSATION_BACKEND=mysql 或 CHECKPOINT_BACKEND=mysql 时共用）
    MYSQL_HOST: str = Field(default="localhost", description="MySQL 服务器地址")
    MYSQL_PORT: int = Field(default=3306, gt=0, le=65535, description="MySQL 端口")
    MYSQL_USER: str = Field(default="root", description="MySQL 用户名")
    MYSQL_PASSWORD: str = Field(default="", description="MySQL 密码")
    MYSQL_DATABASE: str = Field(default="zpagent", description="MySQL 数据库名")

    # ---- 自定义校验器 ----
    # @field_validator("API_KEY") 表示这个函数专门校验 API_KEY 字段
    # @classmethod 是 Python 的类方法装饰器：
    #   - 普通方法的第一个参数是 self（实例本身）
    #   - classmethod 的第一个参数是 cls（类本身），可以在不创建实例时调用
    # 校验函数的签名：cls → 当前类, v → 字段的当前值, 返回值 → 校验/转换后的值
    @field_validator("API_KEY")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """校验 API Key 是否已配置，未配置时发出警告（但不阻止启动）"""
        if not v or v == "your-api-key-here":
            # warnings.warn 输出警告信息，不同于 raise Exception，它不会中断程序
            import warnings
            warnings.warn(
                "API_KEY 未配置！请在 .env 文件或环境变量中设置有效的 API Key。",
                stacklevel=2,
            )
        return v


# 全局配置单例
# Python 模块级别的变量只会在首次 import 时执行一次（天然单例）
# 其他文件通过 from config import settings 即可获取同一个实例
settings = Settings()


def reload_settings() -> None:
    """
    热重载配置：重新从 .env 文件读取配置，原地更新 settings 单例的属性

    为什么需要这个函数？
      Settings() 只在模块首次 import 时执行一次，之后 settings 对象持有的值
      就是那一刻从 .env 读到的快照。运行时通过 API 修改 .env 后，内存中的
      settings 并不知道文件已变化。

    为什么不直接 settings = Settings() 重新赋值？
      其他模块通过 from config import settings 拿到的是 **当时的引用副本**。
      如果这里创建新实例并赋值给 settings，其他模块持有的旧引用不会自动更新。

    解决方案：原地更新属性
      构造一个新的 Settings() 实例读取最新 .env，然后把它的属性字典
      覆盖写入现有 settings 实例的 __dict__。这样所有持有 settings 引用的
      模块（包括 create_llm() 中的 settings.BASE_URL 等）自动看到新值。

    调用时机：
      ConfigService.save_llm_config() 写入 .env 后立即调用此函数，
      使下一次 build_agent_graph() → create_llm() 读到最新配置。
    """
    global settings
    # 从 .env 文件重新构造一个全新的 Settings 实例
    new_settings = Settings()
    # 将新实例的所有字段值原地写入现有单例的 __dict__
    # 效果：settings.BASE_URL、settings.API_KEY 等属性立即变为新值
    # 而其他模块通过 from config import settings 拿到的引用不受影响（仍然是同一个对象）
    settings.__dict__.update(new_settings.__dict__)
    logger.info("[Config] settings 已热重载（BASE_URL=%s, MODEL_NAME=%s）",
                settings.BASE_URL, settings.MODEL_NAME)


# 仅在 reload_settings() 中使用，避免循环 import
import logging
logger = logging.getLogger(__name__)

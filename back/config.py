"""
配置管理模块

使用 pydantic-settings 的 BaseSettings 实现配置管理，
自动从环境变量 / .env 文件加载配置，并提供类型校验和范围校验。
支持兼容 OpenAI 格式的第三方 API（DeepSeek、智谱、Moonshot 等）。
"""

import os
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用配置类

    通过 BaseSettings 自动从环境变量读取配置值，
    同时支持 .env 文件。配置值会进行类型校验和范围校验。
    """

    # ---- 模型配置 ----
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略 .env 中未定义的变量
    )

    # ---- LLM 配置（兼容 OpenAI 格式的 API） ----
    API_KEY: str = Field(default="", description="LLM API 密钥")
    BASE_URL: str = Field(
        default="https://api.deepseek.com", description="API 基础地址"
    )
    MODEL_NAME: str = Field(default="deepseek-v4-flash", description="模型名称")
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

    # ---- 服务配置 ----
    HOST: str = Field(default="0.0.0.0", description="服务监听地址")
    PORT: int = Field(default=8000, gt=0, le=65535, description="服务端口")

    @field_validator("API_KEY")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """校验 API Key 是否已配置"""
        if not v or v == "your-api-key-here":
            import warnings
            warnings.warn(
                "API_KEY 未配置！请在 .env 文件或环境变量中设置有效的 API Key。",
                stacklevel=2,
            )
        return v


# 全局配置单例
settings = Settings()

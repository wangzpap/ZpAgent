"""
摘要中间件构建模块

根据配置决定是否创建 SummarizationMiddleware 实例。
当对话历史的 token 数超过阈值时，自动对早期消息做摘要压缩，
保留最近 N 条消息不动，将更早的消息压缩为一段摘要文本。

SummarizationMiddleware 工作原理（LangChain 官方中间件）：
  - 在 before_model 钩子中检查当前消息历史的 token 总量
  - 超过 max_tokens_before_summary 时触发摘要
  - 用指定的 LLM 对早期消息生成摘要，替换原始消息
  - 保留最近 messages_to_keep 条消息不变
  - 摘要消息以 "## Previous conversation summary:" 为前缀插入

配置来源：config.py 的 Settings 单例（从 .env 读取，支持热重载）
"""

import logging
from typing import Optional

from langchain.agents.middleware import SummarizationMiddleware

from config import settings
from llm import create_llm

logger = logging.getLogger(__name__)


def build_summarization_middleware() -> Optional[SummarizationMiddleware]:
    """
    根据当前配置构建摘要中间件实例

    读取 settings 中的 SUMMARY_* 字段：
      - SUMMARY_ENABLED: 总开关，False 时直接返回 None
      - SUMMARY_MODEL: 摘要专用模型（空字符串表示复用主模型）
      - SUMMARY_MAX_TOKENS: 触发摘要的 token 阈值
      - SUMMARY_MESSAGES_TO_KEEP: 摘要后保留最近消息数

    Returns:
        SummarizationMiddleware 实例，或 None（未启用时）
    """
    if not settings.SUMMARY_ENABLED:
        logger.debug("[Middleware] 摘要中间件未启用")
        return None

    # 确定摘要使用的模型：
    # SUMMARY_MODEL 非空时用它单独创建一个 LLM 实例（可以用更便宜的模型做摘要）
    # 为空时复用主模型（create_llm() 读取 settings.MODEL_NAME）
    if settings.SUMMARY_MODEL:
        # 临时覆盖 MODEL_NAME 创建摘要专用 LLM
        # create_llm() 内部读取 settings 的字段，这里通过参数覆盖 model_name
        summary_llm = create_llm(model_name_override=settings.SUMMARY_MODEL)
        logger.info(
            "[Middleware] 摘要中间件使用专用模型: %s", settings.SUMMARY_MODEL
        )
    else:
        summary_llm = create_llm()
        logger.info(
            "[Middleware] 摘要中间件复用主模型: %s", settings.MODEL_NAME
        )

    middleware = SummarizationMiddleware(
        model=summary_llm,
        max_tokens_before_summary=settings.SUMMARY_MAX_TOKENS,
        messages_to_keep=settings.SUMMARY_MESSAGES_TO_KEEP,
    )

    logger.info(
        "[Middleware] 摘要中间件已创建 | max_tokens=%d | messages_to_keep=%d",
        settings.SUMMARY_MAX_TOKENS,
        settings.SUMMARY_MESSAGES_TO_KEEP,
    )

    return middleware

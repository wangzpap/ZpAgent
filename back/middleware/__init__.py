"""
中间件管理包

统一管理和组装所有 Agent 中间件。未来新增中间件只需：
  1. 在本包下新建 xxx.py（如 pii.py, fallback.py）
  2. 实现 build_xxx_middleware() 函数
  3. 在下方 build_middleware_list() 中注册调用

agent/graph.py 只需调用 build_middleware_list() 获取完整中间件列表，
无需关心中间件的具体细节和数量。
"""

import logging
from typing import List, Any

from middleware.summarization import build_summarization_middleware

logger = logging.getLogger(__name__)


def build_middleware_list() -> List[Any]:
    """
    组装所有已启用的中间件（工厂函数）

    按顺序收集各中间件构建函数的返回值，跳过返回 None 的（未启用）。
    中间件的顺序决定执行优先级（列表前面的先执行）。

    当前支持的中间件：
      - SummarizationMiddleware: 对话历史摘要压缩

    未来可扩展：
      - PIIMiddleware: 个人敏感信息检测与脱敏
      - ModelFallbackMiddleware: 主模型失败时切换备用模型
      - ContextEditingMiddleware: 上下文编辑（清理旧工具调用等）

    Returns:
        已启用的中间件实例列表（可能为空列表）
    """
    middleware_list = []

    # ---- 摘要压缩中间件 ----
    summarization = build_summarization_middleware()
    if summarization:
        middleware_list.append(summarization)

    # ---- 未来在此追加更多中间件 ----
    # pii = build_pii_middleware()
    # if pii:
    #     middleware_list.append(pii)

    if middleware_list:
        logger.info(
            "[Middleware] 已组装 %d 个中间件: %s",
            len(middleware_list),
            [type(m).__name__ for m in middleware_list],
        )
    else:
        logger.debug("[Middleware] 无已启用的中间件")

    return middleware_list

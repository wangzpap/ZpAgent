"""
LLM 客户端模块

使用 LangChain 的 ChatOpenAI 封装与大模型的交互。

ChatOpenAI 是什么？
  - LangChain 对 OpenAI Chat API 的封装类
  - 虽然名字叫 "OpenAI"，但通过修改 base_url 可以接入任何兼容 OpenAI 格式的服务
  - 例如：DeepSeek、智谱 GLM、Moonshot（Kimi）等都支持 OpenAI 兼容接口
  - 好处：换模型只需改配置，不用改代码（策略模式 / 面向接口编程）

该工厂函数被 agent/graph.py 调用，用于构建 LangGraph Agent 时创建 LLM 实例。
"""

# ChatOpenAI: LangChain 提供的 OpenAI 兼容 LLM 客户端
# 它封装了与大模型 API 的所有交互细节（请求构建、重试、流式输出等）
from langchain_openai import ChatOpenAI
from config import settings


def create_llm() -> ChatOpenAI:
    """
    创建 ChatOpenAI 实例（工厂函数）

    工厂函数 = 专门用来创建对象的函数，把创建逻辑集中在一处。
    好处：如果将来要换 LLM 实现或加参数，只改这一个函数就行。

    返回的 ChatOpenAI 实例支持：
      - 普通调用: response = await llm.ainvoke(messages)  → 等待完整回复
      - 流式调用: async for chunk in llm.astream(messages)  → 逐 token 输出
      - 工具绑定: llm.bind_tools(tools)  → 让 LLM 知道有哪些工具可用

    Returns:
        配置好的 ChatOpenAI 实例
    """
    return ChatOpenAI(
        api_key=settings.API_KEY,        # API 密钥（鉴权用）
        base_url=settings.BASE_URL,      # API 地址（决定调用哪个服务商）
        model=settings.MODEL_NAME,       # 模型名称（如 deepseek-v4-flash）
        temperature=settings.TEMPERATURE, # 温度：越高越随机，越低越确定
        max_completion_tokens=settings.MAX_COMPLETION_TOKENS,  # 最大生成 token 数
        request_timeout=settings.REQUEST_TIMEOUT,  # 单次请求超时时间
        max_retries=settings.MAX_RETRIES,           # 请求失败时的最大重试次数
    )

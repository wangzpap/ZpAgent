"""
内置工具集

使用 LangChain 的 @tool 装饰器定义工具，框架会自动：
  - 根据函数签名生成参数 JSON Schema
  - 根据 docstring 生成工具描述
  - 封装为 BaseTool 实例，可被 Agent 的 bind_tools() 使用

@tool 装饰器工作原理：
  1. 读取函数的 docstring → 作为工具的 description（告诉 LLM 这个工具能做什么）
  2. 读取函数参数的类型注解和默认值 → 自动生成 JSON Schema（告诉 LLM 需要传什么参数）
  3. 将函数封装为 BaseTool 对象 → 可以被 LangGraph Agent 自动调用

设计原则：
  - 所有工具必须返回真实、有效的结果，不使用 mock 数据
  - 不依赖外部 API，纯 Python 标准库实现，保证开箱即用

当前内置 2 个工具：
  - get_datetime: 获取当前日期时间（支持时区）
  - base64_tool:  Base64 编码/解码
"""

import base64
import json
from datetime import datetime, timezone, timedelta

from langchain.tools import tool


@tool
def get_datetime(timezone_offset: int = 8) -> str:
    """
    获取当前的日期和时间信息。

    返回格式化的日期、时间、星期、时间戳等完整时间信息。
    默认返回北京时间（UTC+8），可通过 timezone_offset 参数调整时区。

    Args:
        timezone_offset: 时区偏移量（小时），默认 8（北京时间/东八区）。
            常用值：0=UTC, 8=北京/新加坡, 9=东京, -5=纽约, -8=洛杉矶
    """
    # timezone(timedelta(hours=...)): 创建指定偏移量的时区对象
    tz = timezone(timedelta(hours=timezone_offset))
    now = datetime.now(tz)

    # weekday() 返回 0-6（0=周一，6=周日），用字典映射为中文
    weekday_map = {
        0: "星期一", 1: "星期二", 2: "星期三",
        3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日",
    }

    # 构造时区显示名称，如 "UTC+8"、"UTC-5"
    tz_sign = "+" if timezone_offset >= 0 else ""
    tz_name = f"UTC{tz_sign}{timezone_offset}"

    return json.dumps(
        {
            "date": now.strftime("%Y年%m月%d日"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": weekday_map[now.weekday()],
            "timezone": tz_name,
            "iso_format": now.isoformat(),
            "timestamp": int(now.timestamp()),
        },
        ensure_ascii=False,
    )


@tool
def base64_tool(text: str, operation: str = "encode") -> str:
    """
    对文本进行 Base64 编码或解码。

    Base64 是一种将二进制数据转换为 ASCII 字符的编码方式，
    常用于数据传输、图片内嵌、URL 参数编码等场景。

    Args:
        text: 要处理的文本内容。编码时传入原始文本，解码时传入 Base64 字符串。
        operation: 操作类型。"encode" 表示编码（文本→Base64），"decode" 表示解码（Base64→文本）。默认 "encode"。
    """
    try:
        if operation == "encode":
            # 编码流程：字符串 → UTF-8 字节 → Base64 字节 → ASCII 字符串
            encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
            return json.dumps(
                {"operation": "encode", "input": text, "output": encoded},
                ensure_ascii=False,
            )
        elif operation == "decode":
            # 解码流程：Base64 字符串 → Base64 字节 → UTF-8 字节 → 字符串
            decoded = base64.b64decode(text.encode("ascii")).decode("utf-8")
            return json.dumps(
                {"operation": "decode", "input": text, "output": decoded},
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {"error": f"不支持的操作类型: {operation}，请使用 encode 或 decode"},
                ensure_ascii=False,
            )
    except Exception as e:
        return json.dumps({"error": f"操作失败：{str(e)}"}, ensure_ascii=False)


# 所有内置工具列表，供 ToolRegistry 批量注册
# 装饰器 @tool 把函数变成了 BaseTool 对象，所以这个列表里装的是工具对象而非普通函数
BUILTIN_TOOLS = [get_datetime, base64_tool]

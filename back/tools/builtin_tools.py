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

当前内置 3 个工具：
  - get_location: 查询当前位置（模拟数据）
  - get_datetime: 查询当前时间
  - get_weather:  根据城市和日期查询天气（模拟数据）
"""

import json
import random
import time
from datetime import datetime

# @tool 是 LangChain 提供的装饰器（装饰器 = 在函数定义前用 @ 语法包裹函数）
# 效果类似 Java 的 @Bean 或 Spring 的 @Component，声明一个组件并注册到框架中
from langchain.tools import tool


@tool
def get_location() -> str:
    """
    查询用户当前所在的位置信息。

    注意：docstring 很重要！
    LLM 根据这段文字判断"用户的请求是否需要调用这个工具"。
    所以描述要简洁准确，让 LLM 能理解工具的用途。
    """
    # json.dumps: 将 Python 字典转为 JSON 字符串
    # ensure_ascii=False: 允许中文直接输出，不转义为 \uXXXX
    # time.sleep(3): 模拟接口延迟，测试前端加载状态的表现
    time.sleep(3)
    return json.dumps(
        {
            "city": "杭州",
            "province": "浙江省",
            "country": "中国",
            "latitude": 30.25,
            "longitude": 120.17,
        },
        ensure_ascii=False,
    )


@tool
def get_datetime() -> str:
    """查询当前的日期和时间信息。"""
    now = datetime.now()
    # weekday_map: Python 字典，将数字映射为中文星期名称
    # now.weekday() 返回 0-6（0=周一，6=周日）
    weekday_map = {
        0: "星期一", 1: "星期二", 2: "星期三",
        3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日",
    }
    # strftime: 日期格式化方法
    # %Y=四位年份, %m=两位月份, %d=两位日期, %H=两位小时, %M=分钟, %S=秒
    return json.dumps(
        {
            "date": now.strftime("%Y年%m月%d日"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": weekday_map[now.weekday()],
            # timestamp(): 将日期转为 Unix 时间戳（秒数），int() 取整
            "timestamp": int(now.timestamp()),
        },
        ensure_ascii=False,
    )


@tool
def get_weather(city: str, date: str = "今天") -> str:
    """
    根据城市和日期查询天气信息。

    注意 docstring 中的 Args 部分：
      LangChain 会将这些参数说明也提取出来告诉 LLM，
      让 LLM 知道需要传入什么参数、每个参数的含义。

    Args:
        city: 城市名称，如：杭州、北京、上海
        date: 查询日期，如：今天、明天、后天，默认今天
    """
    # 已收录城市的模拟天气数据
    # 实际项目中这里会调用真实的天气 API
    mock_data = {
        "杭州": {"temp_high": 28, "temp_low": 20, "weather": "多云转晴", "humidity": 65, "wind": "东风2级"},
        "北京": {"temp_high": 30, "temp_low": 18, "weather": "晴", "humidity": 35, "wind": "北风3级"},
        "上海": {"temp_high": 27, "temp_low": 22, "weather": "多云", "humidity": 72, "wind": "东南风2级"},
        "广州": {"temp_high": 33, "temp_low": 25, "weather": "雷阵雨", "humidity": 85, "wind": "南风2级"},
        "深圳": {"temp_high": 32, "temp_low": 26, "weather": "阴", "humidity": 80, "wind": "南风3级"},
        "成都": {"temp_high": 25, "temp_low": 18, "weather": "小雨", "humidity": 78, "wind": "微风"},
        "武汉": {"temp_high": 31, "temp_low": 23, "weather": "晴", "humidity": 55, "wind": "南风2级"},
        "西安": {"temp_high": 26, "temp_low": 15, "weather": "多云", "humidity": 40, "wind": "西北风2级"},
    }

    # 查询已知城市 or 为未知城市随机生成数据
    if city in mock_data:
        data = mock_data[city]
    else:
        # random.randint(a, b): 生成 [a, b] 范围内的随机整数
        # random.choice(list): 从列表中随机选择一个元素
        temp_high = random.randint(22, 35)
        data = {
            "temp_high": temp_high,
            "temp_low": temp_high - random.randint(5, 12),
            "weather": random.choice(["晴", "多云", "阴", "小雨", "大风"]),
            "humidity": random.randint(30, 90),
            "wind": "微风",
        }

    # 返回 JSON 字符串（LLM 会解析这个字符串来理解工具的执行结果）
    # 格式化的温度字符串：f"{值}°C"，f-string 是 Python 的字符串模板语法
    return json.dumps(
        {
            "city": city,
            "date": date,
            "weather": data["weather"],
            "temp_high": f"{data['temp_high']}°C",
            "temp_low": f"{data['temp_low']}°C",
            "humidity": f"{data['humidity']}%",
            "wind": data["wind"],
        },
        ensure_ascii=False,
    )


# 所有内置工具列表，供 ToolRegistry 批量注册
# 装饰器 @tool 把函数变成了 BaseTool 对象，所以这个列表里装的是工具对象而非普通函数
BUILTIN_TOOLS = [get_location, get_datetime, get_weather]

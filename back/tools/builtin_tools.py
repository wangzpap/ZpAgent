"""
内置工具集（基于 LangChain @tool 装饰器）

提供 3 个工具：
  - get_location:  查询当前位置（模拟输出）
  - get_datetime:  查询当前时间
  - get_weather:   根据时间和地点查询天气（模拟数据）
"""

import json
import random
from datetime import datetime

from langchain_core.tools import tool


# ============================================
# 查询当前位置（模拟）
# ============================================
@tool
def get_location() -> str:
    """查询用户当前所在的位置。"""
    # 模拟定位结果
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


# ============================================
# 查询当前时间
# ============================================
@tool
def get_datetime() -> str:
    """查询当前的日期和时间信息。"""
    now = datetime.now()
    weekday_map = {
        0: "星期一", 1: "星期二", 2: "星期三",
        3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日",
    }
    return json.dumps(
        {
            "date": now.strftime("%Y年%m月%d日"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": weekday_map[now.weekday()],
            "timestamp": int(now.timestamp()),
        },
        ensure_ascii=False,
    )


# ============================================
# 根据时间和地点查询天气（模拟）
# ============================================
@tool
def get_weather(city: str, date: str = "今天") -> str:
    """根据城市和日期查询天气信息。

    Args:
        city: 城市名称，如：杭州、北京、上海
        date: 查询日期，如：今天、明天、后天，默认今天
    """
    # 模拟天气数据
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

    if city in mock_data:
        data = mock_data[city]
    else:
        # 未收录城市随机生成
        temp_high = random.randint(22, 35)
        data = {
            "temp_high": temp_high,
            "temp_low": temp_high - random.randint(5, 12),
            "weather": random.choice(["晴", "多云", "阴", "小雨", "大风"]),
            "humidity": random.randint(30, 90),
            "wind": "微风",
        }

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


# ============================================
# 所有内置工具列表
# ============================================
BUILTIN_TOOLS = [get_location, get_datetime, get_weather]

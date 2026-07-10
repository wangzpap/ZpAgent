"""
统一 API 响应格式

定义所有 JSON 接口（SSE 流式接口除外）的统一返回格式。
前端通过 code 字段判断请求是否成功（0 = 成功），
data 承载主数据，extra 承载附加信息。
"""

from typing import Optional, Any

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    """
    统一 API 响应格式

    所有 JSON 接口（SSE 流式接口除外）统一使用此格式返回。
    前端通过 code 字段判断请求是否成功（0 = 成功），
    data 承载主数据，extra 承载附加信息。

    示例:
        成功: {"code": 0, "msg": "ok", "data": {...}, "extra": null}
        失败: {"code": 404, "msg": "会话不存在", "data": null, "extra": null}
    """
    code: int = Field(0, description="业务状态码，0 表示成功")
    msg: str = Field("ok", description="提示信息")
    data: Optional[Any] = Field(None, description="主数据")
    extra: Optional[Any] = Field(None, description="附加信息")

    @staticmethod
    def ok(data: Any = None, msg: str = "ok", extra: Any = None) -> "ApiResponse":
        """构建成功响应，返回实例"""
        return ApiResponse(code=0, msg=msg, data=data, extra=extra)

    @staticmethod
    def fail(code: int, msg: str, data: Any = None, extra: Any = None) -> "ApiResponse":
        """构建失败响应，返回实例"""
        return ApiResponse(code=code, msg=msg, data=data, extra=extra)

    def to_dict(self) -> dict:
        """将实例转换为字典"""
        return self.model_dump()

"""
API 响应格式化 - StockQuant Pro
统一成功/失败响应格式，与 backend/API.md 约定一致。
"""
from flask import jsonify
from typing import Any, Optional


def success(
    data: Any = None,
    message: str = "success",
    code: int = 200,
) -> Any:
    """
    成功响应。

    Args:
        data: 响应数据，可为 dict/list/单值
        message: 响应消息
        code: 响应码

    Returns:
        Flask JSON 响应
    """
    return jsonify(
        {
            "code": code,
            "data": data,
            "message": message,
        }
    )


def error(
    message: str = "error",
    code: int = 400,
    data: Optional[Any] = None,
) -> Any:
    """
    错误响应。

    Args:
        message: 错误描述
        code: 错误码，4xx 客户端错误，5xx 服务端错误
        data: 附加数据（可选）

    Returns:
        Flask JSON 响应
    """
    return jsonify(
        {
            "code": code,
            "data": data,
            "message": message,
        }
    )

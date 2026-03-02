"""
策略管理 API - StockQuant Pro
策略 CRUD、列表、详情、模板。
"""
from flask import Blueprint, request
from utils.response import success, error
from services.strategy_service import StrategyService

strategy_bp = Blueprint("strategy", __name__, url_prefix="/api/strategy")
strategy_service = StrategyService()


@strategy_bp.route("/list", methods=["GET"])
def get_strategy_list():
    """
    获取策略列表（支持筛选与分页）。

    Query Params:
        type: 策略类型（select/trade/combo）
        status: 状态（draft/testing/verified/running）
        page: 页码（默认1）
        page_size: 每页数量（默认20）

    Returns:
        {
            "code": 200,
            "data": {
                "items": [策略列表],
                "total": 总数,
                "page": 当前页,
                "page_size": 每页数量
            },
            "message": "success"
        }
    """
    try:
        type_param = request.args.get("type")
        status = request.args.get("status")
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        
        # 获取所有策略（先简单实现，后续可优化为数据库分页）
        all_strategies = strategy_service.get_strategy_list(type=type_param, status=status)
        
        # 手动分页
        total = len(all_strategies)
        start = (page - 1) * page_size
        end = start + page_size
        items = all_strategies[start:end]
        
        result = {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }
        return success(data=result)
    except Exception as e:
        return error(message=f"查询失败：{str(e)}", code=500)


@strategy_bp.route("/<int:strategy_id>", methods=["GET"])
def get_strategy(strategy_id: int):
    """
    获取策略详情。

    Path Params:
        strategy_id: 策略ID

    Returns:
        {
            "code": 200,
            "data": {策略详情},
            "message": "success"
        }
    """
    try:
        result = strategy_service.get_strategy(strategy_id)
        if result is None:
            return error(message="策略不存在", code=404)
        return success(data=result)
    except Exception as e:
        return error(message=f"查询失败：{str(e)}", code=500)


@strategy_bp.route("/create", methods=["POST"])
def create_strategy():
    """
    创建策略。

    Request Body:
        {
            "name": "双均线策略",
            "type": "trade",
            "description": "...",
            "params": {...},
            "code": "..."
        }

    Returns:
        {
            "code": 200,
            "data": {创建的策略},
            "message": "创建成功"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return error(message="请求体为空", code=400)

        name = data.get("name")
        type_param = data.get("type")
        if not name or not type_param:
            return error(message="缺少必填参数：name、type", code=400)

        result = strategy_service.create_strategy(
            name=name,
            type=type_param,
            description=data.get("description"),
            params=data.get("params"),
            code=data.get("code"),
        )
        return success(data=result, message="创建成功")
    except Exception as e:
        return error(message=f"创建失败：{str(e)}", code=500)


@strategy_bp.route("/<int:strategy_id>", methods=["PUT"])
def update_strategy(strategy_id: int):
    """
    更新策略。

    Path Params:
        strategy_id: 策略ID

    Request Body:
        {
            "name": "...",
            "status": "verified",
            ...
        }

    Returns:
        {
            "code": 200,
            "data": {更新后的策略},
            "message": "更新成功"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return error(message="请求体为空", code=400)

        result = strategy_service.update_strategy(
            strategy_id=strategy_id,
            name=data.get("name"),
            type=data.get("type"),
            status=data.get("status"),
            description=data.get("description"),
            params=data.get("params"),
            code=data.get("code"),
            backtest_result=data.get("backtest_result"),
        )
        if result is None:
            return error(message="策略不存在", code=404)
        return success(data=result, message="更新成功")
    except Exception as e:
        return error(message=f"更新失败：{str(e)}", code=500)


@strategy_bp.route("/<int:strategy_id>", methods=["DELETE"])
def delete_strategy(strategy_id: int):
    """
    删除策略。

    Path Params:
        strategy_id: 策略ID

    Returns:
        {
            "code": 200,
            "data": null,
            "message": "删除成功"
        }
    """
    try:
        success_flag = strategy_service.delete_strategy(strategy_id)
        if not success_flag:
            return error(message="策略不存在", code=404)
        return success(message="删除成功")
    except Exception as e:
        return error(message=f"删除失败：{str(e)}", code=500)


@strategy_bp.route("/templates", methods=["GET"])
def get_strategy_templates():
    """
    获取策略模板。

    Returns:
        {
            "code": 200,
            "data": [模板列表],
            "message": "success"
        }
    """
    try:
        result = strategy_service.get_strategy_templates()
        return success(data=result)
    except Exception as e:
        return error(message=f"查询失败：{str(e)}", code=500)

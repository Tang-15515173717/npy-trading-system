"""
策略管理 API - StockQuant Pro SaaS
策略 CRUD、列表、详情、模板，带租户隔离和限制检查。
"""
from flask import Blueprint, request
from flask_login import login_required, current_user
from utils.response import success, error
from services.strategy_service import StrategyService
from utils.subscription_limits import can_create_strategy

strategy_bp = Blueprint("strategy", __name__, url_prefix="/api/strategy")
strategy_service = StrategyService()


@strategy_bp.route("/list", methods=["GET"])
def get_strategy_list():
    """
    获取策略列表（带租户隔离）
    无需登录，未登录用户返回空列表
    """
    try:
        # 尝试获取当前用户的租户ID
        tenant_id = None
        try:
            from flask_login import current_user
            if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                tenant_id = current_user.tenant_id
        except:
            pass

        # 如果没有租户ID，返回空列表
        if not tenant_id:
            return success(data={
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": 20
            })

        type_param = request.args.get("type")
        status = request.args.get("status")
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))

        # 获取该租户的策略
        all_strategies = strategy_service.get_strategy_list(
            type=type_param,
            status=status,
            tenant_id=tenant_id  # 🆕 租户隔离
        )

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
@login_required
def get_strategy(strategy_id: int):
    """
    获取策略详情（带租户隔离检查）
    """
    try:
        tenant_id = current_user.tenant_id
        result = strategy_service.get_strategy(strategy_id, tenant_id=tenant_id)
        
        if result is None:
            return error(message="策略不存在或无权访问", code=404)
        return success(data=result)
    except Exception as e:
        return error(message=f"查询失败：{str(e)}", code=500)


@strategy_bp.route("/create", methods=["POST"])
@login_required
def create_strategy():
    """
    创建策略（带数量限制检查）
    """
    try:
        tenant_id = current_user.tenant_id
        
        # 🆕 检查是否可以创建策略
        can_create, error_msg = can_create_strategy(tenant_id)
        if not can_create:
            return error(
                message=error_msg,
                code=403,
                data={"need_upgrade": True}
            )
        
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
            tenant_id=tenant_id  # 🆕 添加租户ID
        )
        return success(data=result, message="创建成功")
    except Exception as e:
        return error(message=f"创建失败：{str(e)}", code=500)


@strategy_bp.route("/<int:strategy_id>", methods=["PUT"])
@login_required
def update_strategy(strategy_id: int):
    """
    更新策略（带租户隔离检查）
    """
    try:
        tenant_id = current_user.tenant_id
        data = request.get_json()
        if not data:
            return error(message="请求体为空", code=400)

        result = strategy_service.update_strategy(
            strategy_id=strategy_id,
            tenant_id=tenant_id,  # 🆕 租户隔离
            name=data.get("name"),
            type=data.get("type"),
            status=data.get("status"),
            description=data.get("description"),
            params=data.get("params"),
            code=data.get("code"),
            backtest_result=data.get("backtest_result"),
        )
        if result is None:
            return error(message="策略不存在或无权访问", code=404)
        return success(data=result, message="更新成功")
    except Exception as e:
        return error(message=f"更新失败：{str(e)}", code=500)


@strategy_bp.route("/<int:strategy_id>", methods=["DELETE"])
@login_required
def delete_strategy(strategy_id: int):
    """
    删除策略（带租户隔离检查）
    """
    try:
        tenant_id = current_user.tenant_id
        success_flag = strategy_service.delete_strategy(strategy_id, tenant_id=tenant_id)
        
        if not success_flag:
            return error(message="策略不存在或无权访问", code=404)
        return success(message="删除成功")
    except Exception as e:
        return error(message=f"删除失败：{str(e)}", code=500)


@strategy_bp.route("/templates", methods=["GET"])
def get_strategy_templates():
    """
    获取策略模板
    无需登录
    """
    try:
        result = strategy_service.get_strategy_templates()
        return success(data=result)
    except Exception as e:
        return error(message=f"查询失败：{str(e)}", code=500)

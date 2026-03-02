"""
交易管理 API - StockQuant Pro
模拟交易启停、状态查询、持仓查询、交易记录查询。
"""
from flask import Blueprint, request
from utils.response import success, error
from services.trade_service import TradeService

trade_bp = Blueprint("trade", __name__, url_prefix="/api/trade")
trade_service = TradeService()


@trade_bp.route("/account", methods=["GET"])
def get_account():
    """
    获取账户信息（兼容前端接口）。
    
    Query Params:
        session_id: 会话ID（可选，不传则返回最新运行中的会话或模拟数据）
    
    Returns:
        {
            "code": 200,
            "data": {
                "total_asset": 1000000,
                "available": 850000,
                "market_value": 150000,
                "frozen": 0,
                "today_profit": 5230.50,
                "today_profit_pct": 0.52
            },
            "message": "success"
        }
    """
    try:
        session_id = request.args.get("session_id")
        
        # 如果没有session_id，返回模拟数据
        if not session_id:
            return success(data={
                "total_asset": 1000000.0,
                "available": 850000.0,
                "market_value": 150000.0,
                "frozen": 0.0,
                "today_profit": 5230.50,
                "today_profit_pct": 0.52
            })
        
        # 有session_id则获取真实数据
        status = trade_service.get_simulation_status(session_id=session_id)
        return success(data={
            "total_asset": status.get("total_assets", 0),
            "available": status.get("current_capital", 0),
            "market_value": status.get("total_market_value", 0),
            "frozen": 0,
            "today_profit": status.get("total_pnl", 0),
            "today_profit_pct": (status.get("total_pnl", 0) / status.get("initial_capital", 1000000)) * 100
        })
    except Exception as e:
        return error(message=f"查询失败：{str(e)}", code=500)


@trade_bp.route("/orders", methods=["GET"])
def get_orders():
    """
    获取委托订单列表（兼容前端接口）。
    
    Query Params:
        session_id: 会话ID（可选）
        status: 订单状态（可选）
        date: 日期（可选）
    
    Returns:
        {
            "code": 200,
            "data": [订单列表],
            "message": "success"
        }
    """
    try:
        session_id = request.args.get("session_id")
        
        # 如果没有session_id，返回空数组
        if not session_id:
            return success(data=[])
        
        # TODO: 实现真实的订单查询逻辑
        # 暂时返回空数组
        return success(data=[])
    except Exception as e:
        return error(message=f"查询失败：{str(e)}", code=500)


@trade_bp.route("/simulation/start", methods=["POST"])
def start_simulation():
    """
    启动模拟交易。

    Request Body:
        {
            "strategy_id": 1,
            "initial_capital": 1000000
        }

    Returns:
        {
            "code": 200,
            "data": {
                "session_id": "sim_20260129_160000_001",
                "status": "running",
                ...
            },
            "message": "模拟交易已启动"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return error(message="请求体为空", code=400)

        strategy_id = data.get("strategy_id")
        if not strategy_id:
            return error(message="缺少必填参数：strategy_id", code=400)

        initial_capital = data.get("initial_capital", 1000000)

        result = trade_service.start_simulation(
            strategy_id=strategy_id,
            initial_capital=initial_capital,
        )
        return success(data=result, message="模拟交易已启动")
    except ValueError as e:
        return error(message=str(e), code=400)
    except Exception as e:
        return error(message=f"启动失败：{str(e)}", code=500)


@trade_bp.route("/simulation/stop", methods=["POST"])
def stop_simulation():
    """
    停止模拟交易。

    Request Body:
        {
            "session_id": "sim_20260129_160000_001"
        }

    Returns:
        {
            "code": 200,
            "data": {"session_id": "...", "status": "stopped", ...},
            "message": "模拟交易已停止"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return error(message="请求体为空", code=400)

        session_id = data.get("session_id")
        if not session_id:
            return error(message="缺少必填参数：session_id", code=400)

        result = trade_service.stop_simulation(session_id=session_id)
        return success(data=result, message="模拟交易已停止")
    except ValueError as e:
        return error(message=str(e), code=400)
    except Exception as e:
        return error(message=f"停止失败：{str(e)}", code=500)


@trade_bp.route("/simulation/status", methods=["GET"])
def get_simulation_status():
    """
    获取模拟交易状态。

    Query Params:
        session_id: 会话ID（可选，不传则返回最新运行中的会话）

    Returns:
        {
            "code": 200,
            "data": {
                "session_id": "sim_20260129_160000_001",
                "status": "running",
                "current_capital": 950000,
                "positions_count": 3,
                "total_market_value": 230000,
                "total_pnl": 15000,
                "total_assets": 1180000
            },
            "message": "success"
        }
    """
    try:
        session_id = request.args.get("session_id")
        result = trade_service.get_simulation_status(session_id=session_id)
        return success(data=result)
    except Exception as e:
        return error(message=f"查询失败：{str(e)}", code=500)


@trade_bp.route("/positions", methods=["GET"])
def get_positions():
    """
    获取持仓列表。

    Query Params:
        session_id: 会话ID（可选，不传则返回模拟数据）

    Returns:
        {
            "code": 200,
            "data": [持仓列表],
            "message": "success"
        }
    """
    try:
        session_id = request.args.get("session_id")
        
        # 如果没有session_id，返回模拟数据
        if not session_id:
            return success(data=[])

        result = trade_service.get_positions(session_id=session_id)
        return success(data=result)
    except ValueError as e:
        return error(message=str(e), code=400)
    except Exception as e:
        return error(message=f"查询失败：{str(e)}", code=500)


@trade_bp.route("/records", methods=["GET"])
def get_trade_records():
    """
    获取交易记录。v2.1 支持 factor_combo_id、strategy_id、signal_reason 筛选；
    无 session_id 时查询回测交易记录（BacktestTrade），含双驱动字段。
    """
    try:
        session_id = request.args.get("session_id")
        ts_code = request.args.get("ts_code")
        direction = request.args.get("direction")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        _fc = request.args.get("factor_combo_id")
        factor_combo_id = int(_fc) if _fc not in (None, "") else None
        _sid = request.args.get("strategy_id")
        strategy_id = int(_sid) if _sid not in (None, "") else None
        signal_reason = request.args.get("signal_reason")
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)

        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 200:
            page_size = 200

        if session_id:
            result = trade_service.get_trades(
                session_id=session_id,
                ts_code=ts_code,
                page=page,
                page_size=page_size,
            )
            return success(data=result)

        result = trade_service.get_backtest_trade_records(
            ts_code=ts_code,
            direction=direction,
            start_date=start_date,
            end_date=end_date,
            factor_combo_id=factor_combo_id,
            strategy_id=strategy_id,
            signal_reason=signal_reason,
            page=page,
            page_size=page_size,
        )
        return success(data=result)
    except ValueError as e:
        return error(message=str(e), code=400)
    except Exception as e:
        return error(message=f"查询失败：{str(e)}", code=500)

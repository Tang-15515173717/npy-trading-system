"""
每日模拟观测系统 API - StockQuant Pro
=====================================

功能：
1. 策略管理：创建、编辑、删除观测策略
2. 观测记录：查看每日观测结果
3. 交易记录：查看模拟交易明细
4. 数据同步：触发数据同步和补齐
5. 统计汇总：收益统计、胜率分析

作者：Claude Code
日期：2026-02-11
"""
from flask import Blueprint, request
from datetime import datetime
from utils.response import success, error
from utils.database import db
from utils.auth_decorator import token_required, optional_token, get_current_tenant_id
from utils.subscription_decorator import check_subscription, check_feature_limit
from models.daily_observer import (
    DailyObserverStrategy,
    DailyObserverRecord,
    DailyObserverTrade
)
from models.stock import Stock
from models.bar_data import BarData
from services.scoring_engines.registry import list_engines
from services.recommendation_service import record_recommendation, get_recommendation_history
import json
import logging

logger = logging.getLogger(__name__)

daily_observer_bp = Blueprint("daily_observer", __name__, url_prefix="/api/daily-observer")


# ============================================================================
# 合规改造 - 辅助函数
# ============================================================================

DISCLAIMER_TEMPLATE = """
⚠️ 重要声明

本系统提供的所有数据和分析结果，仅供研究学习使用，不构成任何投资建议。

1. 历史表现不代表未来收益
2. 因子筛选结果基于历史数据计算
3. 投资有风险，决策需谨慎
4. 用户应根据自身情况独立判断

使用本系统即表示您已阅读并同意以上声明。
"""


def _simplify_signals(buy_signals: list, sell_signals: list = None) -> dict:
    """
    简化信号（合规改造）

    改造要点：
    1. ❌ 不输出：价格、数量、金额、买入建议
    2. ✅ 只输出：代码、名称、得分、排名、因子分析
    3. ✅ 必须加：免责声明

    Args:
        buy_signals: 买入信号列表
        sell_signals: 卖出信号列表（可选）

    Returns:
        改造后的筛选结果
    """
    filter_results = []

    # 处理买入信号 -> 筛选结果
    for signal in buy_signals:
        # 提取因子信息（如果有的话）
        factors = []
        reason_detail = signal.get("reason_detail", {})

        # 如果有详细的因子分析
        if "factor_analysis" in reason_detail:
            for factor_name, factor_data in reason_detail["factor_analysis"].items():
                factors.append({
                    "name": factor_name,
                    "value": str(factor_data.get("value", "N/A")),
                    "signal": factor_data.get("signal", "中性"),
                    "description": factor_data.get("description", "")
                })
        else:
            # 如果没有详细因子分析，使用基础信息
            factors.append({
                "name": "综合得分",
                "value": str(signal.get("score", 0)),
                "signal": "强势" if signal.get("score", 0) >= 8 else "中性",
                "description": f"排名第{signal.get('rank', 0)}"
            })

        # 构建筛选结果（去除敏感字段）
        item = {
            "ts_code": signal["ts_code"],
            "name": signal["name"],
            "score": signal.get("score", 0),
            "rank": signal.get("rank", 0),
            "factors": factors,
            "summary": "因子得分较高，符合筛选条件"  # 改造后的文案
        }

        # ❌ 不包含：price, amount, volume, buy_price
        # ❌ 不包含：建议买入、推荐买入

        filter_results.append(item)

    # 处理卖出信号 -> 不再符合条件
    if sell_signals:
        for signal in sell_signals:
            item = {
                "ts_code": signal["ts_code"],
                "name": signal["name"],
                "score": signal.get("score", 0),
                "rank": signal.get("rank", 0),
                "factors": [],
                "summary": "不再符合筛选条件",  # 改造后的文案
                "reason": signal.get("reason", "不再符合条件")
            }
            filter_results.append(item)

    return {
        "filter_results": filter_results,
        "disclaimer": DISCLAIMER_TEMPLATE.strip()
    }


def _transform_text(text: str) -> str:
    """
    文案转换（合规改造）

    转换规则：
    - "买入信号" -> "筛选结果"
    - "卖出信号" -> "不再符合条件"
    - "建议买入" -> "符合筛选条件"
    - "推荐买入" -> "因子得分较高"
    """
    text_mapping = {
        "买入信号": "筛选结果",
        "卖出信号": "不再符合条件",
        "建议买入": "符合筛选条件",
        "推荐买入": "因子得分较高",
        "预期收益": "历史表现",
        "目标价格": "参考点位",
        "止损价格": "风险参考"
    }

    for old, new in text_mapping.items():
        text = text.replace(old, new)

    return text


def _verify_strategy_ownership(strategy_id: int, tenant_id: int) -> DailyObserverStrategy:
    """
    验证策略所有权（租户隔离）
    
    Args:
        strategy_id: 策略ID
        tenant_id: 租户ID
    
    Returns:
        策略对象，如果不存在或无权访问则返回None
    """
    return DailyObserverStrategy.query.filter_by(
        id=strategy_id,
        tenant_id=tenant_id
    ).first()


def _generate_buy_reason(ts_code: str, trade_date: str, factor_configs: list, buy_decision: dict) -> dict:
    """
    生成详细的买入原因分析
    
    Args:
        ts_code: 股票代码
        trade_date: 交易日期
        factor_configs: 因子组合配置 [{factor_code, direction, weight}, ...]
        buy_decision: 买入决策 {ts_code, price, score, rank, ...}
    
    Returns:
        {
            "summary": "综合得分排名第2，动量强势",
            "factors": [
                {"name": "5日涨幅", "value": "6.37%", "signal": "强", "contribution": "正向"},
                ...
            ],
            "highlights": ["近5日上涨6.37%", "RSI=66处于强势区间"],
            "risks": ["波动率较高"]
        }
    """
    from models.factor_data import FactorData
    
    result = {
        "summary": "因子选股",
        "factors": [],
        "highlights": [],
        "risks": []
    }
    
    # 查询该股票的因子数据
    factor_data = FactorData.query.filter_by(
        ts_code=ts_code,
        trade_date=trade_date
    ).first()
    
    if not factor_data:
        result["summary"] = f"排名第{buy_decision.get('rank', '?')}，因子选股入选"
        return result
    
    # 因子中文名称映射
    factor_names = {
        "return_5d": "5日涨幅",
        "return_20d": "20日涨幅", 
        "return_60d": "60日涨幅",
        "rsi_14": "RSI(14)",
        "macd": "MACD",
        "macd_signal": "MACD信号线",
        "macd_hist": "MACD柱",
        "volatility_20d": "20日波动率",
        "reversal_5d": "5日反转",
        "turnover_rate": "换手率",
        "volume_ratio": "量比",
        "pe_ratio": "市盈率",
        "pb_ratio": "市净率"
    }
    
    highlights = []
    risks = []
    factors_detail = []
    
    # 分析每个因子
    for config in factor_configs:
        factor_code = config.get("factor_code")
        weight = config.get("weight", 0)
        direction = config.get("direction", "long")
        
        value = getattr(factor_data, factor_code, None)
        if value is None:
            continue
        
        factor_name = factor_names.get(factor_code, factor_code)
        
        # 格式化显示值和生成信号
        if "return" in factor_code:
            display_value = f"{value*100:.2f}%"
            if value > 0.05:
                signal = "强势"
                highlights.append(f"近期上涨{value*100:.1f}%")
            elif value > 0:
                signal = "上涨"
            elif value > -0.03:
                signal = "震荡"
            else:
                signal = "弱势"
                risks.append(f"{factor_name}下跌{abs(value)*100:.1f}%")
        elif factor_code == "rsi_14":
            display_value = f"{value:.1f}"
            if value >= 70:
                signal = "超买"
                risks.append(f"RSI={value:.0f}，接近超买区")
            elif value >= 50:
                signal = "强势"
                highlights.append(f"RSI={value:.0f}，处于强势区间")
            elif value >= 30:
                signal = "中性"
            else:
                signal = "超卖"
                highlights.append(f"RSI={value:.0f}，超卖反弹机会")
        elif factor_code == "macd":
            display_value = f"{value:.3f}"
            if value > 0:
                signal = "多头"
                highlights.append("MACD金叉，多头信号")
            else:
                signal = "空头"
        elif factor_code == "volatility_20d":
            display_value = f"{value*100:.1f}%"
            if value > 0.03:
                signal = "高波动"
                risks.append(f"波动率{value*100:.1f}%，风险较高")
            else:
                signal = "低波动"
        else:
            display_value = f"{value:.4f}" if isinstance(value, float) else str(value)
            signal = "正常"
        
        factors_detail.append({
            "name": factor_name,
            "code": factor_code,
            "value": display_value,
            "signal": signal,
            "weight": f"{weight*100:.0f}%",
            "direction": "做多" if direction == "long" else "做空"
        })
    
    # 生成综合摘要
    rank = buy_decision.get("rank", 0)
    score = buy_decision.get("score", 0)
    
    if rank <= 3:
        rank_desc = f"排名第{rank}（TOP3）"
    elif rank <= 10:
        rank_desc = f"排名第{rank}（前10）"
    else:
        rank_desc = f"排名第{rank}"
    
    # 构建摘要
    summary_parts = [rank_desc]
    if highlights:
        summary_parts.append(highlights[0])
    
    result["summary"] = "，".join(summary_parts)
    result["factors"] = factors_detail
    result["highlights"] = highlights[:3]  # 最多3条亮点
    result["risks"] = risks[:2]  # 最多2条风险
    result["score"] = round(score, 2)
    result["rank"] = rank
    
    return result


# 添加请求日志中间件
@daily_observer_bp.before_request
def log_request():
    logger.info(f"🌐 [{request.method}] {request.path} - before_request")
    if request.path.endswith('complete-data'):
        logger.warning(f"⚠️ complete-data请求被before_request捕获！")


# =============================================================================
# 配置选项
# =============================================================================

@daily_observer_bp.route("/scoring-engines", methods=["GET"])
def get_scoring_engines():
    """获取可用的执行引擎列表"""
    try:
        engines = list_engines()
        return success(data=engines)
    except Exception as e:
        logger.error(f"获取执行引擎列表失败: {e}")
        return error(message=f"获取失败: {str(e)}")


# =============================================================================
# 策略管理
# =============================================================================

@daily_observer_bp.route("/strategies", methods=["GET"])
@token_required
def list_strategies():
    """获取观测策略列表（租户隔离）"""
    try:
        # 🆕 从Token中获取租户ID（必需）
        tenant_id = get_current_tenant_id()

        # 查询策略（强制按租户隔离）
        strategies = DailyObserverStrategy.query.filter_by(
            status="active",
            tenant_id=tenant_id
        ).all()
        return success(data={
            "items": [s.to_dict() for s in strategies],
            "total": len(strategies)
        })
    except Exception as e:
        logger.error(f"获取策略列表失败: {e}")
        return error(message=f"获取失败: {str(e)}")


@daily_observer_bp.route("/strategies/all", methods=["GET"])
@token_required
def list_all_strategies():
    """获取所有观测策略列表（包括已停用，租户隔离）"""
    try:
        # 🆕 从Token中获取租户ID
        tenant_id = get_current_tenant_id()
        
        strategies = DailyObserverStrategy.query.filter_by(
            tenant_id=tenant_id
        ).order_by(
            DailyObserverStrategy.created_at.desc()
        ).all()
        return success(data={
            "items": [s.to_dict() for s in strategies],
            "total": len(strategies)
        })
    except Exception as e:
        logger.error(f"获取策略列表失败: {e}")
        return error(message=f"获取失败: {str(e)}")


@daily_observer_bp.route("/strategies", methods=["POST"])
@token_required
@check_subscription
@check_feature_limit('observer')
def create_strategy():
    """创建观测策略"""
    try:
        # 🆕 从Token中获取租户ID
        tenant_id = get_current_tenant_id()
        
        data = request.get_json()

        # 参数校验
        if not data.get("name"):
            return error(message="策略名称不能为空")

        if not data.get("factor_combo_id"):
            return error(message="必须选择因子组合")

        # 创建策略
        strategy = DailyObserverStrategy(
            tenant_id=tenant_id,  # 🆕 绑定租户ID
            name=data["name"],
            description=data.get("description", ""),
            factor_combo_id=data["factor_combo_id"],
            scoring_engine_id=data.get("scoring_engine_id", "simple_conservative"),
            start_date=data.get("start_date", "20250901"),
            stock_pool=json.dumps(data.get("stock_pool", [])),
            top_n=data.get("top_n", 15),
            max_positions=data.get("max_positions", 7),
            take_profit_ratio=data.get("take_profit_ratio", 0.15),
            stop_loss_ratio=data.get("stop_loss_ratio", -0.08),
            sell_rank_out=data.get("sell_rank_out", 50),
            signal_confirm_days=data.get("signal_confirm_days", 1),
            blacklist_cooldown=data.get("blacklist_cooldown", 30),
            rank_drop_threshold=data.get("rank_drop_threshold", 15),
            status="active"
        )

        db.session.add(strategy)
        db.session.commit()

        return success(data=strategy.to_dict(), message="策略创建成功")
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建策略失败: {e}")
        return error(message=f"创建失败: {str(e)}")


@daily_observer_bp.route("/strategies/<int:strategy_id>", methods=["GET"])
@token_required
def get_strategy(strategy_id: int):
    """获取策略详情（租户隔离）"""
    try:
        # 🆕 从Token中获取租户ID
        tenant_id = get_current_tenant_id()
        
        strategy = DailyObserverStrategy.query.filter_by(
            id=strategy_id,
            tenant_id=tenant_id
        ).first()
        if not strategy:
            return error(message="策略不存在或无权访问", code=404)

        return success(data=strategy.to_dict())
    except Exception as e:
        logger.error(f"获取策略详情失败: {e}")
        return error(message=f"获取失败: {str(e)}")


@daily_observer_bp.route("/strategies/<int:strategy_id>", methods=["PUT"])
@token_required
def update_strategy(strategy_id: int):
    """更新策略（租户隔离）"""
    try:
        # 🆕 验证策略所有权
        tenant_id = get_current_tenant_id()
        strategy = _verify_strategy_ownership(strategy_id, tenant_id)
        if not strategy:
            return error(message="策略不存在或无权访问", code=404)

        data = request.get_json()

        # 更新字段
        if "name" in data:
            strategy.name = data["name"]
        if "description" in data:
            strategy.description = data["description"]
        if "stock_pool" in data:
            strategy.stock_pool = json.dumps(data["stock_pool"])
        if "top_n" in data:
            strategy.top_n = data["top_n"]
        if "max_positions" in data:
            strategy.max_positions = data["max_positions"]
        if "take_profit_ratio" in data:
            strategy.take_profit_ratio = data["take_profit_ratio"]
        if "stop_loss_ratio" in data:
            strategy.stop_loss_ratio = data["stop_loss_ratio"]
        if "status" in data:
            strategy.status = data["status"]

        strategy.updated_at = datetime.utcnow()
        db.session.commit()

        return success(data=strategy.to_dict(), message="更新成功")
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新策略失败: {e}")
        return error(message=f"更新失败: {str(e)}")


@daily_observer_bp.route("/strategies/<int:strategy_id>", methods=["DELETE"])
@token_required
def delete_strategy(strategy_id: int):
    """删除策略（软删除，租户隔离）"""
    try:
        # 🆕 验证策略所有权
        tenant_id = get_current_tenant_id()
        strategy = _verify_strategy_ownership(strategy_id, tenant_id)
        if not strategy:
            return error(message="策略不存在或无权访问", code=404)

        # 软删除：设置为inactive
        strategy.status = "inactive"
        db.session.commit()

        return success(message="删除成功")
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除策略失败: {e}")
        return error(message=f"删除失败: {str(e)}")


# =============================================================================
# 观测记录
# =============================================================================

@daily_observer_bp.route("/strategies/<int:strategy_id>/records", methods=["GET"])
@token_required
def get_strategy_records(strategy_id: int):
    """获取策略的观测记录（租户隔离）"""
    try:
        # 🆕 验证策略属于当前租户
        tenant_id = get_current_tenant_id()
        strategy = DailyObserverStrategy.query.filter_by(
            id=strategy_id,
            tenant_id=tenant_id
        ).first()
        if not strategy:
            return error(message="策略不存在或无权访问", code=404)
        
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 30, type=int)
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        query = DailyObserverRecord.query.filter_by(strategy_id=strategy_id)

        if start_date:
            query = query.filter(DailyObserverRecord.date >= start_date)
        if end_date:
            query = query.filter(DailyObserverRecord.date <= end_date)

        pagination = query.order_by(
            DailyObserverRecord.date.desc()
        ).paginate(page=page, per_page=page_size, error_out=False)

        return success(data={
            "items": [r.to_dict() for r in pagination.items],
            "total": pagination.total,
            "page": page,
            "page_size": page_size,
            "pages": pagination.pages
        })
    except Exception as e:
        logger.error(f"获取观测记录失败: {e}")
        return error(message=f"获取失败: {str(e)}")


@daily_observer_bp.route("/strategies/<int:strategy_id>/latest", methods=["GET"])
@token_required
def get_latest_record(strategy_id: int):
    """获取最新一条观测记录（租户隔离）"""
    try:
        # 🆕 验证策略所有权
        tenant_id = get_current_tenant_id()
        strategy = _verify_strategy_ownership(strategy_id, tenant_id)
        if not strategy:
            return error(message="策略不存在或无权访问", code=404)
        
        record = DailyObserverRecord.query.filter_by(
            strategy_id=strategy_id
        ).order_by(DailyObserverRecord.date.desc()).first()

        if not record:
            return success(data=None, message="暂无观测数据")

        return success(data=record.to_dict())
    except Exception as e:
        logger.error(f"获取最新记录失败: {e}")
        return error(message=f"获取失败: {str(e)}")


# =============================================================================
# 交易记录
# =============================================================================

@daily_observer_bp.route("/strategies/<int:strategy_id>/trades", methods=["GET"])
@token_required
def get_strategy_trades(strategy_id: int):
    """获取策略的交易记录（租户隔离）"""
    try:
        # 🆕 验证策略所有权
        tenant_id = get_current_tenant_id()
        strategy = _verify_strategy_ownership(strategy_id, tenant_id)
        if not strategy:
            return error(message="策略不存在或无权访问", code=404)
        
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 50, type=int)
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        direction = request.args.get("direction")
        ts_code = request.args.get("ts_code")

        query = DailyObserverTrade.query.filter_by(strategy_id=strategy_id)

        if start_date:
            query = query.filter(DailyObserverTrade.date >= start_date)
        if end_date:
            query = query.filter(DailyObserverTrade.date <= end_date)
        if direction:
            query = query.filter(DailyObserverTrade.direction == direction)
        if ts_code:
            query = query.filter(DailyObserverTrade.ts_code == ts_code)

        pagination = query.order_by(
            DailyObserverTrade.date.desc(),
            DailyObserverTrade.created_at.desc()
        ).paginate(page=page, per_page=page_size, error_out=False)

        # 获取所有涉及股票的名称
        ts_codes = list(set([t.ts_code for t in pagination.items]))
        stocks = Stock.query.filter(Stock.ts_code.in_(ts_codes)).all()
        stock_names = {s.ts_code: s.name for s in stocks}

        # 添加股票名称到交易记录
        items = []
        for t in pagination.items:
            trade_dict = t.to_dict()
            trade_dict["stock_name"] = stock_names.get(t.ts_code, t.ts_code)
            items.append(trade_dict)

        return success(data={
            "items": items,
            "total": pagination.total,
            "page": page,
            "page_size": page_size,
            "pages": pagination.pages
        })
    except Exception as e:
        logger.error(f"获取交易记录失败: {e}")
        return error(message=f"获取失败: {str(e)}")


@daily_observer_bp.route("/stock-kline/<ts_code>", methods=["GET"])
def get_stock_kline(ts_code: str):
    """获取股票K线数据"""
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        limit = request.args.get("limit", 300, type=int)

        query = BarData.query.filter_by(ts_code=ts_code, freq="D")

        if start_date:
            query = query.filter(BarData.trade_date >= start_date)
        if end_date:
            query = query.filter(BarData.trade_date <= end_date)

        klines = query.order_by(BarData.trade_date.desc()).limit(limit).all()
        klines.reverse()  # 按时间正序

        return success(data=[k.to_dict() for k in klines])
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        return error(message=f"获取失败: {str(e)}")


# =============================================================================
# 统计汇总
# =============================================================================

@daily_observer_bp.route("/strategies/<int:strategy_id>/summary", methods=["GET"])
@token_required
def get_strategy_summary(strategy_id: int):
    """获取策略统计汇总（租户隔离）"""
    try:
        # 🆕 验证策略所有权
        tenant_id = get_current_tenant_id()
        strategy = _verify_strategy_ownership(strategy_id, tenant_id)
        if not strategy:
            return error(message="策略不存在或无权访问", code=404)
        
        initial_capital = float(strategy.initial_capital) if strategy.initial_capital else 1000000.0
        
        # 获取所有记录
        records = DailyObserverRecord.query.filter_by(
            strategy_id=strategy_id
        ).order_by(DailyObserverRecord.date.asc()).all()

        if not records:
            return success(data={
                "total_days": 0,
                "total_trades": 0,
                "win_rate": 0,
                "total_return": 0,
                "max_drawdown": 0,
                "avg_daily_return": 0,
                "initial_capital": initial_capital,
                "final_value": initial_capital,
                "total_commission": 0
            })

        # 统计
        total_days = len(records)
        total_value = [float(r.total_value) for r in records if r.total_value]

        # 总收益率（使用策略配置的初始资金）
        if total_value:
            final_value = total_value[-1]
            total_return = (final_value - initial_capital) / initial_capital * 100
        else:
            final_value = initial_capital
            total_return = 0

        # 最大回撤
        max_value = 0
        max_drawdown = 0
        for v in total_value:
            if v > max_value:
                max_value = v
            drawdown = (max_value - v) / max_value * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 交易统计 - 配对买卖计算真实盈亏
        all_trades = DailyObserverTrade.query.filter_by(
            strategy_id=strategy_id
        ).order_by(DailyObserverTrade.date.asc(), DailyObserverTrade.created_at.asc()).all()

        # 按股票分组配对买卖
        buy_trades = 0
        sell_trades = 0
        completed_trades = 0
        profitable_trades = 0
        total_commission = 0.0  # 总手续费

        position_map = {}  # {ts_code: {buy_price, volume, buy_trade_id}}

        for trade in all_trades:
            if trade.direction == "buy":
                position_map[trade.ts_code] = {
                    "buy_price": float(trade.price),
                    "volume": int(trade.volume),
                    "buy_trade_id": trade.id
                }
                buy_trades += 1
                # 累加买入手续费
                buy_commission = float(trade.commission) if trade.commission else (float(trade.amount) * 0.0003 if trade.amount else 0)
                total_commission += buy_commission
                
            elif trade.direction == "sell":
                sell_trades += 1
                # 累加卖出手续费
                sell_commission = float(trade.commission) if trade.commission else (float(trade.amount) * 0.0003 if trade.amount else 0)
                total_commission += sell_commission
                
                if trade.ts_code in position_map:
                    # 计算这笔交易的盈亏
                    buy_info = position_map[trade.ts_code]
                    buy_amount = buy_info["buy_price"] * buy_info["volume"]
                    sell_amount = float(trade.price) * int(trade.volume)
                    buy_fee = buy_amount * 0.0003  # 买入手续费
                    sell_fee = float(trade.amount) * 0.0003 if trade.amount else float(trade.commission or 0)  # 卖出手续费

                    profit = sell_amount - buy_amount - buy_fee - sell_fee
                    completed_trades += 1
                    if profit > 0:
                        profitable_trades += 1

                    del position_map[trade.ts_code]

        win_rate = (profitable_trades / completed_trades * 100) if completed_trades > 0 else 0

        # 日均收益
        daily_returns = [float(r.day_return) for r in records if r.day_return is not None]
        avg_daily_return = sum(daily_returns) / len(daily_returns) if daily_returns else 0.0

        return success(data={
            "total_days": total_days,
            "total_trades": buy_trades,
            "win_rate": round(win_rate, 2),
            "total_return": round(total_return, 2),
            "max_drawdown": round(max_drawdown, 2),
            "avg_daily_return": round(avg_daily_return, 4),
            "initial_capital": initial_capital,
            "final_value": float(final_value),
            "total_commission": round(total_commission, 2),
            "commission_ratio": round(total_commission / initial_capital * 100, 3) if initial_capital > 0 else 0
        })
    except Exception as e:
        logger.error(f"获取统计汇总失败: {e}")
        return error(message=f"获取失败: {str(e)}")


@daily_observer_bp.route("/strategies/<int:strategy_id>/holdings", methods=["GET"])
@token_required
def get_strategy_holdings(strategy_id: int):
    """获取策略的最新持仓（租户隔离）"""
    try:
        # 🆕 验证策略所有权
        tenant_id = get_current_tenant_id()
        strategy = _verify_strategy_ownership(strategy_id, tenant_id)
        if not strategy:
            return error(message="策略不存在或无权访问", code=404)
        
        # 获取最新记录
        latest_record = DailyObserverRecord.query.filter_by(
            strategy_id=strategy_id
        ).order_by(DailyObserverRecord.date.desc()).first()

        if not latest_record or not latest_record.holdings:
            return success(data=[])

        holdings_dict = json.loads(latest_record.holdings) if latest_record.holdings else {}

        if not holdings_dict:
            return success(data=[])

        # 获取股票名称
        ts_codes = list(holdings_dict.keys())
        stocks = Stock.query.filter(Stock.ts_code.in_(ts_codes)).all()
        stock_names = {s.ts_code: s.name for s in stocks}

        # 构建返回数据
        holdings = []
        for ts_code, holding in holdings_dict.items():
            holdings.append({
                "ts_code": ts_code,
                "stock_name": stock_names.get(ts_code, ts_code),
                "buy_price": float(holding.get("buy_price", 0)),
                "buy_date": holding.get("buy_date"),
                "volume": holding.get("volume", 0),
                "score": float(holding.get("score", 0)),
                "rank": holding.get("rank", 0)
            })

        return success(data=holdings)
    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        return error(message=f"获取失败: {str(e)}")


# =============================================================================
# 数据同步
# =============================================================================

@daily_observer_bp.route("/sync/all", methods=["POST"])
def sync_all():
    """同步所有策略数据"""
    try:
        from services.daily_observer_service import daily_observer_service

        # 触发同步
        result = daily_observer_service.sync_all_strategies()

        return success(data=result, message="同步任务已启动")
    except Exception as e:
        logger.error(f"同步失败: {e}")
        return error(message=f"同步失败: {str(e)}")


@daily_observer_bp.route("/strategies/<int:strategy_id>/sync", methods=["POST"])
@token_required
def sync_single_strategy(strategy_id: int):
    """同步单个策略数据（租户隔离）"""
    try:
        from services.daily_observer_service import daily_observer_service
        
        # 🆕 验证策略所有权
        tenant_id = get_current_tenant_id()
        strategy = _verify_strategy_ownership(strategy_id, tenant_id)
        if not strategy:
            return error(message="策略不存在或无权访问", code=404)

        # 🔴 从请求体中读取参数
        data = request.get_json() or {}
        auto_complete_data = data.get("auto_complete_data", True)
        
        logger.info(f"开始同步策略{strategy_id}，auto_complete_data={auto_complete_data}")
        
        # 触发同步
        result = daily_observer_service.sync_strategy(strategy_id, auto_complete_data=auto_complete_data)
        logger.info(f"策略{strategy_id}同步完成: 已同步{result.get('synced', 0)}天")

        return success(data=result, message="同步任务已启动")
    except Exception as e:
        logger.error(f"同步策略{strategy_id}失败: {e}")
        return error(message=f"同步失败: {str(e)}")


@daily_observer_bp.route("/data-range", methods=["GET"])
def get_data_range():
    """获取观测数据的时间范围"""
    try:
        from utils.database import db
        from models.daily_observer import DailyObserverRecord
        from sqlalchemy import func

        # 查询因子数据最早日期
        from models.factor_data import FactorData
        earliest_factor = db.session.query(func.min(FactorData.trade_date)).filter(
            FactorData.trade_date != None,
            FactorData.trade_date != ''
        ).scalar()

        # 查询观测记录最早日期
        earliest_observer = db.session.query(func.min(DailyObserverRecord.date)).filter(
            DailyObserverRecord.date != None
        ).scalar()

        return success(data={
            "earliest_factor_date": earliest_factor,
            "earliest_observer_date": earliest_observer
        })
    except Exception as e:
        logger.error(f"查询失败: {e}")
        return error(message=f"查询失败: {str(e)}")


@daily_observer_bp.route("/clear-all", methods=["POST"])
def clear_all_data():
    """清空所有观测数据（危险操作）"""
    try:
        from utils.database import db
        from models.daily_observer import DailyObserverRecord, DailyObserverTrade, DailyObserverStrategy

        # 删除所有观测相关数据
        DailyObserverTrade.query.delete()
        DailyObserverRecord.query.delete()
        DailyObserverStrategy.query.delete()
        db.session.commit()

        logger.info("已清空所有观测数据")
        return success(message="已清空所有观测数据")
    except Exception as e:
        db.session.rollback()
        logger.error(f"清空失败: {e}")
        return error(message=f"清空失败: {str(e)}")


@daily_observer_bp.route("/fill-gap", methods=["POST"])
def fill_gap():
    """补齐缺失数据（旧版）"""
    try:
        from services.daily_observer_service import daily_observer_service

        result = daily_observer_service.fill_missing_data()

        return success(data=result, message=f"补齐完成，共补齐 {result.get('filled', 0)} 条记录")
    except Exception as e:
        logger.error(f"补齐失败: {e}")
        return error(message=f"补齐失败: {str(e)}")


@daily_observer_bp.route("/strategies/<int:strategy_id>/complete-data", methods=["POST"])
def complete_strategy_data(strategy_id: int):
    """
    为策略补全数据（K线 + 因子）
    使用TuShare下载数据（Baostock服务当前不稳定）
    """
    try:
        from models.daily_observer import DailyObserverStrategy
        from services.data_completion_service import data_completion_service
        
        strategy = DailyObserverStrategy.query.get(strategy_id)
        if not strategy:
            return error(message="策略不存在", code=404)
        
        data = request.get_json() or {}
        start_date = data.get("start_date") or strategy.start_date or "20250901"
        end_date = data.get("end_date") or datetime.now().strftime("%Y%m%d")
        logger.info(f"📅 日期范围: {start_date} - {end_date}")
        
        # 获取股票池
        stock_pool = json.loads(strategy.stock_pool) if strategy.stock_pool else []
        if not stock_pool:
            return error(message="股票池为空")
        
        logger.info(f"开始为策略{strategy_id}补全数据: {start_date} 至 {end_date}, 股票池{len(stock_pool)}只")
        
        result = data_completion_service.ensure_data_ready(
            stock_pool=stock_pool,
            start_date=start_date,
            end_date=end_date,
            skip_weekends=True
        )
        
        if result.get("success"):
            message = f"数据补全完成！处理了{len(result.get('dates_processed', []))}个交易日"
            
            # 自动同步策略（sync_strategy 内部会自动记录推荐）
            from services.daily_observer_service import daily_observer_service
            sync_result = daily_observer_service.sync_strategy(strategy_id)
            if sync_result.get("synced", 0) > 0:
                result["sync_result"] = sync_result
                message += f"，同步了{sync_result.get('synced', 0)}天"
                
                # 推荐记录状态（由 sync_strategy 自动完成）
                if sync_result.get("recommendation_saved"):
                    result["recommendation_saved"] = True
                    result["recommendation_data"] = sync_result.get("recommendation_data")
                    message += "，推荐已记录"
            if sync_result.get("errors"):
                result["sync_errors"] = sync_result.get("errors")
        else:
            message = f"数据补全完成，但有{len(result.get('errors', []))}个错误"
        
        return success(data=result, message=message)
        
    except Exception as e:
        logger.error(f"数据补全失败: {e}")
        import traceback
        traceback.print_exc()
        return error(message=f"数据补全失败: {str(e)}")


@daily_observer_bp.route("/strategies/<int:strategy_id>/data-health", methods=["GET"])
def check_data_health(strategy_id: int):
    """
    检查策略的数据健康状况
    
    返回哪些股票、哪天的数据有问题
    """
    try:
        from models.daily_observer import DailyObserverStrategy
        from models.bar_data import BarData
        from models.factor_data import FactorData
        from sqlalchemy import func
        
        strategy = DailyObserverStrategy.query.get(strategy_id)
        if not strategy:
            return error(message="策略不存在", code=404)
        
        # 获取股票池和日期范围
        stock_pool = json.loads(strategy.stock_pool) if strategy.stock_pool else []
        start_date = request.args.get("start_date") or strategy.start_date or "20250901"
        end_date = request.args.get("end_date") or datetime.now().strftime("%Y%m%d")
        
        # 生成交易日列表（简单过滤周末）
        from datetime import datetime as dt, timedelta
        start = dt.strptime(start_date, "%Y%m%d")
        end = dt.strptime(end_date, "%Y%m%d")
        trade_dates = []
        current = start
        while current <= end:
            if current.weekday() < 5:  # 周一到周五
                trade_dates.append(current.strftime("%Y%m%d"))
            current += timedelta(days=1)
        
        issues = []
        
        # 检查每一天的数据
        for date in trade_dates[-10:]:  # 只检查最近10天
            # 检查K线数据
            kline_count = BarData.query.filter(
                BarData.ts_code.in_(stock_pool),
                BarData.trade_date == date
            ).count()
            
            kline_coverage = kline_count / len(stock_pool) if stock_pool else 0
            
            # 检查因子数据
            factor_count = FactorData.query.filter(
                FactorData.ts_code.in_(stock_pool),
                FactorData.trade_date == date
            ).count()
            
            factor_coverage = factor_count / len(stock_pool) if stock_pool else 0
            
            # 记录问题
            if kline_coverage < 0.8:
                issues.append({
                    "date": date,
                    "type": "K线数据",
                    "coverage": f"{kline_coverage*100:.1f}%",
                    "count": f"{kline_count}/{len(stock_pool)}",
                    "severity": "high" if kline_coverage < 0.5 else "medium"
                })
            
            if factor_coverage < 0.8:
                issues.append({
                    "date": date,
                    "type": "因子数据",
                    "coverage": f"{factor_coverage*100:.1f}%",
                    "count": f"{factor_count}/{len(stock_pool)}",
                    "severity": "high" if factor_coverage < 0.5 else "medium"
                })
        
        # 找出一直缺失数据的股票
        problem_stocks = []
        for ts_code in stock_pool[:20]:  # 检查前20只
            recent_kline = BarData.query.filter(
                BarData.ts_code == ts_code,
                BarData.trade_date >= trade_dates[-5] if len(trade_dates) >= 5 else trade_dates[0]
            ).count()
            
            recent_factor = FactorData.query.filter(
                FactorData.ts_code == ts_code,
                FactorData.trade_date >= trade_dates[-5] if len(trade_dates) >= 5 else trade_dates[0]
            ).count()
            
            if recent_kline == 0 or recent_factor == 0:
                problem_stocks.append({
                    "ts_code": ts_code,
                    "kline_days": recent_kline,
                    "factor_days": recent_factor,
                    "status": "严重" if (recent_kline == 0 and recent_factor == 0) else "警告"
                })
        
        return success(data={
            "issues": issues,
            "problem_stocks": problem_stocks,
            "health_score": 100 - len(issues) * 5,  # 简单评分
            "checked_dates": len(trade_dates[-10:]),
            "checked_stocks": min(20, len(stock_pool))
        })
        
    except Exception as e:
        logger.error(f"数据健康检查失败: {e}")
        import traceback
        traceback.print_exc()
        return error(message=f"检查失败: {str(e)}")


# =============================================================================
# 预置策略
# =============================================================================

@daily_observer_bp.route("/preset/震荡组合", methods=["POST"])
def create_oscillation_preset():
    """创建震荡组合预置策略"""
    try:
        data = request.get_json() or {}

        # 震荡组合因子配置
        # reversal_5d, rsi_14, return_5d, macd
        # 使用因子组合ID=20

        strategy = DailyObserverStrategy(
            name=data.get("name", "震荡组合 v2"),
            description="基于反转、RSI、收益和MACD因子的震荡市策略",
            factor_combo_id=20,
            scoring_engine_id="simple_conservative",
            stock_pool=json.dumps(data.get("stock_pool", [])),
            top_n=data.get("top_n", 15),
            max_positions=data.get("max_positions", 7),
            take_profit_ratio=0.15,
            stop_loss_ratio=-0.08,
            sell_rank_out=50,
            signal_confirm_days=2,
            blacklist_cooldown=30,
            status="active"
        )

        db.session.add(strategy)
        db.session.commit()

        return success(data=strategy.to_dict(), message="震荡组合策略创建成功")
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建预置策略失败: {e}")
        return error(message=f"创建失败: {str(e)}")


@daily_observer_bp.route("/preset/动量组合", methods=["POST"])
def create_momentum_preset():
    """创建动量组合预置策略"""
    try:
        data = request.get_json() or {}

        strategy = DailyObserverStrategy(
            name=data.get("name", "动量组合 v1"),
            description="基于动量因子的趋势跟踪策略",
            factor_combo_id=5,  # 强势动量精选
            scoring_engine_id="simple_conservative",
            stock_pool=json.dumps(data.get("stock_pool", [])),
            top_n=data.get("top_n", 10),
            max_positions=data.get("max_positions", 5),
            take_profit_ratio=0.20,
            stop_loss_ratio=-0.10,
            sell_rank_out=30,
            signal_confirm_days=2,
            blacklist_cooldown=30,
            status="active"
        )

        db.session.add(strategy)
        db.session.commit()

        return success(data=strategy.to_dict(), message="动量组合策略创建成功")
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建预置策略失败: {e}")
        return error(message=f"创建失败: {str(e)}")


@daily_observer_bp.route("/preset/反转组合", methods=["POST"])
def create_reversal_preset():
    """创建反转组合预置策略"""
    try:
        data = request.get_json() or {}

        strategy = DailyObserverStrategy(
            name=data.get("name", "反转组合 v1"),
            description="基于反转因子的低买高卖策略",
            factor_combo_id=15,  # F3: 极简三因子
            scoring_engine_id="simple_conservative",
            stock_pool=json.dumps(data.get("stock_pool", [])),
            top_n=data.get("top_n", 12),
            max_positions=data.get("max_positions", 6),
            take_profit_ratio=0.12,
            stop_loss_ratio=-0.08,
            sell_rank_out=40,
            signal_confirm_days=1,
            blacklist_cooldown=30,
            status="active"
        )

        db.session.add(strategy)
        db.session.commit()

        return success(data=strategy.to_dict(), message="反转组合策略创建成功")
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建预置策略失败: {e}")
        return error(message=f"创建失败: {str(e)}")


# =============================================================================
# 操作计划
# =============================================================================

@daily_observer_bp.route("/strategies/<int:strategy_id>/action-plan", methods=["GET"])
def get_action_plan(strategy_id: int):
    """获取策略的操作计划（今日操作/明日操作）"""
    try:
        from datetime import datetime, timedelta

        strategy = DailyObserverStrategy.query.get(strategy_id)
        if not strategy:
            return error(message="策略不存在", code=404)

        # 🔴 T+1 智能判断：根据当前时间决定显示哪天的操作建议
        now = datetime.now()
        today = now.strftime("%Y%m%d")
        current_hour = now.hour
        is_after_market_close = current_hour >= 15
        
        # 计算下一个交易日
        next_day = now + timedelta(days=1)
        while next_day.weekday() >= 5:  # 跳过周末
            next_day += timedelta(days=1)
        next_trade_date = next_day.strftime("%Y%m%d")

        # 获取最新观测记录
        latest_record = DailyObserverRecord.query.filter_by(
            strategy_id=strategy_id
        ).order_by(DailyObserverRecord.date.desc()).first()

        if not latest_record:
            return success(data={
                "date": None,
                "has_data": False,
                "buy_signals": [],
                "sell_signals": [],
                "holdings": [],
                "message": "暂无观测数据，请先同步策略"
            })

        # 🔴 智能选择数据日期：如果最新记录是今天且没有K线数据，使用昨天的记录
        today = datetime.now().strftime("%Y%m%d")
        use_record = latest_record
        
        if latest_record.date == today:
            # 检查今天是否有K线数据
            holdings_dict = json.loads(latest_record.holdings) if latest_record.holdings else {}
            if holdings_dict:
                sample_code = list(holdings_dict.keys())[0]
                from models.bar_data import BarData
                has_today_data = BarData.query.filter_by(
                    ts_code=sample_code,
                    trade_date=today
                ).first() is not None
                
                if not has_today_data:
                    # 今天没有K线数据，使用昨天的记录
                    logger.warning(f"⚠️ 今天({today})无K线数据，使用昨天的记录生成操作建议")
                    yesterday_record = DailyObserverRecord.query.filter(
                        DailyObserverRecord.strategy_id == strategy_id,
                        DailyObserverRecord.date < today
                    ).order_by(DailyObserverRecord.date.desc()).first()
                    
                    if yesterday_record:
                        use_record = yesterday_record
                        logger.info(f"✅ 使用{yesterday_record.date}的数据")
        
        latest_record = use_record  # 使用选定的记录

        # 解析最新记录数据
        selected_stocks = json.loads(latest_record.selected_stocks) if latest_record.selected_stocks else []
        holdings_dict = json.loads(latest_record.holdings) if latest_record.holdings else {}
        scores_dict = json.loads(latest_record.scores) if latest_record.scores else {}

        # 获取股票名称
        all_ts_codes = list(set(selected_stocks + list(holdings_dict.keys())))
        stocks = Stock.query.filter(Stock.ts_code.in_(all_ts_codes)).all()
        stock_names = {s.ts_code: s.name for s in stocks}

        # 根据得分计算排名
        scored_stocks = [
            (ts_code, scores_dict.get(ts_code, 0))
            for ts_code in all_ts_codes
            if ts_code in scores_dict
        ]
        scored_stocks.sort(key=lambda x: x[1], reverse=True)
        stock_ranks = {ts_code: i+1 for i, (ts_code, _) in enumerate(scored_stocks)}

        # 获取当前持仓列表
        current_holdings = []
        for ts_code, holding_info in holdings_dict.items():
            current_holdings.append({
                "ts_code": ts_code,
                "name": stock_names.get(ts_code, ts_code),
                "buy_price": float(holding_info.get("buy_price", 0)),
                "volume": holding_info.get("volume", 0),
                "buy_date": holding_info.get("buy_date"),
                "score": holding_info.get("score", 0),
                "rank": holding_info.get("rank", 0)
            })

        # 计算买入信号（新选中但未持仓的股票）
        holding_codes = set(holdings_dict.keys())
        buy_signals = []
        for ts_code in selected_stocks[:strategy.top_n]:
            if ts_code not in holding_codes:
                score = scores_dict.get(ts_code, 0)
                rank = stock_ranks.get(ts_code, 999)
                buy_signals.append({
                    "ts_code": ts_code,
                    "name": stock_names.get(ts_code, ts_code),
                    "score": score,
                    "rank": rank
                })

        # 计算卖出信号（使用与回测一致的执行引擎逻辑）
        # 🔴 根据策略的 scoring_engine_id 创建对应的引擎实例
        engine_id = strategy.scoring_engine_id or "daily_observer"
        logger.info(f"📊 策略 {strategy_id} 使用引擎: {engine_id}")
        
        # 使用统一的引擎获取方法
        from services.scoring_engines.registry import get_engine
        engine = get_engine(engine_id)
        
        # 🔴 对于 simple_conservative 引擎,需要设置因子组合ID并加载配置
        if engine_id == "simple_conservative":
            engine.factor_combo_id = strategy.factor_combo_id
            engine._load_factor_config()

        # 准备引擎参数（根据引擎类型使用不同默认值）
        if engine_id == "simple_conservative":
            # simple_conservative 引擎使用更保守的参数
            strategy_params = {
                "min_score": 0.7,  # 得分阈值
                "max_positions": strategy.max_positions,
                "take_profit_ratio": 0.20,  # 20%止盈（与回测一致）
                "stop_loss_ratio": -0.05,   # 5%止损（与回测一致）
                "hold_min_days": 5,          # 最少持有5天
                "blacklist_cooldown": strategy.blacklist_cooldown
            }
        else:
            # 其他引擎使用策略配置的参数
            strategy_params = {
                "top_n": strategy.top_n,
                "max_positions": strategy.max_positions,
                "take_profit_ratio": strategy.take_profit_ratio,
                "stop_loss_ratio": strategy.stop_loss_ratio,
                "sell_rank_out": strategy.sell_rank_out,
                "signal_confirm_days": strategy.signal_confirm_days,
                "blacklist_cooldown": strategy.blacklist_cooldown
            }

        # 准备持仓数据格式 {ts_code: {buy_price, buy_date, volume, score, rank}}
        holdings_for_engine = {}
        for h in current_holdings:
            holdings_for_engine[h["ts_code"]] = {
                "buy_price": h["buy_price"],
                "buy_date": h["buy_date"],
                "volume": h["volume"],
                "score": h["score"],
                "rank": h["rank"]
            }

        # 获取交易日期
        trade_date = latest_record.date
        
        # 准备得分数据格式 {ts_code: {score, price, rank}}
        # 批量获取所有相关股票的最新价格
        stock_scores_for_engine = {}
        if all_ts_codes:
            from models.bar_data import BarData
            bars = BarData.query.filter(
                BarData.ts_code.in_(all_ts_codes),
                BarData.trade_date == trade_date
            ).all()
            price_dict = {bar.ts_code: float(bar.close) for bar in bars}
            
            for ts_code in all_ts_codes:
                stock_scores_for_engine[ts_code] = {
                    "score": scores_dict.get(ts_code, 0),
                    "price": price_dict.get(ts_code, 0),  # 使用实际收盘价
                    "rank": stock_ranks.get(ts_code, 999)
                }

        # 获取资金信息
        total_value = float(latest_record.total_value)
        cash = float(latest_record.cash) if latest_record.cash else 0

        # 批量获取持仓股票的最新价格
        holding_codes = list(holdings_dict.keys())
        latest_prices = {}
        if holding_codes:
            from models.bar_data import BarData
            bars = BarData.query.filter(
                BarData.ts_code.in_(holding_codes),
                BarData.trade_date == trade_date
            ).all()
            latest_prices = {bar.ts_code: float(bar.close) for bar in bars}

        current_holdings_list = []
        for ts_code, holding_info in holdings_dict.items():
            buy_price = float(holding_info.get("buy_price", 0))
            volume = holding_info.get("volume", 0)
            
            # 使用最新价格计算市值，如果没有则用买入价
            current_price = latest_prices.get(ts_code, buy_price)
            market_value = current_price * volume
            ratio = (market_value / total_value * 100) if total_value > 0 else 0

            current_holdings_list.append({
                "ts_code": ts_code,
                "name": stock_names.get(ts_code, ts_code),
                "quantity": volume,
                "buy_price": buy_price,
                "current_price": current_price,  # 添加当前价格
                "market_value": market_value,
                "ratio": round(ratio, 2)
            })

        # 🔴 加载卖出历史（冷却期检查）
        # 从数据库获取最近N天内卖出的股票
        cooldown_days = strategy.blacklist_cooldown
        cooldown_start_date = (datetime.strptime(trade_date, "%Y%m%d") - timedelta(days=cooldown_days)).strftime("%Y%m%d")
        
        recent_sells = DailyObserverTrade.query.filter(
            DailyObserverTrade.strategy_id == strategy_id,
            DailyObserverTrade.direction == "sell",
            DailyObserverTrade.date >= cooldown_start_date,
            DailyObserverTrade.date <= trade_date
        ).all()
        
        # 构建卖出历史字典
        sell_history = {trade.ts_code: trade.date for trade in recent_sells}
        engine._sell_history = sell_history
        logger.info(f"📋 加载卖出冷却期记录: {len(sell_history)}只股票在冷却期内")
        
        # 调用执行引擎决策
        decisions = engine.decide_daily_trades(
            holdings=holdings_for_engine,
            stock_scores=stock_scores_for_engine,
            strategy_params=strategy_params,
            trade_date=trade_date
        )

        print(f"[DEBUG] decisions: {decisions}")

        # 格式化买入信号（从decisions获取）
        buy_signals = []
        buy_count = len(decisions.get("buy", []))
        
        # 获取因子组合配置（用于生成详细买入原因）
        factor_configs = []
        if strategy.factor_combo_id:
            from models.factor_combo import FactorCombo
            combo = FactorCombo.query.get(strategy.factor_combo_id)
            if combo and combo.factor_config:
                configs = json.loads(combo.factor_config) if isinstance(combo.factor_config, str) else combo.factor_config
                factor_configs = configs.get("factors", [])
        
        if buy_count > 0 and cash > 0:
            # 等权分配现金给所有买入信号
            cash_per_stock = cash / buy_count
            
            for buy_decision in decisions.get("buy", []):
                ts_code = buy_decision.get("ts_code")
                price = buy_decision.get("price", 0)
                
                # 计算买入数量（向下取整到100的倍数，A股交易单位）
                if price > 0:
                    volume = int(cash_per_stock / price / 100) * 100
                    amount = price * volume
                else:
                    volume = 0
                    amount = 0

                # 计算买入后的预期占比
                after_market_value = total_value  # 总资产不变，只是现金转为持仓
                after_ratio = (amount / after_market_value * 100) if after_market_value > 0 else 0

                # 🆕 生成详细的买入原因分析
                reason_detail = _generate_buy_reason(ts_code, trade_date, factor_configs, buy_decision)

                buy_signals.append({
                    "ts_code": ts_code,
                    "name": stock_names.get(ts_code, ts_code),
                    "price": price,
                    "volume": volume,
                    "amount": amount,
                    "score": buy_decision.get("score", 0),
                    "rank": buy_decision.get("rank", 0),
                    "reason": reason_detail.get("summary", "因子选股"),
                    "reason_detail": reason_detail,  # 详细分析
                    "after_ratio": round(after_ratio, 2)
                })

        # 格式化卖出信号
        sell_signals = []
        for sell_decision in decisions.get("sell", []):
            ts_code = sell_decision.get("ts_code")
            holding_info = holdings_dict.get(ts_code, {})
            price = sell_decision.get("price", 0)
            volume = sell_decision.get("volume", 0)
            
            # 如果price为0，使用latest_prices中的当前价格作为后备
            if price == 0:
                price = latest_prices.get(ts_code, 0)
            
            # 如果还是0，使用买入价作为最后后备
            if price == 0:
                price = float(holding_info.get("buy_price", 0))
            
            amount = price * volume
            buy_price = float(holding_info.get("buy_price", 0))

            # 计算盈亏
            profit = amount - (buy_price * volume) - (amount * 0.0003) - (buy_price * volume * 0.0003)

            sell_signals.append({
                "ts_code": ts_code,
                "name": stock_names.get(ts_code, ts_code),
                "reason": sell_decision.get("reason", ""),
                "price": price,
                "volume": volume,
                "amount": amount,
                "buy_price": buy_price,
                "profit_loss": profit
            })

        # 继续持有的股票
        continue_holdings = []
        sold_codes = set(s.get("ts_code") for s in decisions.get("sell", []))
        for ts_code, holding_info in holdings_dict.items():
            if ts_code not in sold_codes:
                buy_price = float(holding_info.get("buy_price", 0))
                current_price = latest_prices.get(ts_code, buy_price)
                
                # 计算盈亏百分比
                profit_pct = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0.0

                continue_holdings.append({
                    "ts_code": ts_code,
                    "name": stock_names.get(ts_code, ts_code),
                    "buy_price": buy_price,
                    "current_price": current_price,
                    "profit_pct": round(profit_pct, 2)
                })

        # 🔴 T+1 智能判断：收盘后显示"明天执行"
        # 如果是收盘后，且最新记录是今天，则建议是"明天执行"
        is_tomorrow = False
        execution_date = latest_record.date
        execution_message = None
        
        if is_after_market_close and latest_record.date == today:
            is_tomorrow = True
            execution_date = next_trade_date
            execution_message = f"📅 基于今日({today})收盘数据，以下为明天({next_trade_date})的操作建议"
        elif latest_record.date < today:
            execution_message = f"⚠️ 数据日期({latest_record.date})较旧，请先更新数据"
        
        return success(data={
            "date": latest_record.date,  # 数据日期
            "execution_date": execution_date,  # 执行日期（收盘后为明天）
            "is_tomorrow": is_tomorrow,  # 是否是明天的建议
            "execution_message": execution_message,  # 执行提示
            "has_data": True,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "continue_holdings": continue_holdings,
            "current_holdings": current_holdings_list,  # 添加当前持仓详情（含占比）
            "total_value": total_value,  # 添加总资产
            "cash": cash,  # 添加现金
            "current_positions": len(current_holdings),
            "max_positions": strategy.max_positions
        })
    except Exception as e:
        logger.error(f"获取操作计划失败: {e}")
        import traceback
        traceback.print_exc()
        return error(message=f"获取失败: {str(e)}")


@daily_observer_bp.route("/strategies/<int:strategy_id>/recommendations", methods=["GET"])
def get_recommendations(strategy_id: int):
    """获取策略的推荐历史记录"""
    try:
        limit = request.args.get("limit", 30, type=int)
        records = get_recommendation_history(strategy_id, limit)
        return success(data=records)
    except Exception as e:
        logger.error(f"获取推荐历史失败: {e}")
        return error(message=str(e))


@daily_observer_bp.route("/strategies/<int:strategy_id>/recommendations/record", methods=["POST"])
def save_recommendation(strategy_id: int):
    """手动记录当天推荐"""
    try:
        result = record_recommendation(strategy_id)
        if result.get("success"):
            return success(data=result.get("data"), message=result.get("message"))
        else:
            return error(message=result.get("message"))
    except Exception as e:
        logger.error(f"记录推荐失败: {e}")
        return error(message=str(e))



# ============================================================================
# 合规改造接口 - 每日筛选结果（改造后）
# ============================================================================

@daily_observer_bp.route("/strategies/<int:strategy_id>/filter-results", methods=["GET"])
@token_required
@check_feature_limit("observer")  # 检查是否为专业版用户
def get_filter_results_compliant(strategy_id: int):
    """
    获取策略的筛选结果（改造后合规版）
    
    合规改造要点：
    1. ❌ 不输出：价格、数量、金额、买入建议
    2. ✅ 只输出：代码、名称、得分、排名、因子分析
    3. ✅ 必须加：免责声明
    
    文案改造：
    - "买入信号" -> "筛选结果"
    - "卖出信号" -> "不再符合条件"
    - "建议买入" -> "符合筛选条件"
    """
    try:
        tenant_id = get_current_tenant_id()
        
        # 验证策略所有权
        strategy = _verify_strategy_ownership(strategy_id, tenant_id)
        if not strategy:
            return error(message="策略不存在或无权访问", code=404)
        
        # 调用原有的 action-plan 接口获取数据
        from flask import current_app
        with current_app.test_request_context():
            # 复用 get_action_plan 的逻辑
            result = get_action_plan(strategy_id)
            
            if result.status_code != 200:
                return result
            
            # 解析返回的数据
            data = result.get_json()
            if data.get("code") != 0:
                return result
            
            plan_data = data.get("data", {})
            
            # 使用简化函数处理信号
            simplified = _simplify_signals(
                buy_signals=plan_data.get("buy_signals", []),
                sell_signals=plan_data.get("sell_signals", [])
            )
            
            # 构建改造后的响应
            return success(data={
                "date": plan_data.get("date"),
                "execution_date": plan_data.get("execution_date"),
                "strategy_name": strategy.name,
                "disclaimer": simplified["disclaimer"],
                "filter_results": simplified["filter_results"],
                "statistics": {
                    "total_pool": len(plan_data.get("buy_signals", [])) + len(plan_data.get("sell_signals", [])) + len(plan_data.get("continue_holdings", [])),
                    "qualified": len(plan_data.get("buy_signals", [])),
                    "not_qualified": len(plan_data.get("sell_signals", [])),
                    "holding": len(plan_data.get("continue_holdings", [])),
                    "avg_score": sum(s.get("score", 0) for s in simplified["filter_results"]) / len(simplified["filter_results"]) if simplified["filter_results"] else 0
                },
                "generated_at": datetime.now().isoformat()
            })
            
    except Exception as e:
        logger.error(f"获取筛选结果失败: {e}")
        import traceback
        traceback.print_exc()
        return error(message=f"获取失败: {str(e)}")

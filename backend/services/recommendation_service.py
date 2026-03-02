"""
推荐记录服务
记录每天收盘后的"明日操作建议"
"""
import json
import logging
from datetime import datetime, timedelta
from utils.database import db

logger = logging.getLogger(__name__)


def record_recommendation(strategy_id: int, target_date: str = None) -> dict:
    """
    记录策略的"明日操作建议"到数据库
    
    逻辑：
    - record_date: 数据日期（今天收盘后）
    - execution_date: 执行日期（明天）
    - holdings: 当前持仓（明天开盘前的状态）
    - buy_signals: 明天应该买入的
    - sell_signals: 明天应该卖出的
    
    Args:
        strategy_id: 策略ID
        target_date: 指定日期（用于补全历史数据），格式 YYYYMMDD
        
    Returns:
        dict: {"success": bool, "message": str, "data": dict}
    """
    try:
        from models.daily_observer import (
            DailyObserverStrategy,
            DailyObserverRecord,
            DailyObserverTrade
        )
        from models.daily_recommendation import DailyRecommendation
        from models.stock import Stock
        from models.bar_data import BarData
        
        strategy = DailyObserverStrategy.query.get(strategy_id)
        if not strategy:
            return {"success": False, "message": "策略不存在"}
        
        # 确定数据日期（record_date）
        if target_date:
            record_date = target_date
        else:
            latest_record = DailyObserverRecord.query.filter_by(
                strategy_id=strategy_id
            ).order_by(DailyObserverRecord.date.desc()).first()
            if not latest_record:
                return {"success": False, "message": "暂无观测数据"}
            record_date = latest_record.date
        
        # 获取该日期的观测记录（今天收盘后的状态）
        daily_record = DailyObserverRecord.query.filter_by(
            strategy_id=strategy_id,
            date=record_date
        ).first()
        
        if not daily_record:
            return {"success": False, "message": f"没有{record_date}的观测数据"}
        
        # 计算明天的交易日（execution_date）
        next_day = datetime.strptime(record_date, "%Y%m%d") + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        execution_date = next_day.strftime("%Y%m%d")
        
        # 检查是否已有记录
        existing = DailyRecommendation.query.filter_by(
            strategy_id=strategy_id,
            record_date=record_date
        ).first()
        
        if existing:
            logger.info(f"策略{strategy_id}在{record_date}已有记录，更新中...")
        
        # ========== 获取明天的交易（从 execution_date 读取） ==========
        # 如果明天的交易已经执行了，就用实际交易；否则重新计算预测
        tomorrow_trades = DailyObserverTrade.query.filter_by(
            strategy_id=strategy_id,
            date=execution_date
        ).all()
        
        # 当前持仓（今天收盘后的持仓 = 明天开盘前的持仓）
        holdings_dict = json.loads(daily_record.holdings) if daily_record.holdings else {}
        
        # 获取股票名称
        trade_codes = [t.ts_code for t in tomorrow_trades]
        all_ts_codes = list(set(trade_codes + list(holdings_dict.keys())))
        
        stocks = Stock.query.filter(Stock.ts_code.in_(all_ts_codes)).all() if all_ts_codes else []
        stock_names = {s.ts_code: s.name for s in stocks}
        
        # 获取价格
        price_dict = {}
        if all_ts_codes:
            bars = BarData.query.filter(
                BarData.ts_code.in_(all_ts_codes),
                BarData.trade_date == record_date
            ).all()
            price_dict = {bar.ts_code: float(bar.close) for bar in bars}
        
        # 构建当前持仓列表
        holdings_list = []
        for ts_code, info in holdings_dict.items():
            holdings_list.append({
                "ts_code": ts_code,
                "name": stock_names.get(ts_code, ts_code),
                "buy_price": float(info.get("buy_price", 0)),
                "current_price": price_dict.get(ts_code, 0),
                "volume": info.get("volume", 0)
            })
        
        # 如果明天的交易已执行，使用实际交易数据
        if tomorrow_trades:
            buy_signals = []
            sell_signals = []
            
            for trade in tomorrow_trades:
                signal_data = {
                    "ts_code": trade.ts_code,
                    "name": stock_names.get(trade.ts_code, trade.ts_code),
                    "price": float(trade.price) if trade.price else 0,
                    "volume": trade.volume or 0,
                    "reason": trade.signal_reason or ""
                }
                
                if trade.direction == "buy":
                    buy_signals.append(signal_data)
                else:
                    sell_signals.append(signal_data)
        else:
            # 明天的交易还没执行，需要重新计算预测
            buy_signals, sell_signals = _calculate_tomorrow_signals(
                strategy, daily_record, holdings_dict, stock_names, price_dict, record_date
            )
        
        # 保存或更新记录
        cash = float(daily_record.cash) if daily_record.cash else 0
        total_value = float(daily_record.total_value) if daily_record.total_value else 0
        
        if existing:
            existing.execution_date = execution_date
            existing.total_value = total_value
            existing.cash = cash
            existing.holdings = json.dumps(holdings_list, ensure_ascii=False)
            existing.buy_signals = json.dumps(buy_signals, ensure_ascii=False)
            existing.sell_signals = json.dumps(sell_signals, ensure_ascii=False)
            existing.created_at = datetime.now()
            db.session.commit()
            logger.info(f"✅ 更新策略{strategy_id}: {record_date}数据 -> {execution_date}建议")
        else:
            rec = DailyRecommendation(
                strategy_id=strategy_id,
                strategy_name=strategy.name,
                record_date=record_date,
                execution_date=execution_date,
                total_value=total_value,
                cash=cash,
                holdings=json.dumps(holdings_list, ensure_ascii=False),
                buy_signals=json.dumps(buy_signals, ensure_ascii=False),
                sell_signals=json.dumps(sell_signals, ensure_ascii=False)
            )
            db.session.add(rec)
            db.session.commit()
            logger.info(f"✅ 新增策略{strategy_id}: {record_date}数据 -> {execution_date}建议")
        
        return {
            "success": True,
            "message": f"已记录: 基于{record_date}数据，{execution_date}执行",
            "data": {
                "record_date": record_date,
                "execution_date": execution_date,
                "holdings_count": len(holdings_list),
                "buy_count": len(buy_signals),
                "sell_count": len(sell_signals)
            }
        }
        
    except Exception as e:
        logger.error(f"记录推荐失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}


def _calculate_tomorrow_signals(strategy, daily_record, holdings_dict, stock_names, price_dict, record_date):
    """计算明日交易信号（当明天的交易还没执行时）"""
    from models.daily_observer import DailyObserverTrade
    from datetime import datetime, timedelta
    
    # 获取策略的评分引擎
    engine_id = strategy.scoring_engine_id or "daily_observer"
    
    if engine_id == "simple_conservative":
        from services.scoring_engines.simple_conservative import SimpleConservativeEngine
        engine = SimpleConservativeEngine(factor_combo_id=strategy.factor_combo_id)
    elif engine_id == "v2_adaptive":
        from services.scoring_engines.v2_adaptive import V2AdaptiveEngine
        engine = V2AdaptiveEngine()
    elif engine_id == "v3_enhanced":
        from services.scoring_engines.v3_enhanced import V3EnhancedEngine
        engine = V3EnhancedEngine()
    elif engine_id == "v4_optimized":
        from services.scoring_engines.v4_optimized import V4OptimizedEngine
        engine = V4OptimizedEngine()
    elif engine_id == "v1_momentum":
        from services.scoring_engines.v1_momentum import V1MomentumEngine
        engine = V1MomentumEngine()
    else:
        from services.scoring_engines.daily_observer_engine import DailyObserverEngine
        engine = DailyObserverEngine()
    
    # 准备引擎参数
    if engine_id == "simple_conservative":
        strategy_params = {
            "min_score": 0.7,
            "max_positions": strategy.max_positions,
            "take_profit_ratio": 0.20,
            "stop_loss_ratio": -0.05,
            "hold_min_days": 5,
            "blacklist_cooldown": strategy.blacklist_cooldown
        }
    else:
        strategy_params = {
            "top_n": strategy.top_n,
            "max_positions": strategy.max_positions,
            "take_profit_ratio": strategy.take_profit_ratio,
            "stop_loss_ratio": strategy.stop_loss_ratio,
            "sell_rank_out": strategy.sell_rank_out,
            "signal_confirm_days": strategy.signal_confirm_days,
            "blacklist_cooldown": strategy.blacklist_cooldown
        }
    
    # 准备持仓数据
    holdings_for_engine = {}
    for ts_code, info in holdings_dict.items():
        holdings_for_engine[ts_code] = {
            "buy_price": float(info.get("buy_price", 0)),
            "buy_date": info.get("buy_date"),
            "volume": info.get("volume", 0),
            "score": info.get("score", 0),
            "rank": info.get("rank", 0)
        }
    
    # 准备得分数据
    scores_dict = json.loads(daily_record.scores) if daily_record.scores else {}
    selected_stocks = json.loads(daily_record.selected_stocks) if daily_record.selected_stocks else []
    all_ts_codes = list(set(selected_stocks + list(holdings_dict.keys())))
    
    scored_stocks = [
        (ts_code, scores_dict.get(ts_code, 0))
        for ts_code in all_ts_codes
        if ts_code in scores_dict
    ]
    scored_stocks.sort(key=lambda x: x[1], reverse=True)
    stock_ranks = {ts_code: i+1 for i, (ts_code, _) in enumerate(scored_stocks)}
    
    stock_scores_for_engine = {}
    for ts_code in all_ts_codes:
        stock_scores_for_engine[ts_code] = {
            "score": scores_dict.get(ts_code, 0),
            "price": price_dict.get(ts_code, 0),
            "rank": stock_ranks.get(ts_code, 999)
        }
    
    # 加载卖出冷却期
    cooldown_days = strategy.blacklist_cooldown
    cooldown_start_date = (datetime.strptime(record_date, "%Y%m%d") - timedelta(days=cooldown_days)).strftime("%Y%m%d")
    
    recent_sells = DailyObserverTrade.query.filter(
        DailyObserverTrade.strategy_id == strategy.id,
        DailyObserverTrade.direction == "sell",
        DailyObserverTrade.date >= cooldown_start_date,
        DailyObserverTrade.date <= record_date
    ).all()
    
    sell_history = {trade.ts_code: trade.date for trade in recent_sells}
    engine._sell_history = sell_history
    
    # 调用引擎决策
    decisions = engine.decide_daily_trades(
        holdings=holdings_for_engine,
        stock_scores=stock_scores_for_engine,
        strategy_params=strategy_params,
        trade_date=record_date
    )
    
    # 🔴 修复：计算卖出后的可用资金
    # 获取当前现金
    cash = float(daily_record.cash) if daily_record.cash else 0
    
    # 先计算哪些持仓会被卖出，以及会回笼多少资金
    sell_codes = [s.get("ts_code") for s in decisions.get("sell", [])]
    sell_revenue = 0.0
    
    for sell_decision in decisions.get("sell", []):
        ts_code = sell_decision.get("ts_code")
        if ts_code in holdings_dict:
            volume = holdings_dict[ts_code].get("volume", 0)
            price = price_dict.get(ts_code, 0)
            if price > 0 and volume > 0:
                amount = price * volume
                commission = amount * 0.0003
                sell_revenue += (amount - commission)
    
    # 可用现金 = 当前现金 + 卖出收入
    available_cash = cash + sell_revenue
    
    logger.info(f"💰 推荐生成：当前现金{cash:.2f}，预计卖出收入{sell_revenue:.2f}，可用现金{available_cash:.2f}")

    
    # 获取买入/卖出股票的额外信息
    from models.stock import Stock
    from models.bar_data import BarData
    
    buy_codes = [b.get("ts_code") for b in decisions.get("buy", [])]
    sell_codes = [s.get("ts_code") for s in decisions.get("sell", [])]
    all_signal_codes = list(set(buy_codes + sell_codes))
    
    # 补充获取股票名称
    if all_signal_codes:
        extra_stocks = Stock.query.filter(Stock.ts_code.in_(all_signal_codes)).all()
        for s in extra_stocks:
            if s.ts_code not in stock_names:
                stock_names[s.ts_code] = s.name
    
    # 补充获取价格
    if all_signal_codes:
        extra_bars = BarData.query.filter(
            BarData.ts_code.in_(all_signal_codes),
            BarData.trade_date == record_date
        ).all()
        for bar in extra_bars:
            if bar.ts_code not in price_dict:
                price_dict[bar.ts_code] = float(bar.close)
    
    # 格式化买入/卖出信号
    buy_signals = []
    
    # 🔴 修复：使用可用现金（包含卖出收入）计算买入预算
    # 计算卖出后的剩余持仓数
    remaining_positions = len(holdings_dict) - len(sell_codes)
    max_positions = strategy.max_positions
    available_slots = max_positions - remaining_positions
    
    if available_slots > 0 and available_cash > 0:
        buy_budget = available_cash / available_slots
        logger.info(f"📊 买入预算：可用仓位{available_slots}个，单仓预算{buy_budget:.2f}")
    else:
        buy_budget = 0
        logger.info(f"⚠️  无法买入：可用仓位{available_slots}，可用现金{available_cash:.2f}")

    buy_count = len(decisions.get("buy", []))
    
    if buy_count > 0 and buy_budget > 0:
        # 🔴 使用修正后的买入预算
        for buy in decisions.get("buy", []):
            ts_code = buy.get("ts_code")
            # 优先使用引擎返回的价格，否则从 price_dict 获取
            price = buy.get("price") or price_dict.get(ts_code, 0)
            volume = int(buy_budget / price / 100) * 100 if price > 0 else 0
            
            if volume < 100:
                logger.warning(f"⚠️  {ts_code} 计算数量不足100股，跳过")
                continue
            
            buy_signals.append({
                "ts_code": ts_code,
                "name": stock_names.get(ts_code, ts_code),
                "price": price,
                "volume": volume,
                "reason": buy.get("reason", "因子选股")
            })
    
    sell_signals = []
    for sell in decisions.get("sell", []):
        ts_code = sell.get("ts_code")
        price = sell.get("price") or price_dict.get(ts_code, 0)
        sell_signals.append({
            "ts_code": ts_code,
            "name": stock_names.get(ts_code, ts_code),
            "price": price,
            "volume": sell.get("volume", 0),
            "reason": sell.get("reason", "")
        })
    
    return buy_signals, sell_signals


def get_recommendation_history(strategy_id: int, limit: int = 30) -> list:
    """
    获取策略的推荐历史
    
    Args:
        strategy_id: 策略ID
        limit: 最多返回的记录数
        
    Returns:
        list: 推荐记录列表
    """
    from models.daily_recommendation import DailyRecommendation
    
    records = DailyRecommendation.query.filter_by(
        strategy_id=strategy_id
    ).order_by(DailyRecommendation.record_date.desc()).limit(limit).all()
    
    return [r.to_dict() for r in records]

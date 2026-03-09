"""
每日模拟观测服务
负责执行每日的选股、模拟交易、资金管理
保持简单逻辑，不依赖复杂的执行引擎
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict

from flask import current_app
from utils.database import db
from sqlalchemy import func
from models.daily_observer import (
    DailyObserverStrategy,
    DailyObserverRecord,
    DailyObserverTrade
)
from models.factor_combo import FactorCombo
from models.factor_data import FactorData
from models.bar_data import BarData
from models.stock import Stock
from services.scoring_engines.registry import get_engine
from services.data_completion_service import data_completion_service

logger = logging.getLogger(__name__)

# 固定手续费
COMMISSION_RATE = 0.0003  # 双边0.03%


class DailyObserverService:
    """每日模拟观测服务"""

    def __init__(self):
        # 尝试从多个来源获取token
        self.tushare_token = os.getenv("TUSHARE_TOKEN")

        # 尝试从Application读取
        if not self.tushare_token:
            try:
                import sys
                sys.path.insert(0, '../..')
                from Application import TUSHARE_TOKEN
                self.tushare_token = TUSHARE_TOKEN
            except Exception:
                pass

        # 尝试从settings读取
        if not self.tushare_token:
            try:
                from config.settings import settings
                self.tushare_token = getattr(settings, 'TUSHARE_TOKEN', None)
            except Exception:
                pass

        if not self.tushare_token:
            self.ts = None
            return

        # TuShare Pro 接口
        import tushare as ts
        self.ts = ts.pro_api(token=self.tushare_token)

        # 初始化执行引擎（稍后在策略中配置，但目前���使用）
        self.scoring_engine = None

    def _get_stock_pool(self, strategy: DailyObserverStrategy) -> List[str]:
        """获取股票池"""
        if strategy.stock_pool:
            return json.loads(strategy.stock_pool)
        return []

    def _has_factor_data(self, stocks: List[str], trade_date: str, min_ratio: float = 0.3) -> bool:
        """检查是否有足够的因子数据（默认30%覆盖率）"""
        try:
            count = FactorData.query.filter(
                FactorData.ts_code.in_(stocks),
                FactorData.trade_date == trade_date
            ).count()
            ratio = count / len(stocks) if stocks else 0
            print(f"[DEBUG] {trade_date}: {count}/{len(stocks)} = {ratio*100:.1f}% >= {min_ratio*100}%? {ratio >= min_ratio}")
            return ratio >= min_ratio
        except Exception as e:
            logger.debug(f"检查因子数据失败: {e}")
            return False

    def _has_kline_data_for_date(self, stocks: List[str], trade_date: str, min_ratio: float = 0.3) -> bool:
        """
        检查指定日期的K线数据是否已准备好
        
        交易执行需要当天的价格数据（开盘价买入、收盘价计算市值）
        如果当天K线数据不足，就不应该执行交易，避免产生异常数据
        
        Args:
            stocks: 股票池
            trade_date: 交易日期（YYYYMMDD格式）
            min_ratio: 最小覆盖率（默认30%）
            
        Returns:
            bool: 是否有足够的K线数据
        """
        from models.bar_data import BarData
        
        try:
            if not stocks:
                return False
                
            count = BarData.query.filter(
                BarData.ts_code.in_(stocks),
                BarData.trade_date == trade_date
            ).count()
            
            ratio = count / len(stocks) if stocks else 0
            has_enough = ratio >= min_ratio
            
            logger.debug(f"[K线检查] {trade_date}: {count}/{len(stocks)} = {ratio*100:.1f}% >= {min_ratio*100}%? {has_enough}")
            
            if not has_enough:
                logger.warning(f"⚠️ {trade_date} K线数据不足: {count}/{len(stocks)} ({ratio*100:.1f}%)")
            
            return has_enough
        except Exception as e:
            logger.error(f"检查K线数据失败: {e}")
            return False

    def _calculate_scores(self, strategy: DailyObserverStrategy, stocks: List[str],
                         trade_date: str) -> Dict[str, Dict]:
        """计算所有股票的因子得分（使用执行引擎）"""
        from models.factor_combo import FactorCombo

        # 使用策略配置的执行引擎
        engine = get_engine(strategy.scoring_engine_id)
        
        # 🔴 对于 simple_conservative 引擎,需要设置因子组合ID并加载配置
        if hasattr(engine, 'factor_combo_id') and hasattr(engine, '_load_factor_config'):
            engine.factor_combo_id = strategy.factor_combo_id
            engine._load_factor_config()

        # v2_adaptive引擎需要根据市场状态动态选择因子组合
        if hasattr(engine, '_detect_market_state'):
            # 判断市场状态
            market_state = engine._detect_market_state(trade_date)

            # 根据市场状态选择因子组合
            if market_state == "bull":
                combo = FactorCombo.query.get(engine.bull_combo_id)
            elif market_state == "bear":
                combo = FactorCombo.query.get(engine.bear_combo_id)
            else:  # range
                combo = FactorCombo.query.get(engine.range_combo_id)

            if not combo:
                logger.error(f"因子组合不存在 (market_state={market_state})")
                return {}

            print(f"[DEBUG] {trade_date}: 市场状态={market_state}, 使用因子组合={combo.name}")
        else:
            # 其他引擎使用策略配置的因子组合
            combo = FactorCombo.query.get(strategy.factor_combo_id)
            if not combo:
                logger.error(f"因子组合{strategy.factor_combo_id}不存在")
                return {}

        try:
            factor_config = json.loads(combo.factor_config)
            factors = factor_config.get("factors", [])
        except Exception as e:
            logger.error(f"解析因子组合配置失败: {e}")
            return {}

        if not factors:
            logger.error("因子组合没有配置因子")
            return {}

        # 使用引擎的标准化打分方法
        stock_scores = engine._calculate_daily_scores(stocks, trade_date, factors)

        return stock_scores

    def _select_stocks(self, stock_scores: Dict[str, Dict], top_n: int) -> List[Dict]:
        """根据得分选股"""
        # 按得分排序，返回前top_n只
        sorted_stocks = sorted(
            stock_scores.items(),
            key=lambda x: x[1].get("score", 0),
            reverse=True
        )
        selected = []

        for i, (ts_code, data) in enumerate(sorted_stocks[:top_n]):
            selected.append({
                "ts_code": ts_code,
                "score": data.get("score", 0),
                "price": data.get("price", 0),
                "rank": i + 1
            })

        return selected

    def _get_price(self, ts_code: str, trade_date: str) -> Optional[float]:
        """获取收盘价（优先本地，备用Tushare）"""
        try:
            # 优先从本地BarData表获取
            bar = BarData.query.filter_by(
                ts_code=ts_code,
                trade_date=trade_date
            ).first()

            if bar and bar.close:
                return float(bar.close)
        except Exception as e:
            logger.debug(f"从本地获取价格失败: {e}")

        # 备用：从Tushare获取
        if self.ts is None:
            return None
        try:
            df = self.ts.daily(ts_code=ts_code, start_date=trade_date, end_date=trade_date)
            if df is not None and len(df) > 0:
                return float(df.iloc[0]['close'])
        except Exception as e:
            logger.debug(f"从Tushare获取价格失败: {e}")

        return None

    def _get_latest_price(self, ts_code: str, trade_date: str) -> Optional[float]:
        """获取最近的收盘价（向前查找，用于节假日等无数据情况）"""
        try:
            # 向前查找最近14天的收盘价
            bar = BarData.query.filter(
                BarData.ts_code == ts_code,
                BarData.trade_date <= trade_date
            ).order_by(BarData.trade_date.desc()).first()
            
            if bar and bar.close:
                return float(bar.close)
        except Exception as e:
            logger.debug(f"获取最近价格失败: {e}")
        
        return None

    def _get_latest_record(self, strategy_id: int) -> Optional[DailyObserverRecord]:
        """获取最新记录"""
        return DailyObserverRecord.query.filter_by(
            strategy_id=strategy_id
        ).order_by(DailyObserverRecord.date.desc()).first()

    def _get_prev_trading_day(self, trade_date: str, stock_pool: List[str] = None) -> Optional[str]:
        """
        获取前一个有数据的交易日

        Args:
            trade_date: 当前交易日 YYYYMMDD
            stock_pool: 股票池（用于检查是否有因子数据）

        Returns:
            前一个有数据的交易日 YYYYMMDD，如果没有则返回None
        """
        date = datetime.strptime(trade_date, "%Y%m%d")

        # 🔴 优先从交易日历向前查找
        try:
            from models.trading_calendar import TradingCalendar

            # 向前查找最多14天（2周）
            for days_back in range(1, 15):
                prev_date = date - timedelta(days=days_back)
                prev_date_str = prev_date.strftime("%Y%m%d")

                # 查询交易日历
                record = TradingCalendar.query.get(prev_date_str)

                # 如果记录存在且是交易日，检查因子数据
                if record and record.is_trading_day:
                    if stock_pool:
                        if self._has_factor_data(stock_pool, prev_date_str):
                            logger.debug(f"📅 {trade_date} 的信号日期: {prev_date_str} (向前{days_back}天，使用交易日历)")
                            return prev_date_str
                    else:
                        logger.debug(f"📅 {trade_date} 的信号日期: {prev_date_str} (向前{days_back}天，使用交易日历)")
                        return prev_date_str

                # 如果交易日历中没有��录，跳到下一个日期
                if not record:
                    continue
        except Exception as e:
            logger.debug(f"从交易日历查找失败: {e}")

        # 备用方案：原始逻辑（跳过周末 + 检查因子数据）
        for days_back in range(1, 15):
            prev_date = date - timedelta(days=days_back)

            # 跳过周末
            if prev_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
                continue

            prev_date_str = prev_date.strftime("%Y%m%d")

            # 如果提供了股票池，检查是否有因子数据
            if stock_pool:
                if self._has_factor_data(stock_pool, prev_date_str):
                    logger.debug(f"📅 {trade_date} 的信号日期: {prev_date_str} (向前{days_back}天，备用方案)")
                    return prev_date_str
            else:
                # 没有股票池，只跳过周末
                return prev_date_str

        # 14天内都没有找到有数据的交易日
        logger.warning(f"⚠️ {trade_date} 向前14天内未找到有数据的交易日")
        return None
    
    def _get_trading_days(self, start_date: str, end_date: str, stock_pool: List[str] = None) -> List[str]:
        """
        获取交易日列表（优先使用交易日历）

        1. 优先从TradingCalendar表获取真实交易日
        2. 备用：从K线数据中获取实际交易日
        3. 最后备用：简单过滤周末
        """
        # 🔴 优先从交易日历获取
        try:
            from models.trading_calendar import TradingCalendar
            records = TradingCalendar.query.filter(
                TradingCalendar.cal_date >= start_date,
                TradingCalendar.cal_date <= end_date,
                TradingCalendar.is_trading_day == True
            ).order_by(TradingCalendar.cal_date).all()

            if records and len(records) > 0:
                trading_days = [r.cal_date for r in records]
                logger.info(f"📅 从交易日历获取交易日: {len(trading_days)}天 ({start_date} ~ {end_date})")
                return trading_days
        except Exception as e:
            logger.debug(f"从交易日历获取失败: {e}")

        # 备用1: 从K线数据中获取真实交易日
        try:
            query = BarData.query.filter(
                BarData.trade_date >= start_date,
                BarData.trade_date <= end_date
            )

            # 如果有股票池，只看股票池的数据
            if stock_pool:
                query = query.filter(BarData.ts_code.in_(stock_pool[:10]))  # 取前10只检查

            # 获取唯一的交易日期
            dates = db.session.query(BarData.trade_date).filter(
                BarData.trade_date >= start_date,
                BarData.trade_date <= end_date
            ).distinct().order_by(BarData.trade_date).all()

            if dates:
                trading_days = [d[0] for d in dates]
                logger.info(f"📅 从K线数据获取交易日: {len(trading_days)}天 ({start_date} ~ {end_date})")
                return trading_days
        except Exception as e:
            logger.warning(f"从K线数据获取交易日失败: {e}")

        # 备用2: 简单过滤周末（可能包含节假日）
        logger.warning("⚠️ 使用简单交易日过滤（可能包含节假日）")
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")
        days = []
        d = start
        while d <= end:
            if d.weekday() < 5:
                days.append(d.strftime("%Y%m%d"))
            d += timedelta(days=1)
        return days

    def _run_daily_observation(self, strategy_id: int, trade_date: str) -> Dict:
        """
        执行单日观测（T+1交易模式）
        
        逻辑：
        - trade_date是T日
        - 使用T-1日的数据生成交易信号
        - 在T日执行交易（执行T-1日收盘后生成的信号）
        - 记录为T日的交易
        """
        result = {
            "date": trade_date,
            "success": False,
            "error": None,
            "selected_stocks": [],
            "trades": [],
            "day_return": 0,
            "total_value": 0
        }

        try:
            # 获取策略
            strategy = DailyObserverStrategy.query.get(strategy_id)
            if not strategy:
                result["error"] = "策略不存在"
                return result

            # 检查是否已处理
            existing = DailyObserverRecord.query.filter_by(
                strategy_id=strategy_id,
                date=trade_date
            ).first()
            if existing:
                result["success"] = True
                result["message"] = f"{trade_date}已处理"
                return result

            # 获取股票池
            stock_pool = self._get_stock_pool(strategy)
            if not stock_pool:
                result["error"] = "股票池为空"
                return result

            # 🔴 T+1逻辑：优先读取昨天生成的推荐记录
            from models.daily_recommendation import DailyRecommendation
            recommendation = DailyRecommendation.query.filter_by(
                strategy_id=strategy_id,
                execution_date=trade_date  # 查找execution_date=今天的推荐
            ).first()
            
            # 🔴 T+1逻辑：获取前一个有数据的交易日(用于计算得分)
            signal_date = self._get_prev_trading_day(trade_date, stock_pool)
            
            if signal_date is None:
                logger.debug(f"跳过{trade_date}：向前14天内未找到有数据的交易日")
                result["error"] = "前一交易日数据不足"
                return result

            # 🔴 新增：只对"今天"检查K线数据是否已准备好
            today = datetime.now().strftime("%Y%m%d")
            if trade_date == today:
                if not self._has_kline_data_for_date(stock_pool, trade_date):
                    logger.warning(f"⚠️ 跳过{trade_date}：今天的K线数据未准备好，请先下载")
                    result["error"] = f"{trade_date}的K线数据未准备好"
                    result["skip_reason"] = "kline_not_ready"
                    return result

            # 🔴 使用前一个有数据的交易日来计算得分（生成今日要执行的信号）
            logger.info(f"📊 {trade_date}: 使用{signal_date}的数据生成交易信号")
            stock_scores = self._calculate_scores(strategy, stock_pool, signal_date)
            
            if not stock_scores:
                result["error"] = "无有效得分"
                return result
            
            # 选股
            selected = self._select_stocks(stock_scores, strategy.top_n)
            result["selected_stocks"] = [s["ts_code"] for s in selected]
            
            # 如果有推荐记录,使用推荐中的买卖信号
            use_recommendation = recommendation is not None
            if use_recommendation:
                logger.info(f"📋 {trade_date}: 使用推荐记录(基于{recommendation.record_date}的数据)")
                # 从推荐记录中解析买卖信号
                recommendation_buy = json.loads(recommendation.buy_signals) if recommendation.buy_signals else []
                recommendation_sell = json.loads(recommendation.sell_signals) if recommendation.sell_signals else []
            else:
                logger.warning(f"⚠️ {trade_date}: 没有推荐记录,重新计算交易信号")

            # 获取上一日记录
            prev_record = DailyObserverRecord.query.filter(
                DailyObserverRecord.strategy_id == strategy_id,
                DailyObserverRecord.date < trade_date
            ).order_by(DailyObserverRecord.date.desc()).first()

            # 初始化资金和持仓
            initial_capital = 1000000
            if prev_record:
                capital = float(prev_record.cash) if prev_record.cash else 1000000
                holdings_dict = json.loads(prev_record.holdings) if prev_record.holdings else {}
            else:
                capital = float(initial_capital)
                holdings_dict = {}

            # 初始化交易列表
            trades = []

            # 🔴 如果使用推荐记录,直接转换为decisions格式
            if use_recommendation:
                # 从推荐记录构建decisions
                decisions = {"buy": [], "sell": []}
                
                # 处理卖出信号
                for sell_signal in recommendation_sell:
                    ts_code = sell_signal.get("ts_code")
                    if ts_code in holdings_dict:
                        decisions["sell"].append({
                            "ts_code": ts_code,
                            "price": self._get_price(ts_code, trade_date) or sell_signal.get("price", 0),
                            "volume": holdings_dict[ts_code].get("volume", 0),
                            "reason": sell_signal.get("reason", "推荐卖出")
                        })
                
                # 处理买入信号
                for buy_signal in recommendation_buy:
                    decisions["buy"].append({
                        "ts_code": buy_signal.get("ts_code"),
                        "price": self._get_price(buy_signal.get("ts_code"), trade_date) or buy_signal.get("price", 0),
                        "volume": buy_signal.get("volume", 0),
                        "score": buy_signal.get("score", 0),
                        "rank": buy_signal.get("rank", 0),
                        "reason": buy_signal.get("reason", "推荐买入")
                    })
                
                logger.info(f"✅ 使用推荐: 买入{len(decisions['buy'])}只, 卖出{len(decisions['sell'])}只")
            else:
                # 没有推荐记录,使用引擎重新计算
                # 使用执行引擎决策买卖
                engine = get_engine(strategy.scoring_engine_id)
                
                # 🔴 根据引擎类型准备不同的参数（确保与回测逻辑一致）
                engine_id = strategy.scoring_engine_id or "daily_observer"
                if engine_id == "simple_conservative":
                    # simple_conservative 引擎使用自己的保守参数
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
                        "max_positions": strategy.max_positions,
                        "take_profit_ratio": strategy.take_profit_ratio,
                        "stop_loss_ratio": strategy.stop_loss_ratio,
                        "top_n": strategy.top_n,
                        "sell_rank_out": strategy.sell_rank_out,
                        "signal_confirm_days": strategy.signal_confirm_days,
                        "blacklist_cooldown": strategy.blacklist_cooldown,
                        "rank_drop_threshold": strategy.rank_drop_threshold or 15  # 从数据库读取，默认15
                    }
                
                # 🔴 从数据库加载卖出历史（冷却期检查）
                cooldown_days = strategy.blacklist_cooldown
                cooldown_start_date = (datetime.strptime(trade_date, "%Y%m%d") - timedelta(days=cooldown_days)).strftime("%Y%m%d")
                recent_sells = DailyObserverTrade.query.filter(
                    DailyObserverTrade.strategy_id == strategy_id,
                    DailyObserverTrade.direction == "sell",
                    DailyObserverTrade.date >= cooldown_start_date,
                    DailyObserverTrade.date < trade_date  # 不包括当天
                ).all()
                engine._sell_history = {trade.ts_code: trade.date for trade in recent_sells}
                
                # 🔴 加载亏损计数（用于simple_conservative引擎）
                if hasattr(engine, 'stock_loss_count'):
                    from collections import defaultdict
                    engine.stock_loss_count = defaultdict(int)
                    # 统计历史亏损次数
                    loss_sells = DailyObserverTrade.query.filter(
                        DailyObserverTrade.strategy_id == strategy_id,
                        DailyObserverTrade.direction == "sell",
                        DailyObserverTrade.signal_reason.like("%止损%")
                    ).all()
                    for trade in loss_sells:
                        engine.stock_loss_count[trade.ts_code] += 1

                decisions = engine.decide_daily_trades(
                    holdings=holdings_dict,
                    stock_scores=stock_scores,
                    strategy_params=strategy_params,
                    trade_date=trade_date
                )
                
                logger.info(f"⚠️ 重新计算: 买入{len(decisions['buy'])}只, 卖出{len(decisions['sell'])}只")

            # 🔴 修改：先执行卖出决策（与回测逻辑保持一致）
            # 🔴 修改：先执行卖出决策（与回测逻辑保持一致）
            for sell_signal in decisions["sell"]:
                ts_code = sell_signal["ts_code"]
                price = sell_signal["price"]
                volume = sell_signal["volume"]

                amount = float(price * volume)
                commission = amount * COMMISSION_RATE

                # 记录卖出
                trade = DailyObserverTrade(
                    strategy_id=strategy_id,
                    record_id=0,
                    date=trade_date,
                    ts_code=ts_code,
                    direction="sell",
                    price=price,
                    volume=volume,
                    amount=amount,
                    commission=commission,
                    signal_reason=sell_signal["reason"],
                    composite_score=holdings_dict[ts_code].get("score", 0),
                    rank=holdings_dict[ts_code].get("rank", 0)
                )
                trades.append(trade)

                # 更新资金
                capital += (amount - commission)

                # 移除持仓
                del holdings_dict[ts_code]

            # 🔴 然后执行买入决策（使用卖出后的资金）
            # 🔴 修复：考虑手续费，预留1.5倍的手续费空间确保资金充足
            available_capital = capital
            positions_after_sell = strategy.max_positions - len(holdings_dict)
            # 预留手续费空间：买入时需要支付手续费，所以预算要预留出来
            # 公式：实际可用资金 = 当前资金 / (1 + 手续费率)，大约预留0.1%的空间
            effective_capital = available_capital * (1 - COMMISSION_RATE * 1.5)
            buy_budget = effective_capital / max(1, positions_after_sell)
            for buy_signal in decisions["buy"]:
                ts_code = buy_signal["ts_code"]
                price = buy_signal["price"]

                # 计算买入数量
                volume = int(buy_budget / price / 100) * 100
                if volume < 100:
                    continue

                amount = float(price * volume)
                commission = amount * COMMISSION_RATE

                # 检查资金是否充足
                if capital < (amount + commission):
                    logger.warning(f"资金不足，跳过买入{ts_code}: 需要{amount + commission:.2f}，剩余{capital:.2f}")
                    continue

                # 记录买入
                trade = DailyObserverTrade(
                    strategy_id=strategy_id,
                    record_id=0,
                    date=trade_date,
                    ts_code=ts_code,
                    direction="buy",
                    price=price,
                    volume=volume,
                    amount=amount,
                    commission=commission,
                    signal_reason=buy_signal["reason"],
                    composite_score=buy_signal["score"],
                    rank=buy_signal["rank"]
                )
                trades.append(trade)

                # 更新资金和持仓
                capital -= (amount + commission)
                holdings_dict[ts_code] = {
                    "buy_price": price,
                    "buy_date": trade_date,
                    "volume": volume,
                    "score": buy_signal["score"],
                    "rank": buy_signal["rank"]
                }

            # 计算持仓市值（使用T日当天收盘价）
            position_value = 0
            for ts_code, holding in holdings_dict.items():
                price = None
                
                # 1. 🔴 优先从数据库获取当天(T日)收盘价
                price = self._get_price(ts_code, trade_date)
                
                # 2. 如果没有，获取最近的收盘价（如节假日）
                if not price or price <= 0:
                    price = self._get_latest_price(ts_code, trade_date)
                
                # 3. 最后保底使用买入价
                if not price or price <= 0:
                    price = float(holding.get("buy_price", 0))
                
                if price and price > 0:
                    position_value += price * holding["volume"]

            total_value = capital + position_value

            # 计算收益率
            day_return = 0
            # 计算收益率
            if prev_record:
                prev_value = float(prev_record.total_value) if prev_record.total_value else initial_capital
                day_return = (total_value - prev_value) / prev_value * 100 if prev_value > 0 else 0
            else:
                day_return = 0
            
            # 累计收益率 = (当前总资产 - 初始资金) / 初始资金 * 100
            cumulative_return = (total_value - initial_capital) / initial_capital * 100

            # 构建返回数据
            result.update({
                "selected_stocks": selected,
                "day_return": day_return,
                "cumulative_return": cumulative_return,
                "total_value": total_value,
                "capital": capital,
                "position_value": position_value,
                "cash": capital,
                "holdings": json.dumps(holdings_dict),
                "holding_count": len(holdings_dict)
            })

            # 创建观测记录
            record = DailyObserverRecord(
                strategy_id=strategy_id,
                date=trade_date,
                selected_stocks=json.dumps([s["ts_code"] for s in selected]),
                scores=json.dumps({k: v.get("score", 0) for k, v in stock_scores.items()}),
                capital=capital,
                position_value=position_value,
                cash=capital,
                day_return=day_return,
                cumulative_return=cumulative_return,
                total_value=total_value,
                holdings=json.dumps(holdings_dict),
                holding_count=len(holdings_dict)
            )

            db.session.add(record)
            db.session.flush()  # 先flush获取record.id

            # 添加交易记录到数据库
            for trade in trades:
                trade.record_id = record.id
                db.session.add(trade)

            db.session.commit()

            result["success"] = True
            result["trades"] = trades
            
            # 🔴 执行完交易后,立即生成明日推荐
            try:
                from services.recommendation_service import record_recommendation
                rec_result = record_recommendation(strategy_id, target_date=trade_date)
                if rec_result.get("success"):
                    logger.info(f"✅ {trade_date}交易完成,已生成明日推荐: {rec_result.get('message')}")
                    result["recommendation_saved"] = True
                else:
                    logger.warning(f"⚠️ 生成明日推荐失败: {rec_result.get('message')}")
                    result["recommendation_saved"] = False
            except Exception as rec_e:
                logger.error(f"生成明日推荐异常: {rec_e}")
                import traceback
                traceback.print_exc()
                result["recommendation_error"] = str(rec_e)

        except Exception as e:
            logger.error(f"执行观测失败: {e}")
            result["error"] = str(e)

        return result

    def sync_strategy(self, strategy_id: int, auto_complete_data: bool = True) -> Dict:
        """
        同步单个策略（从上次运行日期到今天）
        
        Args:
            strategy_id: 策略ID
            auto_complete_data: 是否自动补全数据（K线+因子）
        """
        logger.info(f"=== sync_strategy 开始: strategy_id={strategy_id}, auto_complete_data={auto_complete_data} ===")

        result = {
            "strategy_id": strategy_id,
            "synced": 0,
            "errors": [],
            "data_completion": None
        }

        try:
            strategy = DailyObserverStrategy.query.get(strategy_id)
            if not strategy:
                result["errors"].append("策略不存在")
                return result

            # 确定起始日期（使用策略配置的起始日期）
            start_date = strategy.start_date or "20250901"
            logger.info(f"策略{strategy_id}: 起始日期={start_date}")

            # 🔥 结束日期改为昨天，不尝试补全今天的数据（今天还没收盘）
            from datetime import timedelta
            end_date = datetime.now().strftime("%Y%m%d")
            logger.info(f"同步结束日期: {end_date}（不包含今天，避免因今天无数据导致失败）")

            # 获取股票池
            stock_pool = self._get_stock_pool(strategy)
            logger.info(f"策略{strategy_id}: 股票池大小={len(stock_pool)}")

            # 获取交易日列表
            trading_days = self._get_trading_days(start_date, end_date)
            logger.info(f"策略{strategy_id}: 起始日期{start_date}, 结束日期{end_date}, 交易日数{len(trading_days)}")

            if not stock_pool:
                result["errors"].append("股票池为空，请先添加股票")
                return result

            if not trading_days:
                result["errors"].append("没有交易日")
                return result
            
            # 🔴 新增：自动补全数据
            if auto_complete_data:
                logger.info(f"🔄 开始自动补全数据: {start_date} 至 {end_date}")
                completion_result = data_completion_service.ensure_data_ready(
                    stock_pool=stock_pool,
                    start_date=start_date,
                    end_date=end_date,
                    skip_weekends=True
                )
                result["data_completion"] = completion_result
                
                if not completion_result.get("success"):
                    logger.warning(f"⚠️ 数据补全有错误: {completion_result.get('errors')}")
                else:
                    logger.info(f"✅ 数据补全完成: 处理{len(completion_result.get('dates_processed', []))}天")


            # 执行每个交易日
            processed_count = 0
            skipped_count = 0
            today = datetime.now().strftime("%Y%m%d")
            
            # 🔴 T+1逻辑：第一天没有前一天数据，第一天空仓
            if len(trading_days) > 0:
                first_day = trading_days[0]
                # 检查第一天的前一个有数据的交易日
                prev_first_day = self._get_prev_trading_day(first_day, stock_pool)
                if prev_first_day is None:
                    logger.info(f"⚠️ 第一天{first_day}向前未找到有数据的交易日，第一天空仓")
                    # 第一天空仓：创建一个空record
                    first_record = DailyObserverRecord(
                        strategy_id=strategy_id,
                        date=first_day,
                        capital=1000000,
                        cash=1000000,
                        position_value=0,
                        total_value=1000000,
                        holdings="{}",
                        selected_stocks="[]",
                        scores="{}",
                        day_return=0,
                        cumulative_return=0
                    )
                    db.session.add(first_record)
                    db.session.commit()
                    logger.info(f"✅ 第一天{first_day}：空仓记录已创建")
                    result["synced"] += 1
                    processed_count += 1
            
            # 🔴 T+1 逻辑：判断是否在收盘后
            current_hour = datetime.now().hour
            is_after_market_close = current_hour >= 15
            
            for trade_date in trading_days:
                # 跳过未来日期
                if trade_date > today:
                    continue
                
                # 🔴 T+1 逻辑：今天的处理
                if trade_date == today:
                    if not is_after_market_close:
                        # 交易时段内（9:30-15:00），跳过今天
                        logger.debug(f"跳过今天{trade_date}：当前在交易时段")
                        skipped_count += 1
                        continue
                    else:
                        # 收盘后，可以处理今天的交易
                        logger.info(f"✅ 处理今天{trade_date}：已收盘")

                # 执行观测
                r = self._run_daily_observation(strategy_id, trade_date)
                if r["success"]:
                    result["synced"] += 1
                    processed_count += 1
                elif r.get("skip_reason") == "kline_not_ready":
                    # 🆕 K线数据未准备好，跳过但不计入错误
                    skipped_count += 1
                    logger.info(f"⏭️ 跳过{trade_date}：K线数据未准备好")
                    # 添加到结果中，让前端知道跳过原因
                    if "skipped_dates" not in result:
                        result["skipped_dates"] = []
                    result["skipped_dates"].append({
                        "date": trade_date,
                        "reason": "K线数据未准备好"
                    })
                else:
                    result["errors"].append(f"{trade_date}: {r.get('error')}")
                    logger.info(f"策略{strategy_id} 同步完成: {result['synced']}天")

            print(f"[DEBUG] 策略{strategy_id}同步完成: 处理{processed_count}天, 跳过{skipped_count}天, 错误{len(result['errors'])}个")
            logger.info(f"策略{strategy_id}同步完成: {result['synced']}天，错误: {len(result['errors'])}")
            
            # 🔴 自动记录明日推荐到数据库
            if processed_count > 0:
                try:
                    from services.recommendation_service import record_recommendation
                    rec_result = record_recommendation(strategy_id)
                    if rec_result.get("success"):
                        result["recommendation_saved"] = True
                        result["recommendation_data"] = rec_result.get("data")
                        logger.info(f"✅ 策略{strategy_id}推荐已记录: {rec_result.get('message')}")
                    else:
                        result["recommendation_saved"] = False
                        logger.warning(f"⚠️ 记录推荐失败: {rec_result.get('message')}")
                except Exception as rec_e:
                    logger.error(f"记录推荐异常: {rec_e}")
                    result["recommendation_error"] = str(rec_e)
            
            return result

        except Exception as e:
            result["errors"].append(str(e))
            logger.error(f"同步策略失败: {e}")
            return result

    def sync_all_strategies(self) -> Dict:
        """同步所有策略"""
        result = {
            "total": 0,
            "synced": 0,
            "errors": []
        }

        strategies = DailyObserverStrategy.query.filter_by(status="active").all()
        result["total"] = len(strategies)

        for strategy in strategies:
            r = self.sync_strategy(strategy.id)
            result["synced"] += r["synced"]
            result["errors"].extend(r["errors"])

        return result

    def fill_missing_data(self) -> Dict:
        """补齐缺失数据"""
        result = {
            "checked": 0,
            "filled": 0,
            "errors": []
        }

        try:
            strategies = DailyObserverStrategy.query.filter_by(status="active").all()

            for strategy in strategies:
                # 确定起始日期
                start_date = "20250901"  # 从2025年9月开始

                # 获取交易日列表
                trading_days = self._get_trading_days(start_date, datetime.now().strftime("%Y%m%d"))

                # 执行每个交易日
                for trade_date in trading_days:
                    # 跳过今天
                    today = datetime.now().strftime("%Y%m%d")
                    if trade_date == today:
                        continue

                    # 跳过没有足够因子数据的日期
                    if not self._has_factor_data(
                        self._get_stock_pool(strategy), trade_date):
                        logger.debug(f"跳过{trade_date}：因子数据不足")
                        continue

                    # 检查是否已处理
                    existing = DailyObserverRecord.query.filter_by(
                        strategy_id=strategy.id,
                        date=trade_date
                    ).first()

                    if existing:
                        continue

                    # 执行观测
                    r = self._run_daily_observation(strategy.id, trade_date)
                    if r["success"]:
                        result["filled"] += 1

        except Exception as e:
            result["errors"].append(str(e))
            logger.error(f"补齐失败: {e}")

        result["checked"] = len(trading_days)
        logger.info(f"补齐完成: 检查{result['checked']}天，补齐{result['filled']}天")

        return result


# 创建单例实例
try:
    daily_observer_service = DailyObserverService()
except (ValueError, Exception) as e:
    logger.warning(f"每日观测服务初始化失败: {e}")
    daily_observer_service = None

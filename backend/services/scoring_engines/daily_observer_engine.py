"""
每日观测引擎 - 专门用于每日观测系统
=====================================
核心逻辑：
1. 使用 decide_daily_trades 方法进行买卖决策
2. 参数化控制所有交易行为
3. 可被 v2_adaptive 等引擎复用

适用场景：
- 每日观测系统
- 简单的参数化策略
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from services.scoring_engines.base_engine import BaseEngine


class DailyObserverEngine(BaseEngine):
    """每日观测引擎 - 参数化买卖决策"""

    ENGINE_ID = "daily_observer"
    ENGINE_NAME = "每日观测引擎"
    ENGINE_DESC = "参数化买卖决策，专用于每日观测系统"
    ENGINE_VERSION = "1.0"

    def __init__(self):
        super().__init__()
        self._sell_history = {}  # {ts_code: sell_date}

    # ==================================================================
    # 主循环
    # ==================================================================
    def run_backtest(
        self,
        factor_combo_id: int,
        stocks: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float,
        commission: float,
        slippage: float,
        backtest_params: Dict[str, Any],
    ) -> Dict:
        """
        执行参数化回测
        """
        # 初始化
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.trades = []
        self.positions = {}
        self._sell_history = {}

        # 获取因子配置
        factors = self._get_factor_config(factor_combo_id)

        # 提取回测参数
        max_positions = backtest_params.get("max_positions", 7)
        take_profit_ratio = backtest_params.get("take_profit_ratio", 0.15)
        stop_loss_ratio = backtest_params.get("stop_loss_ratio", -0.08)
        top_n = backtest_params.get("top_n", 15)
        sell_rank_out = backtest_params.get("sell_rank_out", 50)
        signal_confirm_days = backtest_params.get("signal_confirm_days", 1)
        blacklist_cooldown = backtest_params.get("blacklist_cooldown", 30)

        trading_days = self._get_trading_days(start_date, end_date)
        equity_curve = []

        for day in trading_days:
            stock_scores = self._calculate_daily_scores(stocks, day, factors)

            if not stock_scores:
                # 无数据时估值
                total_value = self._calculate_total_value(day)
                equity_curve.append({
                    "date": day, "value": total_value,
                    "cash": self.cash, "position_value": total_value - self.cash
                })
                continue

            # 构建持仓字典
            holdings_dict = {}
            for ts_code, pos in self.positions.items():
                holdings_dict[ts_code] = {
                    "buy_price": pos["cost"],
                    "buy_date": pos["buy_date"],
                    "volume": pos["volume"],
                    "score": pos.get("score_history", [0])[-1] if pos.get("score_history") else 0,
                    "rank": stock_scores.get(ts_code, {}).get("rank", 999)
                }

            # 策略参数
            strategy_params = {
                "max_positions": max_positions,
                "take_profit_ratio": take_profit_ratio,
                "stop_loss_ratio": stop_loss_ratio,
                "top_n": top_n,
                "sell_rank_out": sell_rank_out,
                "signal_confirm_days": signal_confirm_days,
                "blacklist_cooldown": blacklist_cooldown
            }

            # 使用 decide_daily_trades 决策
            decisions = self.decide_daily_trades(
                holdings=holdings_dict,
                stock_scores=stock_scores,
                strategy_params=strategy_params,
                trade_date=day
            )

            # 执行卖出
            for sell_signal in decisions["sell"]:
                ts_code = sell_signal["ts_code"]
                price = sell_signal["price"]
                self._sell_stock(day, ts_code, price, sell_signal["reason"], commission, slippage)

            # 执行买入
            if decisions["buy"]:
                buy_budget = self.cash / max(1, max_positions - len(self.positions))
                for buy_signal in decisions["buy"]:
                    ts_code = buy_signal["ts_code"]
                    price = buy_signal["price"]
                    self._buy_stock(
                        day, ts_code, price, buy_budget,
                        buy_signal["rank"], buy_signal["score"],
                        commission, slippage
                    )

            # 权益
            total_value = self._calculate_total_value(day)
            equity_curve.append({
                "date": day, "value": total_value,
                "cash": self.cash, "position_value": total_value - self.cash
            })

        statistics = self._calculate_statistics(equity_curve)
        return {
            "statistics": statistics,
            "equity_curve": equity_curve,
            "trades": self.trades,
            "positions": self.positions
        }

    # ==================================================================
    # 参数定义（供前端使用）
    # ==================================================================
    @staticmethod
    def get_params_schema() -> Dict:
        """
        返回参数配置schema，供前端动态生成表单
        """
        return {
            "max_positions": {
                "type": "number",
                "label": "最大持仓数",
                "default": 7,
                "min": 1,
                "max": 20,
                "step": 1,
                "description": "同时持有的最大股票数量"
            },
            "take_profit_ratio": {
                "type": "number",
                "label": "止盈比例",
                "default": 0.15,
                "min": 0.05,
                "max": 0.5,
                "step": 0.01,
                "description": "盈利达到此比例时止盈卖出（如0.15=15%）"
            },
            "stop_loss_ratio": {
                "type": "number",
                "label": "止损比例",
                "default": -0.08,
                "min": -0.2,
                "max": -0.02,
                "step": 0.01,
                "description": "亏损达到此比例时止损卖出（如-0.08=-8%）"
            },
            "top_n": {
                "type": "number",
                "label": "选股数量",
                "default": 15,
                "min": 5,
                "max": 50,
                "step": 1,
                "description": "从得分排名前N名中选择股票"
            },
            "sell_rank_out": {
                "type": "number",
                "label": "排名下降阈值",
                "default": 50,
                "min": 10,
                "max": 100,
                "step": 5,
                "description": "排名下降到此数值以下时考虑卖出"
            },
            "signal_confirm_days": {
                "type": "number",
                "label": "信号确认天数",
                "default": 1,
                "min": 1,
                "max": 5,
                "step": 1,
                "description": "连续N天排名靠前才买入（降低交易频率）"
            },
            "blacklist_cooldown": {
                "type": "number",
                "label": "冷却期天数",
                "default": 30,
                "min": 0,
                "max": 90,
                "step": 5,
                "description": "卖出后N天内不再买入同一股票（0=不限制）"
            }
        }

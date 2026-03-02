"""
打分驱动回测引擎 v1 - 动量+均值回归策略
=========================================
基于任务44-52复盘分析的策略，包含：
  1. 移动止损（trailing stop）- 保护已有利润
  2. 大盘趋势过滤器 - 弱势市场减仓/暂停买入
  3. 长期亏损退出优化 - 结合得分趋势判断
  4. 个股黑名单机制 - 连续亏损股票暂停买入
  5. 信号持续性确认 - 买入时机精细化

适用因子组合：强势动量精选(#5) 或 均值回归增强v2(#8)
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from services.scoring_engines.base_engine import BaseEngine


class V1MomentumEngine(BaseEngine):
    """v1 动量+均值回归策略引擎"""

    ENGINE_ID = "v1_momentum"
    ENGINE_NAME = "v1 动量均值回归"
    ENGINE_DESC = "移动止损 + 大盘趋势过滤 + 黑名单 + 信号确认（基线版本）"
    ENGINE_VERSION = "1.0"

    def __init__(self):
        super().__init__()
        self.blacklist = {}                        # {ts_code: cooldown_until_date}
        self.stock_loss_count = defaultdict(int)   # {ts_code: 连续亏损次数}
        self.prev_day_scores = {}                  # 前一天的得分
        self.market_trend = 1.0                    # 大盘趋势系数 0~1

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
        """执行打分驱动回测"""
        # 初始化
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.trades = []
        self.positions = {}
        self.blacklist = {}
        self.stock_loss_count = defaultdict(int)
        self.prev_day_scores = {}
        self.market_trend = 1.0

        # 获取因子配置
        factors = self._get_factor_config(factor_combo_id)

        # 提取回测参数
        top_n = backtest_params.get("top_n", 5)
        sell_rank_out = backtest_params.get("sell_rank_out", 50)
        take_profit_ratio = backtest_params.get("take_profit_ratio", 0.25)
        stop_loss_ratio = backtest_params.get("stop_loss_ratio", -0.06)
        max_positions = backtest_params.get("max_positions", 5)
        trailing_stop_ratio = backtest_params.get("trailing_stop_ratio", 0.10)
        signal_confirm_days = backtest_params.get("signal_confirm_days", 2)
        blacklist_cooldown = backtest_params.get("blacklist_cooldown", 30)

        trading_days = self._get_trading_days(start_date, end_date)
        equity_curve = []

        for i, day in enumerate(trading_days):
            stock_scores = self._calculate_daily_scores(stocks, day, factors)

            if not stock_scores:
                # 节假日：用 last_price 估值，避免假回撤
                total_value = self._calculate_total_value(day)
                equity_curve.append({
                    "date": day, "value": total_value,
                    "cash": self.cash, "position_value": total_value - self.cash
                })
                continue

            # 1. 大盘趋势
            self._update_market_trend(equity_curve)

            # 2. 更新持仓最高价
            self._update_position_peaks(stock_scores)

            # 3. 卖出
            self._process_sell_signals(
                day, stock_scores, sell_rank_out,
                take_profit_ratio, stop_loss_ratio,
                trailing_stop_ratio, blacklist_cooldown,
                commission, slippage
            )

            # 4. 买入
            self._process_buy_signals(
                day, stock_scores, top_n, max_positions,
                signal_confirm_days, commission, slippage
            )

            # 5. 保存当天得分
            self.prev_day_scores = {
                ts_code: data["score"] for ts_code, data in stock_scores.items()
            }

            # 6. 权益
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
    # 大盘趋势过滤器
    # ==================================================================
    def _update_market_trend(self, equity_curve: List[Dict]):
        """用账户权益曲线的短期趋势判断大盘状况"""
        if len(equity_curve) < 20:
            self.market_trend = 1.0
            return
        recent = equity_curve[-20:]
        start_val = recent[0]["value"]
        end_val = recent[-1]["value"]
        if start_val <= 0:
            self.market_trend = 1.0
            return
        change = (end_val - start_val) / start_val
        if change < -0.10:
            self.market_trend = 0.3
        elif change < -0.05:
            self.market_trend = 0.6
        elif change < 0:
            self.market_trend = 0.8
        else:
            self.market_trend = 1.0

    # ==================================================================
    # 更新持仓最高价
    # ==================================================================
    def _update_position_peaks(self, stock_scores: Dict[str, Dict]):
        """更新每个持仓的历史最高价和最后已知价格"""
        for ts_code, position in self.positions.items():
            current_price = stock_scores.get(ts_code, {}).get("price")
            if current_price:
                position["last_price"] = current_price
                if current_price > position.get("max_price", position["cost"]):
                    position["max_price"] = current_price

    # ==================================================================
    # 卖出逻辑
    # ==================================================================
    def _process_sell_signals(
        self, trade_date: str, stock_scores: Dict,
        sell_rank_out: int, take_profit_ratio: float,
        stop_loss_ratio: float, trailing_stop_ratio: float,
        blacklist_cooldown: int, commission: float, slippage: float
    ):
        """卖出信号处理：强制止损 > 移动止损 > 止盈 > 得分恶化 > 长期亏损"""
        sell_list = []

        for ts_code, pos in self.positions.items():
            current_price = stock_scores.get(ts_code, {}).get("price")
            if not current_price:
                continue

            current_rank = stock_scores.get(ts_code, {}).get("rank", 999)
            current_score = stock_scores.get(ts_code, {}).get("score", -999)
            profit_ratio = (current_price - pos["cost"]) / pos["cost"]
            holding_days = pos.get("holding_days", 0) + 1
            pos["holding_days"] = holding_days

            score_history = pos.get("score_history", [])
            score_history.append(current_score)
            if len(score_history) > 10:
                score_history = score_history[-10:]
            pos["score_history"] = score_history

            sell_reason = None

            # 1. 强制止损
            if profit_ratio <= stop_loss_ratio:
                sell_reason = f"止损{profit_ratio:.2%}"

            # 2. 移动止损（持仓>=5天且曾盈利过）
            elif holding_days >= 5:
                max_price = pos.get("max_price", pos["cost"])
                if max_price > pos["cost"]:
                    drawdown_from_peak = (max_price - current_price) / max_price
                    if drawdown_from_peak >= trailing_stop_ratio:
                        locked_profit = (max_price - pos["cost"]) / pos["cost"]
                        sell_reason = f"移动止损(峰值回撤{drawdown_from_peak:.2%},曾盈利{locked_profit:.2%})"

            # 3. 止盈（持仓>=5天）
            elif profit_ratio >= take_profit_ratio and holding_days >= 5:
                sell_reason = f"止盈{profit_ratio:.2%}"

            # 4. 得分持续恶化
            if sell_reason is None and holding_days >= 5:
                if len(score_history) >= 5:
                    recent_avg = sum(score_history[-3:]) / 3
                    earlier_avg = sum(score_history[:3]) / 3
                    score_declining = recent_avg < earlier_avg * 0.5
                    if current_rank > sell_rank_out and score_declining and current_score < 0:
                        sell_reason = f"得分恶化(rank={current_rank},score={current_score:.2f})"

            # 5. 长期亏损
            if sell_reason is None and holding_days > 20 and profit_ratio < -0.05:
                if len(score_history) >= 5:
                    recent_avg = sum(score_history[-3:]) / 3
                    if recent_avg <= 0:
                        sell_reason = f"长期亏损且得分转负({holding_days}天,{profit_ratio:.2%})"
                else:
                    sell_reason = f"长期亏损({holding_days}天,{profit_ratio:.2%})"

            if sell_reason:
                sell_list.append((ts_code, sell_reason, profit_ratio))

        for ts_code, reason, profit_ratio in sell_list:
            price = stock_scores[ts_code]["price"]
            self._sell_stock(trade_date, ts_code, price, reason, commission, slippage)

            # 更新黑名单
            if profit_ratio < 0:
                self.stock_loss_count[ts_code] += 1
                if self.stock_loss_count[ts_code] >= 2:
                    cooldown_date = datetime.strptime(trade_date, "%Y%m%d") + timedelta(days=blacklist_cooldown)
                    self.blacklist[ts_code] = cooldown_date.strftime("%Y%m%d")
            else:
                self.stock_loss_count[ts_code] = 0

    # ==================================================================
    # 买入逻辑
    # ==================================================================
    def _process_buy_signals(
        self, trade_date: str, stock_scores: Dict,
        top_n: int, max_positions: int,
        signal_confirm_days: int, commission: float, slippage: float
    ):
        """买入信号处理：大盘过滤、黑名单、信号持续性确认"""
        current_positions = len(self.positions)
        if current_positions >= max_positions:
            return

        if self.market_trend < 0.5:
            return

        sorted_stocks = sorted(
            stock_scores.items(), key=lambda x: x[1]["score"], reverse=True
        )

        buy_candidates = []
        for ts_code, data in sorted_stocks[:top_n * 2]:
            if ts_code in self.positions:
                continue

            # 黑名单检查
            if ts_code in self.blacklist:
                if trade_date < self.blacklist[ts_code]:
                    continue
                else:
                    del self.blacklist[ts_code]

            if data["score"] <= 0.5 or data["rank"] > top_n:
                continue

            # 信号持续性确认
            prev_score = self.prev_day_scores.get(ts_code, 0)
            if signal_confirm_days >= 2 and prev_score <= 0:
                continue

            buy_candidates.append((ts_code, data))
            if len(buy_candidates) >= max_positions - current_positions:
                break

        can_buy = min(len(buy_candidates), max_positions - current_positions)
        if can_buy == 0:
            return

        available_cash = self.cash * self.market_trend

        # 动态仓位分配
        total_score = sum(d["score"] for _, d in buy_candidates[:can_buy])
        allocations = []
        if total_score <= 0:
            per_stock = available_cash / can_buy
            allocations = [(ts, d, per_stock) for ts, d in buy_candidates[:can_buy]]
        else:
            for ts_code, data in buy_candidates[:can_buy]:
                w = data["score"] / total_score
                w = max(0.1, min(0.4, w))
                allocations.append((ts_code, data, available_cash * w))
            total_alloc = sum(c for _, _, c in allocations)
            if total_alloc > available_cash:
                allocations = [
                    (ts, d, c * available_cash / total_alloc) for ts, d, c in allocations
                ]

        for ts_code, data, cash_amount in allocations:
            self._buy_stock(
                trade_date, ts_code, data["price"],
                cash_amount, data["rank"], data["score"],
                commission, slippage
            )

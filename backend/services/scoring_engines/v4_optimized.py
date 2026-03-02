"""
优化自适应策略引擎 v4 - 稳健版
=====================================
v4优化：在v2基础上改进
1. 保持±5%阈值（v3的±3%太敏感）
2. 加入成交量确认
3. 根据市场状态调整仓位
4. 移除延迟确认（会错失机会）

核心思路：v2表现很好，只���微调而非大改
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
import json
from services.scoring_engines.base_engine import BaseEngine


class OptimizedAdaptiveEngine(BaseEngine):
    """v4 优化自适应策略引擎"""

    ENGINE_ID = "v4_optimized"
    ENGINE_NAME = "v4 优化自适应"
    ENGINE_DESC = "v2基础+成交量确认+智能仓位（稳健平衡版）"
    ENGINE_VERSION = "4.0"

    def __init__(self, bull_combo_id=18, bear_combo_id=19, range_combo_id=20):
        super().__init__()
        self.bull_combo_id = bull_combo_id
        self.bear_combo_id = bear_combo_id
        self.range_combo_id = range_combo_id
        self.market_state_history = {}
        self._factor_configs = {}

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
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.trades = []
        self.positions = {}
        self.blacklist = {}
        self.stock_loss_count = defaultdict(int)
        self.prev_day_scores = {}
        self.market_trend = 1.0

        self._load_factor_configs()

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
            market_state = self._detect_market_state(day)
            self.market_state_history[day] = market_state

            if market_state == "bull":
                factors = self._factor_configs["bull"]
                state_label = "🐂牛市"
            elif market_state == "bear":
                factors = self._factor_configs["bear"]
                state_label = "🐻熊市"
            else:
                factors = self._factor_configs["range"]
                state_label = "📊震荡"

            stock_scores = self._calculate_daily_scores(stocks, day, factors)

            if not stock_scores:
                total_value = self._calculate_total_value(day)
                equity_curve.append({
                    "date": day, "value": total_value,
                    "cash": self.cash, "position_value": total_value - self.cash,
                    "market_state": market_state
                })
                continue

            if i % 20 == 0:
                print(f"[{day}] {state_label} - 使用{len(factors)}个因子")

            self._update_market_trend(equity_curve)
            self._update_position_peaks(stock_scores)

            self._process_sell_signals(
                day, stock_scores, sell_rank_out,
                take_profit_ratio, stop_loss_ratio,
                trailing_stop_ratio, blacklist_cooldown,
                commission, slippage
            )

            # v4：根据状态调整仓位
            position_multiplier = self._get_position_multiplier(market_state)
            adjusted_max_positions = max(1, int(max_positions * position_multiplier))

            self._process_buy_signals(
                day, stock_scores, top_n, adjusted_max_positions,
                signal_confirm_days, commission, slippage
            )

            self.prev_day_scores = {
                ts_code: data["score"] for ts_code, data in stock_scores.items()
            }

            total_value = self._calculate_total_value(day)
            equity_curve.append({
                "date": day, "value": total_value,
                "cash": self.cash, "position_value": total_value - self.cash,
                "market_state": market_state
            })

        state_stats = self._calculate_state_stats()
        statistics = self._calculate_statistics(equity_curve)
        statistics["market_state_stats"] = state_stats

        return {
            "statistics": statistics,
            "equity_curve": equity_curve,
            "trades": self.trades,
            "positions": self.positions
        }

    def _detect_market_state(self, trade_date: str) -> str:
        """
        v4：保持±5%阈值（和v2一致）+ 成交量确认
        """
        from models.bar_data import BarData

        current_bars = BarData.query.filter(
            BarData.trade_date == trade_date
        ).all()

        if not current_bars or len(current_bars) < 10:
            return "range"

        current_avg = sum(float(b.close) for b in current_bars) / len(current_bars)
        current_volume = sum(float(b.vol) for b in current_bars if b.vol)

        current_dt = datetime.strptime(trade_date, "%Y%m%d")
        target_dt = current_dt - timedelta(days=60)
        target_date = target_dt.strftime("%Y%m%d")

        past_bars = BarData.query.filter(
            BarData.trade_date <= target_date,
            BarData.trade_date > (target_dt - timedelta(days=30)).strftime("%Y%m%d")
        ).all()

        if not past_bars or len(past_bars) < 10:
            return "range"

        past_by_date = {}
        for b in past_bars:
            if b.trade_date not in past_by_date:
                past_by_date[b.trade_date] = {'prices': [], 'volumes': []}
            past_by_date[b.trade_date]['prices'].append(float(b.close))
            if b.vol:
                past_by_date[b.trade_date]['volumes'].append(float(b.vol))

        if not past_by_date:
            return "range"

        latest_past_date = max(past_by_date.keys())
        past_avg = sum(past_by_date[latest_past_date]['prices']) / len(past_by_date[latest_past_date]['prices'])
        past_volume = sum(past_by_date[latest_past_date]['volumes']) if past_by_date[latest_past_date]['volumes'] else 0

        return_60d = (current_avg - past_avg) / past_avg if past_avg > 0 else 0

        # v4：成交量确认（80%阈值）
        volume_confirm = True
        if past_volume > 0 and current_volume > 0:
            volume_ratio = current_volume / past_volume
            volume_confirm = volume_ratio > 0.8

        # v4：保持±5%阈值（和v2一致）
        if return_60d > 0.05 and volume_confirm:
            return "bull"
        elif return_60d < -0.05 and volume_confirm:
            return "bear"
        else:
            return "range"

    def _get_position_multiplier(self, state: str) -> float:
        """根据市场状态调整仓位系数"""
        multipliers = {
            "bull": 1.0,    # 牛市满仓
            "range": 0.8,   # 震荡80%仓位
            "bear": 0.6     # 熊市60%仓位
        }
        return multipliers.get(state, 0.8)

    def _load_factor_configs(self):
        from models.factor_combo import FactorCombo

        bull_combo = FactorCombo.query.get(self.bull_combo_id)
        if bull_combo:
            self._factor_configs["bull"] = json.loads(bull_combo.factor_config).get("factors", [])

        bear_combo = FactorCombo.query.get(self.bear_combo_id)
        if bear_combo:
            self._factor_configs["bear"] = json.loads(bear_combo.factor_config).get("factors", [])

        range_combo = FactorCombo.query.get(self.range_combo_id)
        if range_combo:
            self._factor_configs["range"] = json.loads(range_combo.factor_config).get("factors", [])

        print(f"✅ v4引擎加载配置：牛市{len(self._factor_configs['bull'])}因子, "
              f"熊市{len(self._factor_configs['bear'])}因子, "
              f"震荡{len(self._factor_configs['range'])}因子")

    def _calculate_state_stats(self) -> Dict:
        stats = {
            "bull_days": 0,
            "bear_days": 0,
            "range_days": 0,
            "total_days": len(self.market_state_history)
        }

        for state in self.market_state_history.values():
            if state == "bull":
                stats["bull_days"] += 1
            elif state == "bear":
                stats["bear_days"] += 1
            else:
                stats["range_days"] += 1

        if stats["total_days"] > 0:
            stats["bull_ratio"] = stats["bull_days"] / stats["total_days"]
            stats["bear_ratio"] = stats["bear_days"] / stats["total_days"]
            stats["range_ratio"] = stats["range_days"] / stats["total_days"]

        return stats

    def _update_market_trend(self, equity_curve: List[Dict]):
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

    def _update_position_peaks(self, stock_scores: Dict[str, Dict]):
        for ts_code, position in self.positions.items():
            current_price = stock_scores.get(ts_code, {}).get("price")
            if current_price:
                position["last_price"] = current_price
                if current_price > position.get("max_price", position["cost"]):
                    position["max_price"] = current_price

    def _process_sell_signals(
        self, trade_date: str, stock_scores: Dict,
        sell_rank_out: int, take_profit_ratio: float,
        stop_loss_ratio: float, trailing_stop_ratio: float,
        blacklist_cooldown: int, commission: float, slippage: float
    ):
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

            if profit_ratio <= stop_loss_ratio:
                sell_reason = f"止损{profit_ratio:.2%}"
            elif holding_days >= 5:
                max_price = pos.get("max_price", pos["cost"])
                if max_price > pos["cost"]:
                    drawdown_from_peak = (max_price - current_price) / max_price
                    if drawdown_from_peak >= trailing_stop_ratio:
                        locked_profit = (max_price - pos["cost"]) / pos["cost"]
                        sell_reason = f"移动止损(峰值回撤{drawdown_from_peak:.2%},曾盈利{locked_profit:.2%})"
            elif profit_ratio >= take_profit_ratio and holding_days >= 5:
                sell_reason = f"止盈{profit_ratio:.2%}"
            if sell_reason is None and holding_days >= 5:
                if len(score_history) >= 5:
                    recent_avg = sum(score_history[-3:]) / 3
                    earlier_avg = sum(score_history[:3]) / 3
                    score_declining = recent_avg < earlier_avg * 0.5
                    if current_rank > sell_rank_out and score_declining and current_score < 0:
                        sell_reason = f"得分恶化(rank={current_rank},score={current_score:.2f})"
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

            if profit_ratio < 0:
                self.stock_loss_count[ts_code] += 1
                if self.stock_loss_count[ts_code] >= 2:
                    cooldown_date = datetime.strptime(trade_date, "%Y%m%d") + timedelta(days=blacklist_cooldown)
                    self.blacklist[ts_code] = cooldown_date.strftime("%Y%m%d")
            else:
                self.stock_loss_count[ts_code] = 0

    def _process_buy_signals(
        self, trade_date: str, stock_scores: Dict,
        top_n: int, max_positions: int,
        signal_confirm_days: int, commission: float, slippage: float
    ):
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

            if ts_code in self.blacklist:
                if trade_date < self.blacklist[ts_code]:
                    continue
                else:
                    del self.blacklist[ts_code]

            if data["score"] <= 0.5 or data["rank"] > top_n:
                continue

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

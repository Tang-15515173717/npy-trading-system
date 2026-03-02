"""
自适应策略引擎 v2 - 根据市场状态动态切换因子组合
======================================================
核心逻辑：
1. 每个交易日判断市场状态（基于上证指数60日涨跌）
2. 根据市场状态自动选择对应的因子组合：
   - 牛市（指数60日>+5%）：使用牛市组合（高动量追涨）
   - 震荡（指数60日±5%）：使用震荡组合（均值回归）
   - 熊市（指数60日<-5%）：使用熊市组合（超跌反弹+做空）
3. 动态切换因子组合进行打分和交易

适用场景：跨越牛熊震荡的全周期投资
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
import json
from services.scoring_engines.base_engine import BaseEngine


class AdaptiveEngine(BaseEngine):
    """v2 自适应策略引擎 - 市场状态感知"""

    ENGINE_ID = "v2_adaptive"
    ENGINE_NAME = "v2 自适应策略"
    ENGINE_DESC = "根据市场状态自动切换因子组合：牛市追涨、震荡反转、熊市防御"
    ENGINE_VERSION = "2.0"

    def __init__(self, bull_combo_id=18, bear_combo_id=19, range_combo_id=20):
        super().__init__()
        # 三个市场状态对应的因子组合ID
        self.bull_combo_id = bull_combo_id  # 牛市组合
        self.bear_combo_id = bear_combo_id  # 熊市组合
        self.range_combo_id = range_combo_id  # 震荡组合

        # 市场状态历史
        self.market_state_history = {}  # {date: state}

        # 缓存因子配置（避免重复查询）
        self._factor_configs = {}

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
        执行自适应回测

        注意：factor_combo_id参数被忽略，使用内部配置的三个组合
        """
        # 初始化
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.trades = []
        self.positions = {}
        self.blacklist = {}
        self.stock_loss_count = defaultdict(int)
        self.prev_day_scores = {}
        self.market_trend = 1.0

        # 预加载三个因子组合配置
        self._load_factor_configs()

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
            # 🔥 核心：判断市场状态并选择因子组合
            market_state = self._detect_market_state(day)
            self.market_state_history[day] = market_state

            # 根据市场状态选择因子组合
            if market_state == "bull":
                factors = self._factor_configs["bull"]
                state_label = "🐂牛市"
            elif market_state == "bear":
                factors = self._factor_configs["bear"]
                state_label = "🐻熊市"
            else:  # range
                factors = self._factor_configs["range"]
                state_label = "📊震荡"

            # 使用选定因子计算得分
            stock_scores = self._calculate_daily_scores(stocks, day, factors)

            if not stock_scores:
                # 节假日：用 last_price 估值，避免假回撤
                total_value = self._calculate_total_value(day)
                equity_curve.append({
                    "date": day, "value": total_value,
                    "cash": self.cash, "position_value": total_value - self.cash,
                    "market_state": market_state
                })
                continue

            # 每20天打印一次市场状态
            if i % 20 == 0:
                print(f"[{day}] {state_label} - 使用{len(factors)}个因子")

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
                "cash": self.cash, "position_value": total_value - self.cash,
                "market_state": market_state
            })

        # 统计市场状态分布
        state_stats = self._calculate_state_stats()

        statistics = self._calculate_statistics(equity_curve)
        statistics["market_state_stats"] = state_stats

        return {
            "statistics": statistics,
            "equity_curve": equity_curve,
            "trades": self.trades,
            "positions": self.positions
        }

    # ==================================================================
    # 市场状态判断
    # ==================================================================
    def _detect_market_state(self, trade_date: str) -> str:
        """
        判断市场状态

        判断标准（基于等权市场指数60日涨跌）：
        - 牛市：市场指数60日涨幅 > 5%
        - 熊市：市场指数60日涨幅 < -5%
        - 震荡：其他情况

        Args:
            trade_date: 交易日期 YYYYMMDD

        Returns:
            "bull", "bear", 或 "range"
        """
        from models.bar_data import BarData

        # 计算当前日期的市场平均收盘价
        current_bars = BarData.query.filter(
            BarData.trade_date == trade_date
        ).all()

        if not current_bars or len(current_bars) < 10:
            return "range"  # 数据不足时默认震荡

        current_avg = sum(float(b.close) for b in current_bars) / len(current_bars)

        # 计算60个自然日前的日期
        current_dt = datetime.strptime(trade_date, "%Y%m%d")
        target_dt = current_dt - timedelta(days=60)
        target_date = target_dt.strftime("%Y%m%d")

        # 查找60天前最近的有数据的交易日
        past_bars = BarData.query.filter(
            BarData.trade_date <= target_date,
            BarData.trade_date > (target_dt - timedelta(days=30)).strftime("%Y%m%d")
        ).all()

        if not past_bars or len(past_bars) < 10:
            return "range"  # 无历史数据时默认震荡

        # 按日期分组计算平均价格
        past_by_date = {}
        for b in past_bars:
            if b.trade_date not in past_by_date:
                past_by_date[b.trade_date] = []
            past_by_date[b.trade_date].append(float(b.close))

        if not past_by_date:
            return "range"

        # 使用最近的有数据的日期
        latest_past_date = max(past_by_date.keys())
        past_avg = sum(past_by_date[latest_past_date]) / len(past_by_date[latest_past_date])

        # 计算60日涨跌幅
        return_60d = (current_avg - past_avg) / past_avg if past_avg > 0 else 0

        # 判断市场状态
        if return_60d > 0.05:  # 涨幅>5%
            return "bull"
        elif return_60d < -0.05:  # 跌幅>5%
            return "bear"
        else:
            return "range"

    # ==================================================================
    # 因子配置加载
    # ==================================================================
    def _load_factor_configs(self):
        """预加载三个市场状态的因子配置"""
        from models.factor_combo import FactorCombo

        # 牛市组合
        bull_combo = FactorCombo.query.get(self.bull_combo_id)
        if bull_combo:
            self._factor_configs["bull"] = json.loads(bull_combo.factor_config).get("factors", [])
        else:
            self._factor_configs["bull"] = []

        # 熊市组合
        bear_combo = FactorCombo.query.get(self.bear_combo_id)
        if bear_combo:
            self._factor_configs["bear"] = json.loads(bear_combo.factor_config).get("factors", [])
        else:
            self._factor_configs["bear"] = []

        # 震荡组合
        range_combo = FactorCombo.query.get(self.range_combo_id)
        if range_combo:
            self._factor_configs["range"] = json.loads(range_combo.factor_config).get("factors", [])
        else:
            self._factor_configs["range"] = []

        print(f"✅ 自适应引擎加载配置：牛市{len(self._factor_configs['bull'])}因子, "
              f"熊市{len(self._factor_configs['bear'])}因子, "
              f"震荡{len(self._factor_configs['range'])}因子")

    # ==================================================================
    # 市场状态统计
    # ==================================================================
    def _calculate_state_stats(self) -> Dict:
        """计算市场状态分布统计"""
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

    # ==================================================================
    # 继承基类的买卖逻辑
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

    def _update_position_peaks(self, stock_scores: Dict[str, Dict]):
        """更新每个持仓的历史最高价和最后已知价格"""
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
        """卖出信号处理"""
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

            # 2. 移动止损
            elif holding_days >= 5:
                max_price = pos.get("max_price", pos["cost"])
                if max_price > pos["cost"]:
                    drawdown_from_peak = (max_price - current_price) / max_price
                    if drawdown_from_peak >= trailing_stop_ratio:
                        locked_profit = (max_price - pos["cost"]) / pos["cost"]
                        sell_reason = f"移动止损(峰值回撤{drawdown_from_peak:.2%},曾盈利{locked_profit:.2%})"

            # 3. 止盈
            elif profit_ratio >= take_profit_ratio and holding_days >= 5:
                sell_reason = f"止盈{profit_ratio:.2%}"

            # 4. 得分恶化
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
        """买入信号处理"""
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

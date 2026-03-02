"""
打分驱动回测引擎 v3.0 - Scoring-Driven Backtest Engine
基于因子打分的日级回测系统

v3.0 优化内容（基于任务44-52复盘分析）：
  1. P0: 移动止损（trailing stop）- 保护已有利润
  2. P0: 大盘趋势过滤器 - 弱势市场减仓/暂停买入
  3. P1: 长期亏损退出优化 - 结合得分趋势判断
  4. P2: 个股黑名单机制 - 连续亏损股票暂停买入
  5. P2: 买入时机精细化 - 信号持续性确认 + 回调买入
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
from models.factor_combo import FactorCombo
from models.factor_data import FactorData
from models.bar_data import BarData
from utils.database import db
import json


class ScoringBacktestEngine:
    """打分驱动回测引擎 v3.0"""

    def __init__(self):
        self.trades = []
        self.positions = {}       # {ts_code: {volume, cost, buy_date, holding_days, max_price, prev_scores}}
        self.cash = 0
        self.initial_capital = 0
        self.blacklist = {}       # {ts_code: cooldown_until_date} 个股黑名单
        self.stock_loss_count = defaultdict(int)  # {ts_code: 连续亏损次数}
        self.prev_day_scores = {} # 前一天的得分，用于信号持续性判断
        self.market_trend = 1.0   # 大盘趋势系数 0~1

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
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

        # 获取因子组合配置
        factor_combo = FactorCombo.query.get(factor_combo_id)
        if not factor_combo:
            raise ValueError(f"因子组合ID {factor_combo_id} 不存在")

        factor_config = json.loads(factor_combo.factor_config)
        factors = factor_config.get("factors", [])
        if not factors:
            raise ValueError("因子组合没有配置因子")

        # 提取回测参数
        top_n = backtest_params.get("top_n", 5)
        sell_rank_out = backtest_params.get("sell_rank_out", 50)
        take_profit_ratio = backtest_params.get("take_profit_ratio", 0.25)
        stop_loss_ratio = backtest_params.get("stop_loss_ratio", -0.06)
        max_positions = backtest_params.get("max_positions", 5)
        # v3.0 新增参数
        trailing_stop_ratio = backtest_params.get("trailing_stop_ratio", 0.10)  # 移动止损：从最高点回撤10%
        signal_confirm_days = backtest_params.get("signal_confirm_days", 2)     # 信号确认天数
        blacklist_cooldown = backtest_params.get("blacklist_cooldown", 30)       # 黑名单冷却期(天)

        # 生成交易日列表
        trading_days = self._get_trading_days(start_date, end_date)

        # 权益曲线
        equity_curve = []

        # 逐日回测
        for i, day in enumerate(trading_days):
            # 0. 更新大盘趋势（用股票池整体涨跌判断）
            stock_scores = self._calculate_daily_scores(stocks, day, factors)

            if not stock_scores:
                # 节假日/无数据日：仍记录权益（用last_price估值，避免假回撤）
                total_value = self._calculate_total_value(day)
                equity_curve.append({
                    "date": day, "value": total_value,
                    "cash": self.cash, "position_value": total_value - self.cash
                })
                continue

            # 1. 更新大盘趋势系数
            self._update_market_trend(equity_curve)

            # 2. 更新持仓的最高价（用于移动止损）
            self._update_position_peaks(stock_scores)

            # 3. 卖出信号
            self._process_sell_signals(
                day, stock_scores, sell_rank_out,
                take_profit_ratio, stop_loss_ratio,
                trailing_stop_ratio, blacklist_cooldown,
                commission, slippage
            )

            # 4. 买入信号
            self._process_buy_signals(
                day, stock_scores, top_n, max_positions,
                signal_confirm_days, commission, slippage
            )

            # 5. 保存当天得分（用于明天的信号持续性判断）
            self.prev_day_scores = {
                ts_code: data["score"] for ts_code, data in stock_scores.items()
            }

            # 6. 记录当日权益
            total_value = self._calculate_total_value(day)
            equity_curve.append({
                "date": day, "value": total_value,
                "cash": self.cash, "position_value": total_value - self.cash
            })

            # 记录权益更新

        # 计算统计指标
        statistics = self._calculate_statistics(equity_curve)

        return {
            "statistics": statistics,
            "equity_curve": equity_curve,
            "trades": self.trades,
            "positions": self.positions
        }

    # ------------------------------------------------------------------
    # 辅助工具
    # ------------------------------------------------------------------
    def _get_trading_days(self, start_date: str, end_date: str) -> List[str]:
        """生成交易日列表（过滤周末）"""
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")
        days = []
        d = start
        while d <= end:
            if d.weekday() < 5:
                days.append(d.strftime("%Y%m%d"))
            d += timedelta(days=1)
        return days

    # ------------------------------------------------------------------
    # P0: 大盘趋势过滤器
    # ------------------------------------------------------------------
    def _update_market_trend(self, equity_curve: List[Dict]):
        """
        用账户权益曲线的短期趋势判断大盘状况
        如果近20天权益持续下跌，降低仓位系数
        """
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
            # 近20天跌超10%，大幅降低仓位
            self.market_trend = 0.3
        elif change < -0.05:
            # 近20天跌超5%，适度降低
            self.market_trend = 0.6
        elif change < 0:
            # 小幅下跌
            self.market_trend = 0.8
        else:
            # 上涨趋势
            self.market_trend = 1.0

    # ------------------------------------------------------------------
    # P0: 更新持仓最高价（用于移动止损）
    # ------------------------------------------------------------------
    def _update_position_peaks(self, stock_scores: Dict[str, Dict]):
        """更新每个持仓的历史最高价和最后已知价格"""
        for ts_code, position in self.positions.items():
            current_price = stock_scores.get(ts_code, {}).get("price")
            if current_price:
                position["last_price"] = current_price  # 同步更新最后已知价格
                if current_price > position.get("max_price", position["cost"]):
                    position["max_price"] = current_price

    # ------------------------------------------------------------------
    # 打分计算（v2.0: Z-score标准化 + 方向性处理）
    # ------------------------------------------------------------------
    def _calculate_daily_scores(
        self, stocks: List[str], trade_date: str, factors: List[Dict]
    ) -> Dict[str, Dict]:
        """计算当日股票打分"""
        factor_values_by_code = {}
        temp_data = {}

        # 第一轮：收集所有因子值
        for ts_code in stocks:
            factor_data = FactorData.query.filter_by(
                ts_code=ts_code, trade_date=trade_date
            ).first()
            if not factor_data:
                continue

            bar = BarData.query.filter_by(
                ts_code=ts_code, trade_date=trade_date
            ).first()
            if not bar:
                continue

            factor_values = {}
            for fc in factors:
                code = fc.get("factor_code")
                val = getattr(factor_data, code, None)
                if val is not None:
                    val = float(val)
                    factor_values[code] = val
                    factor_values_by_code.setdefault(code, []).append(val)

            if factor_values:
                temp_data[ts_code] = {
                    "factor_values": factor_values,
                    "price": float(bar.close)
                }

        # 第二轮：Z-score标准化 + 加权求和
        stock_scores = {}
        for ts_code, data in temp_data.items():
            total_score = 0
            normalized = {}

            for fc in factors:
                code = fc.get("factor_code")
                weight = fc.get("weight", 1.0)
                direction = fc.get("direction", "long")

                if code not in data["factor_values"]:
                    continue

                raw = data["factor_values"][code]
                vals = factor_values_by_code.get(code, [])

                if len(vals) > 1:
                    mean_v = sum(vals) / len(vals)
                    std_v = (sum((x - mean_v) ** 2 for x in vals) / len(vals)) ** 0.5
                    z = (raw - mean_v) / std_v if std_v > 0 else 0
                else:
                    z = 0

                if direction == "short":
                    z = -z

                normalized[code] = z
                total_score += z * weight

            stock_scores[ts_code] = {
                "score": total_score,
                "price": data["price"],
                "factor_values": normalized
            }

        # 计算排名
        sorted_list = sorted(stock_scores.items(), key=lambda x: x[1]["score"], reverse=True)
        for rank, (ts_code, _) in enumerate(sorted_list, 1):
            stock_scores[ts_code]["rank"] = rank

        return stock_scores

    # ------------------------------------------------------------------
    # 卖出逻辑 v3.0
    # ------------------------------------------------------------------
    def _process_sell_signals(
        self, trade_date: str, stock_scores: Dict,
        sell_rank_out: int, take_profit_ratio: float,
        stop_loss_ratio: float, trailing_stop_ratio: float,
        blacklist_cooldown: int, commission: float, slippage: float
    ):
        """
        卖出信号处理 v3.0
        优先级: 强制止损 > 移动止损 > 止盈 > 得分恶化 > 长期亏损
        """
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

            # 更新得分历史（用于趋势判断）
            score_history = pos.get("score_history", [])
            score_history.append(current_score)
            if len(score_history) > 10:
                score_history = score_history[-10:]
            pos["score_history"] = score_history

            sell_reason = None

            # ── 1. 强制止损（与 v3.0 一致） ──
            if profit_ratio <= stop_loss_ratio:
                sell_reason = f"止损{profit_ratio:.2%}"

            # ── 2. P0: 移动止损（持仓≥5天且曾盈利过） ──
            elif holding_days >= 5:
                max_price = pos.get("max_price", pos["cost"])
                if max_price > pos["cost"]:  # 曾经盈利过
                    drawdown_from_peak = (max_price - current_price) / max_price
                    if drawdown_from_peak >= trailing_stop_ratio:
                        locked_profit = (max_price - pos["cost"]) / pos["cost"]
                        sell_reason = f"移动止损(峰值回撤{drawdown_from_peak:.2%},曾盈利{locked_profit:.2%})"

            # ── 3. 止盈（持仓≥5天） ──
            elif profit_ratio >= take_profit_ratio and holding_days >= 5:
                sell_reason = f"止盈{profit_ratio:.2%}"

            # ── 4. P1: 得分持续恶化（结合趋势，代替简单的排名跌出） ──
            if sell_reason is None and holding_days >= 5:
                if len(score_history) >= 5:
                    recent_avg = sum(score_history[-3:]) / 3
                    earlier_avg = sum(score_history[:3]) / 3
                    score_declining = recent_avg < earlier_avg * 0.5  # 得分下降超50%

                    if current_rank > sell_rank_out and score_declining and current_score < 0:
                        sell_reason = f"得分恶化(rank={current_rank},score={current_score:.2f})"

            # ── 5. P1: 长期亏损优化（结合得分趋势而非简单天数+亏损） ──
            if sell_reason is None and holding_days > 20 and profit_ratio < -0.05:
                if len(score_history) >= 5:
                    recent_avg = sum(score_history[-3:]) / 3
                    # 如果得分还在上升，给更多耐心
                    if recent_avg <= 0:
                        sell_reason = f"长期亏损且得分转负({holding_days}天,{profit_ratio:.2%})"
                else:
                    # 得分历史不足，按原规则
                    sell_reason = f"长期亏损({holding_days}天,{profit_ratio:.2%})"

            if sell_reason:
                sell_list.append((ts_code, sell_reason, profit_ratio))

        # 执行卖出
        for ts_code, reason, profit_ratio in sell_list:
            price = stock_scores[ts_code]["price"]
            self._sell_stock(trade_date, ts_code, price, reason, commission, slippage)

            # P2: 更新个股黑名单
            if profit_ratio < 0:
                self.stock_loss_count[ts_code] += 1
                if self.stock_loss_count[ts_code] >= 2:
                    # 连续亏损2次，加入冷却期
                    cooldown_date = datetime.strptime(trade_date, "%Y%m%d") + timedelta(days=blacklist_cooldown)
                    self.blacklist[ts_code] = cooldown_date.strftime("%Y%m%d")
            else:
                # 盈利了，重置连续亏损计数
                self.stock_loss_count[ts_code] = 0

    # ------------------------------------------------------------------
    # 买入逻辑 v3.0
    # ------------------------------------------------------------------
    def _process_buy_signals(
        self, trade_date: str, stock_scores: Dict,
        top_n: int, max_positions: int,
        signal_confirm_days: int, commission: float, slippage: float
    ):
        """
        买入信号处理 v3.0
        增加：大盘过滤、黑名单、信号持续性确认
        """
        current_positions = len(self.positions)
        if current_positions >= max_positions:
            return

        # P0: 大盘弱势时不买入
        if self.market_trend < 0.5:
            return

        sorted_stocks = sorted(
            stock_scores.items(), key=lambda x: x[1]["score"], reverse=True
        )

        buy_candidates = []
        for ts_code, data in sorted_stocks[:top_n * 2]:  # 扫描更多候选，因为要过滤
            if ts_code in self.positions:
                continue

            # P2: 检查黑名单
            if ts_code in self.blacklist:
                if trade_date < self.blacklist[ts_code]:
                    continue
                else:
                    del self.blacklist[ts_code]  # 冷却期结束

            # 基本过滤：得分>0.5 且排名在前列
            if data["score"] <= 0.5 or data["rank"] > top_n:
                continue

            # P2: 信号持续性确认
            prev_score = self.prev_day_scores.get(ts_code, 0)
            if signal_confirm_days >= 2 and prev_score <= 0:
                # 前一天得分不是正的，跳过（需要连续信号确认）
                continue

            buy_candidates.append((ts_code, data))

            if len(buy_candidates) >= max_positions - current_positions:
                break

        can_buy = min(len(buy_candidates), max_positions - current_positions)
        if can_buy == 0:
            return

        # P0: 根据大盘趋势调整可用资金
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

            # 归一化
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

    # ------------------------------------------------------------------
    # 执行买卖
    # ------------------------------------------------------------------
    def _buy_stock(
        self, trade_date: str, ts_code: str, price: float,
        cash_amount: float, rank: int, score: float,
        commission: float, slippage: float
    ):
        """买入股票"""
        price = float(price)
        buy_price = price * (1 + slippage)

        volume = int(cash_amount / buy_price / 100) * 100
        if volume < 100:
            return

        cost = volume * buy_price
        fee = cost * commission
        total_cost = cost + fee

        if total_cost > self.cash:
            return

        self.positions[ts_code] = {
            "volume": volume,
            "cost": buy_price,
            "buy_date": trade_date,
            "holding_days": 0,
            "max_price": buy_price,      # P0: 初始化最高价（用于移动止损）
            "last_price": buy_price,     # 最后已知市场价（用于假期估值）
            "score_history": [score],     # P1: 初始化得分历史
        }

        self.cash -= total_cost

        self.trades.append({
            "date": trade_date,
            "symbol": ts_code,
            "direction": "buy",
            "price": buy_price,
            "volume": volume,
            "amount": cost,
            "commission": fee,
            "signal_reason": f"排名{rank},得分{score:.2f}"
        })

    def _sell_stock(
        self, trade_date: str, ts_code: str, price: float,
        reason: str, commission: float, slippage: float
    ):
        """卖出股票"""
        if ts_code not in self.positions:
            return

        pos = self.positions[ts_code]
        price = float(price)
        sell_price = price * (1 - slippage)

        volume = pos["volume"]
        revenue = volume * sell_price
        fee = revenue * commission
        net_revenue = revenue - fee

        self.cash += net_revenue
        del self.positions[ts_code]

        self.trades.append({
            "date": trade_date,
            "symbol": ts_code,
            "direction": "sell",
            "price": sell_price,
            "volume": volume,
            "amount": revenue,
            "commission": fee,
            "signal_reason": reason
        })

    # ------------------------------------------------------------------
    # 计算总资产
    # ------------------------------------------------------------------
    def _calculate_total_value(self, trade_date: str) -> float:
        """计算当前总资产（节假日用最后已知价格，避免假回撤）"""
        total = self.cash
        for ts_code, pos in self.positions.items():
            bar = BarData.query.filter_by(ts_code=ts_code, trade_date=trade_date).first()
            if bar:
                price = float(bar.close)
                pos["last_price"] = price  # 更新最后已知价格
            else:
                # 节假日/停牌：用最后已知价格，而非买入成本
                price = pos.get("last_price", pos["cost"])
            total += pos["volume"] * price
        return total

    # ------------------------------------------------------------------
    # 统计指标
    # ------------------------------------------------------------------
    def _calculate_statistics(self, equity_curve: List[Dict]) -> Dict:
        """计算统计指标"""
        if not equity_curve:
            return {}

        final_value = equity_curve[-1]["value"]
        total_return = (final_value - self.initial_capital) / self.initial_capital

        # 最大回撤
        max_drawdown = 0
        peak = equity_curve[0]["value"]
        for point in equity_curve:
            v = point["value"]
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak > 0 else 0
            if dd > max_drawdown:
                max_drawdown = dd

        # FIFO配对计算盈亏
        positions_fifo = defaultdict(list)
        completed = []
        for t in self.trades:
            if t["direction"] == "buy":
                positions_fifo[t["symbol"]].append(t)
            elif t["direction"] == "sell":
                if positions_fifo[t["symbol"]]:
                    buy_t = positions_fifo[t["symbol"]].pop(0)
                    pnl = t["amount"] - buy_t["amount"] - (t.get("commission", 0) + buy_t.get("commission", 0))
                    completed.append(pnl)

        winning_count = sum(1 for p in completed if p > 0)
        losing_count = sum(1 for p in completed if p < 0)
        total_completed = len(completed)
        win_rate = winning_count / total_completed if total_completed > 0 else 0

        total_win = sum(p for p in completed if p > 0)
        total_loss = abs(sum(p for p in completed if p < 0))
        avg_win = total_win / winning_count if winning_count > 0 else 0
        avg_loss = total_loss / losing_count if losing_count > 0 else 0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        profit_factor = total_win / total_loss if total_loss > 0 else 0

        # 年化收益率
        days = len(equity_curve)
        annual_return = ((1 + total_return) ** (252 / max(days, 1))) - 1 if days > 0 else 0

        # 夏普比率
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev_v = equity_curve[i - 1]["value"]
            curr_v = equity_curve[i]["value"]
            if prev_v > 0:
                daily_returns.append((curr_v - prev_v) / prev_v)

        if len(daily_returns) > 1:
            avg_d = sum(daily_returns) / len(daily_returns)
            std_d = (sum((r - avg_d) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
            sharpe = (avg_d / std_d) * (252 ** 0.5) if std_d > 0 else 0
        else:
            sharpe = 0

        return {
            "initial_capital": self.initial_capital,
            "final_value": final_value,
            "total_return": total_return * 100,
            "total_return_pct": f"{total_return * 100:.2f}%",
            "annual_return": annual_return * 100,
            "annual_return_pct": f"{annual_return * 100:.2f}%",
            "max_drawdown": max_drawdown * 100,
            "max_drawdown_pct": f"{max_drawdown * 100:.2f}%",
            "sharpe_ratio": round(sharpe, 2),
            "total_trades": len(self.trades),
            "winning_trades": winning_count,
            "losing_trades": losing_count,
            "win_rate": win_rate * 100,
            "win_rate_pct": f"{win_rate * 100:.2f}%",
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_loss_ratio": round(profit_loss_ratio, 2),
            "profit_factor": round(profit_factor, 2),
            "net_pnl": round(final_value - self.initial_capital, 2)
        }

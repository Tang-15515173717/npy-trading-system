"""
打分驱动回测引擎 - 基类
========================
所有版本的引擎都继承此基类。
基类提供公共工具方法（交易日生成、统计计算、买卖执行等），
子类只需实现具体的打分、买卖信号逻辑。
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
from models.factor_combo import FactorCombo
from models.factor_data import FactorData
from models.bar_data import BarData
from utils.database import db
import json


class BaseEngine:
    """打分驱动回测引擎基类 - 所有版本继承此类"""

    # 子类必须覆盖的元信息
    ENGINE_ID: str = "base"
    ENGINE_NAME: str = "基础引擎"
    ENGINE_DESC: str = "基类，不可直接使用"
    ENGINE_VERSION: str = "0.0"

    def __init__(self):
        self.trades = []
        self.positions = {}
        self.cash = 0
        self.initial_capital = 0

    # ==================================================================
    # 主入口（子类一般不需要覆盖）
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
        """执行打分驱动回测（子类可覆盖以自定义主循环）"""
        raise NotImplementedError("子类必须实现 run_backtest 方法")

    # ==================================================================
    # 公共工具方法（所有版本共用）
    # ==================================================================
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

    def _get_factor_config(self, factor_combo_id: int) -> List[Dict]:
        """获取因子组合配置"""
        factor_combo = FactorCombo.query.get(factor_combo_id)
        if not factor_combo:
            raise ValueError(f"因子组合ID {factor_combo_id} 不存在")
        factor_config = json.loads(factor_combo.factor_config)
        factors = factor_config.get("factors", [])
        if not factors:
            raise ValueError("因子组合没有配置因子")
        return factors

    def _calculate_daily_scores(
        self, stocks: List[str], trade_date: str, factors: List[Dict]
    ) -> Dict[str, Dict]:
        """计算当日股票��分（Z-score标准化 + 方向性处理）"""
        factor_values_by_code = {}
        temp_data = {}

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

        # Z-score标准��� + 加权求和
        stock_scores = {}
        for ts_code, data in temp_data.items():
            total_score = 0
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
                total_score += z * weight

            stock_scores[ts_code] = {
                "score": total_score,
                "price": data["price"],
            }

        # 排名
        sorted_list = sorted(stock_scores.items(), key=lambda x: x[1]["score"], reverse=True)
        for rank, (ts_code, _) in enumerate(sorted_list, 1):
            stock_scores[ts_code]["rank"] = rank

        return stock_scores

    def _calculate_total_value(self, trade_date: str) -> float:
        """计算当前总资产（节假日用最后已知价格，避免假回撤）"""
        total = self.cash
        for ts_code, pos in self.positions.items():
            bar = BarData.query.filter_by(ts_code=ts_code, trade_date=trade_date).first()
            if bar:
                price = float(bar.close)
                pos["last_price"] = price
            else:
                price = pos.get("last_price", pos["cost"])
            total += pos["volume"] * price
        return total

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
            "max_price": buy_price,
            "last_price": buy_price,
            "score_history": [score],
        }
        self.cash -= total_cost
        self.trades.append({
            "date": trade_date, "symbol": ts_code, "direction": "buy",
            "price": buy_price, "volume": volume, "amount": cost,
            "commission": fee, "signal_reason": f"排名{rank},得分{score:.2f}"
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
            "date": trade_date, "symbol": ts_code, "direction": "sell",
            "price": sell_price, "volume": volume, "amount": revenue,
            "commission": fee, "signal_reason": reason
        })

    def decide_daily_trades(
        self,
        holdings: Dict[str, Dict],  # 当前持仓 {ts_code: {buy_price, buy_date, volume, score, rank}}
        stock_scores: Dict[str, Dict],  # 今日得�� {ts_code: {score, price, rank}}
        strategy_params: Dict,  # 策略参数 {max_positions, take_profit_ratio, stop_loss_ratio, top_n, sell_rank_out, signal_confirm_days, blacklist_cooldown}
        trade_date: str
    ) -> Dict:
        """
        决策今日买卖（供观测系统使用）
        返回: {
            "buy": [{ts_code, price, volume, rank, score, reason}],
            "sell": [{ts_code, price, volume, reason}]
        }
        """
        max_positions = strategy_params.get("max_positions", 7)
        take_profit = strategy_params.get("take_profit_ratio", 0.15)
        stop_loss = strategy_params.get("stop_loss_ratio", -0.08)
        sell_rank_out = strategy_params.get("sell_rank_out", 50)
        signal_confirm_days = strategy_params.get("signal_confirm_days", 1)
        blacklist_cooldown = strategy_params.get("blacklist_cooldown", 30)

        buy_signals = []
        sell_signals = []

        # 检查冷却期：最近卖出过的股票不买入
        if not hasattr(self, '_sell_history'):
            self._sell_history = {}  # {ts_code: sell_date}

        # 清理过期的冷却记录
        from datetime import datetime, timedelta
        cooldown_expiry = (datetime.strptime(trade_date, "%Y%m%d") - timedelta(days=blacklist_cooldown)).strftime("%Y%m%d")
        for ts_code in list(self._sell_history.keys()):
            if self._sell_history[ts_code] < cooldown_expiry:
                del self._sell_history[ts_code]

        # 🔴 修改：先决策卖出
        for ts_code, holding in holdings.items():
            if ts_code not in stock_scores:
                continue

            buy_price = float(holding.get("buy_price", 0))
            current_price = float(stock_scores[ts_code]["price"])
            pct_change = (current_price - buy_price) / buy_price if buy_price > 0 else 0

            should_sell = False
            reason = ""

            # 1. 止盈
            if pct_change >= take_profit:
                should_sell = True
                reason = "止盈"
            # 2. 止损
            elif pct_change <= stop_loss:
                should_sell = True
                reason = "止损"
            # 3. 排名下降（增加缓冲：只有排名大幅下降才卖出）
            else:
                current_rank = stock_scores[ts_code].get("rank", 999)
                previous_rank = holding.get("rank", 999)
                # 排名下降超过N位才卖出（可配置参数）
                rank_threshold = strategy_params.get("rank_drop_threshold", 10)
                if current_rank > previous_rank + rank_threshold:
                    should_sell = True
                    reason = f"排名下降({previous_rank}->{current_rank})"

            if should_sell:
                sell_signals.append({
                    "ts_code": ts_code,
                    "price": current_price,
                    "volume": holding.get("volume", 0),
                    "reason": reason
                })
                # 记录卖出历史
                self._sell_history[ts_code] = trade_date

        # 🔴 修改：再决策买入（基于卖出后的持仓数）
        current_positions = len(holdings)
        positions_after_sell = current_positions - len(sell_signals)
        
        if positions_after_sell < max_positions:
            top_n = strategy_params.get("top_n", 15)
            
            # 过滤掉冷却期、已持仓、即将卖出的股票
            sell_codes = {s["ts_code"] for s in sell_signals}
            available_stocks = [
                (code, data) for code, data in stock_scores.items()
                if code not in holdings  # 排除已持仓
                and code not in sell_codes  # 排除即将卖出（虽然已持仓就不会在这里了）
                and code not in self._sell_history  # 排除冷却期
                and data.get("rank", 999) <= top_n  # 排名在前N名内
            ]
            
            # 按排名排序
            sorted_stocks = sorted(available_stocks, key=lambda x: x[1].get("rank", 999))
            
            # 取可买入数量（卖出后的空余仓位）
            can_buy = max_positions - positions_after_sell
            for ts_code, data in sorted_stocks[:can_buy]:
                price = data["price"]
                buy_signals.append({
                    "ts_code": ts_code,
                    "price": price,
                    "volume": 0,  # 需要外部根据资金计算
                    "score": data["score"],
                    "rank": data["rank"],
                    "reason": "因子选股"
                })

        return {"buy": buy_signals, "sell": sell_signals}

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

        days = len(equity_curve)
        annual_return = ((1 + total_return) ** (252 / max(days, 1))) - 1 if days > 0 else 0

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

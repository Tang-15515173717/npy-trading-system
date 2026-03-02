"""
VeighNa 回测引擎封装 - StockQuant Pro
提供简化的回测接口（Week 3 先实现 mock 版本，后续集成真实 VeighNa 引擎）。
"""
from typing import Dict, List, Optional
import random
from datetime import datetime, timedelta


class VnpyBacktestEngine:
    """VeighNa 回测引擎封装（简化版）"""

    def __init__(self):
        self.strategy_code = None
        self.stocks = []
        self.start_date = None
        self.end_date = None
        self.initial_capital = 1000000
        self.commission = 0.0003
        self.slippage = 0.01

    def run_backtest(
        self,
        strategy_code: Optional[str],
        stocks: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 1000000,
        commission: float = 0.0003,
        slippage: float = 0.01,
    ) -> Dict:
        """
        运行回测（简化版 mock 实现）。

        Args:
            strategy_code: 策略代码
            stocks: 股票列表
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            initial_capital: 初始资金
            commission: 手续费率
            slippage: 滑点

        Returns:
            回测结果字典
        """
        # 模拟回测计算（真实版本会调用 VeighNa 的 BacktestEngine）
        # 这里生成一些随机但合理的回测结果
        
        # 计算交易日数量（简化：按每月 20 个交易日估算）
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")
        days = (end - start).days
        trading_days = int(days * 240 / 365)  # 估算交易日

        # 生成回测统计数据
        total_return = random.uniform(-20, 50)  # -20% 到 +50%
        annual_return = total_return / (days / 365) if days > 365 else total_return
        max_drawdown = -random.uniform(5, 25)  # -5% 到 -25%
        sharpe_ratio = random.uniform(0.5, 2.5)
        win_rate = random.uniform(45, 65)  # 45% 到 65%
        total_trades = random.randint(20, 200)
        winning_trades = int(total_trades * win_rate / 100)

        statistics = {
            "total_return": round(total_return, 2),
            "annual_return": round(annual_return, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sharpe_ratio * 1.2, 2),
            "win_rate": round(win_rate, 2),
            "profit_loss_ratio": round(random.uniform(1.5, 3.0), 2),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
        }

        # 生成资金曲线（简化：只生成关键点）
        equity_curve = []
        current_equity = initial_capital
        benchmark_equity = initial_capital
        dates = [start + timedelta(days=i * 7) for i in range(min(trading_days // 7, 100))]
        
        for date in dates:
            current_equity *= (1 + random.uniform(-0.02, 0.03))
            benchmark_equity *= (1 + random.uniform(-0.01, 0.015))
            equity_curve.append({
                "date": date.strftime("%Y%m%d"),
                "equity": round(current_equity, 2),
                "benchmark": round(benchmark_equity, 2),
            })

        # 生成交易记录（简化：只生成部分）
        trades = []
        sample_trades = min(total_trades, 20)  # 只返回最近 20 笔
        for i in range(sample_trades):
            trade_date = (start + timedelta(days=random.randint(0, days))).strftime("%Y%m%d")
            stock = random.choice(stocks) if stocks else "000001.SZ"
            direction = random.choice(["buy", "sell"])
            price = round(random.uniform(10, 50), 2)
            volume = random.randint(100, 5000) // 100 * 100
            amount = price * volume
            
            trades.append({
                "date": trade_date,
                "stock": stock,
                "direction": direction,
                "price": price,
                "volume": volume,
                "amount": round(amount, 2),
                "commission": round(amount * commission, 2),
            })

        return {
            "statistics": statistics,
            "equity_curve": equity_curve,
            "trades": sorted(trades, key=lambda x: x["date"]),
        }

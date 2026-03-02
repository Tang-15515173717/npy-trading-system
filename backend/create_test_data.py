"""
StockQuant Pro - 前后端联调测试数据构造脚本

运行此脚本将创建完整的测试数据：
- 10 只股票基本信息
- 5 个策略（来自模板）
- 3 个回测任务（含结果）
- 1 个模拟交易会话（含持仓和交易记录）

运行方式：
cd /Users/mac/IdeaProjects/vnpy/backend
python3 create_test_data.py
"""

from app import create_app
from models.stock import Stock
from models.bar_data import BarData
from models.strategy import Strategy
from models.backtest import BacktestTask, BacktestTrade
from models.simulation import SimulationSession, SimulationPosition, SimulationTrade
from utils.database import db
from datetime import datetime, timedelta
import json
import random


def create_test_stocks():
    """创建测试股票数据"""
    print("📊 创建股票测试数据...")
    
    stocks_data = [
        {"ts_code": "000001.SZ", "symbol": "000001", "exchange": "SZSE", "name": "平安银行", "area": "深圳", "industry": "银行", "market": "主板", "list_date": "19910403"},
        {"ts_code": "000002.SZ", "symbol": "000002", "exchange": "SZSE", "name": "万科A", "area": "深圳", "industry": "房地产", "market": "主板", "list_date": "19910129"},
        {"ts_code": "000858.SZ", "symbol": "000858", "exchange": "SZSE", "name": "五粮液", "area": "四川", "industry": "白酒", "market": "主板", "list_date": "19980427"},
        {"ts_code": "600000.SH", "symbol": "600000", "exchange": "SSE", "name": "浦发银行", "area": "上海", "industry": "银行", "market": "主板", "list_date": "19991110"},
        {"ts_code": "600519.SH", "symbol": "600519", "exchange": "SSE", "name": "贵州茅台", "area": "贵州", "industry": "白酒", "market": "主板", "list_date": "20010827"},
        {"ts_code": "600036.SH", "symbol": "600036", "exchange": "SSE", "name": "招商银行", "area": "深圳", "industry": "银行", "market": "主板", "list_date": "20020409"},
        {"ts_code": "601318.SH", "symbol": "601318", "exchange": "SSE", "name": "中国平安", "area": "深圳", "industry": "保险", "market": "主板", "list_date": "20070301"},
        {"ts_code": "601888.SH", "symbol": "601888", "exchange": "SSE", "name": "中国中免", "area": "海南", "industry": "零售", "market": "主板", "list_date": "20090702"},
        {"ts_code": "300750.SZ", "symbol": "300750", "exchange": "SZSE", "name": "宁德时代", "area": "福建", "industry": "电池", "market": "创业板", "list_date": "20180611"},
        {"ts_code": "688981.SH", "symbol": "688981", "exchange": "SSE", "name": "中芯国际", "area": "上海", "industry": "半导体", "market": "科创板", "list_date": "20200716"},
    ]
    
    for data in stocks_data:
        stock = Stock.query.filter_by(ts_code=data["ts_code"]).first()
        if not stock:
            stock = Stock(**data)
            db.session.add(stock)
    
    db.session.commit()
    print(f"   ✅ 创建了 {len(stocks_data)} 只股票")


def create_test_strategies():
    """创建测试策略数据"""
    print("📝 创建策略测试数据...")
    
    strategies_data = [
        {
            "name": "双均线突破策略",
            "type": "trade",
            "code": "# 双均线策略\nclass DoubleMaStrategy:\n    fast_ma = 5\n    slow_ma = 20",
            "params": {"fast_ma": 5, "slow_ma": 20, "stop_loss": 0.05},
            "description": "经典双均线策略，适合趋势行情"
        },
        {
            "name": "MACD金叉策略",
            "type": "trade",
            "code": "# MACD策略\nclass MacdStrategy:\n    pass",
            "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
            "description": "基于MACD指标的交易策略"
        },
        {
            "name": "网格交易策略",
            "type": "trade",
            "code": "# 网格交易\nclass GridStrategy:\n    pass",
            "params": {"grid_min": 10.0, "grid_max": 15.0, "grid_step": 0.5},
            "description": "震荡市场高抛低吸"
        },
        {
            "name": "动量选股策略",
            "type": "select",
            "code": "# 动量选股\ndef select_stocks():\n    pass",
            "params": {"lookback_period": 20, "top_n": 10},
            "description": "选择近期涨幅最大的股票"
        },
        {
            "name": "布林带突破策略",
            "type": "trade",
            "code": "# 布林带策略\nclass BollingerStrategy:\n    pass",
            "params": {"period": 20, "std_dev": 2},
            "description": "价格突破布林带上下轨交易"
        },
    ]
    
    for data in strategies_data:
        strategy = Strategy.query.filter_by(name=data["name"]).first()
        if not strategy:
            strategy = Strategy(
                name=data["name"],
                type=data["type"],
                code=data["code"],
                params=json.dumps(data["params"], ensure_ascii=False),
                description=data["description"],
                status="active"
            )
            db.session.add(strategy)
    
    db.session.commit()
    print(f"   ✅ 创建了 {len(strategies_data)} 个策略")


def create_test_backtests():
    """创建测试回测数据"""
    print("⚡ 创建回测测试数据...")
    
    strategies = Strategy.query.limit(3).all()
    stocks = ["000001.SZ", "000002.SZ", "600519.SH"]
    
    for i, strategy in enumerate(strategies):
        task_id = f"bt_20260115_{10+i:02d}0000_{strategy.id:03d}"
        
        task = BacktestTask.query.filter_by(task_id=task_id).first()
        if not task:
            # 生成模拟回测结果
            total_return = random.uniform(-10, 40)
            max_drawdown = -random.uniform(5, 20)
            sharpe_ratio = random.uniform(0.8, 2.5)
            total_trades = random.randint(30, 150)
            win_rate = random.uniform(50, 70)
            
            result = {
                "statistics": {
                    "total_return": round(total_return, 2),
                    "annual_return": round(total_return / 2, 2),
                    "max_drawdown": round(max_drawdown, 2),
                    "sharpe_ratio": round(sharpe_ratio, 2),
                    "sortino_ratio": round(sharpe_ratio * 1.15, 2),
                    "win_rate": round(win_rate, 2),
                    "profit_loss_ratio": round(random.uniform(1.5, 3.0), 2),
                    "total_trades": total_trades,
                    "winning_trades": int(total_trades * win_rate / 100),
                    "losing_trades": int(total_trades * (100 - win_rate) / 100),
                },
                "equity_curve": [
                    {"date": "20230101", "equity": 1000000, "benchmark": 1000000},
                    {"date": "20230630", "equity": 1050000, "benchmark": 1020000},
                    {"date": "20231231", "equity": 1150000, "benchmark": 1080000},
                    {"date": "20240630", "equity": 1220000, "benchmark": 1100000},
                    {"date": "20241231", "equity": 1000000 * (1 + total_return/100), "benchmark": 1120000},
                ]
            }
            
            task = BacktestTask(
                task_id=task_id,
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                stocks=json.dumps(stocks, ensure_ascii=False),
                start_date="20230101",
                end_date="20241231",
                initial_capital=1000000,
                commission=0.0003,
                slippage=0.01,
                benchmark="000001.SH",
                status="completed",
                progress=100,
                result=json.dumps(result, ensure_ascii=False),
                started_at=datetime.utcnow() - timedelta(days=30-i),
                completed_at=datetime.utcnow() - timedelta(days=30-i, hours=-2),
                created_at=datetime.utcnow() - timedelta(days=30-i)
            )
            db.session.add(task)
            
            # 添加几条交易记录
            for j in range(5):
                trade = BacktestTrade(
                    task_id=task_id,
                    trade_date=f"2023{random.randint(1,12):02d}{random.randint(1,28):02d}",
                    ts_code=random.choice(stocks),
                    direction=random.choice(["buy", "sell"]),
                    price=round(random.uniform(10, 50), 2),
                    volume=random.randint(100, 5000) // 100 * 100,
                    amount=0,  # 会在保存时计算
                    commission=0,
                )
                trade.amount = trade.price * trade.volume
                trade.commission = trade.amount * 0.0003
                db.session.add(trade)
    
    db.session.commit()
    print(f"   ✅ 创建了 3 个回测任务及交易记录")


def create_test_simulation():
    """创建测试模拟交易数据"""
    print("💰 创建模拟交易测试数据...")
    
    strategy = Strategy.query.first()
    if not strategy:
        print("   ⚠️ 没有策略，跳过模拟交易")
        return
    
    session_id = "sim_20260128_100000_001"
    session = SimulationSession.query.filter_by(session_id=session_id).first()
    
    if not session:
        initial_capital = 1000000
        session = SimulationSession(
            session_id=session_id,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            initial_capital=initial_capital,
            current_capital=850000,
            status="running",
            started_at=datetime.utcnow() - timedelta(days=2)
        )
        db.session.add(session)
        
        # 创建持仓
        positions_data = [
            {"ts_code": "000001.SZ", "volume": 5000, "cost_price": 15.30, "current_price": 16.20},
            {"ts_code": "600519.SH", "volume": 200, "cost_price": 1680.50, "current_price": 1720.00},
            {"ts_code": "300750.SZ", "volume": 1000, "cost_price": 180.20, "current_price": 175.80},
        ]
        
        for data in positions_data:
            market_value = data["current_price"] * data["volume"]
            cost = data["cost_price"] * data["volume"]
            pnl = market_value - cost
            pnl_pct = (pnl / cost) * 100
            
            position = SimulationPosition(
                session_id=session_id,
                ts_code=data["ts_code"],
                volume=data["volume"],
                available=data["volume"],
                cost_price=data["cost_price"],
                current_price=data["current_price"],
                market_value=market_value,
                pnl=pnl,
                pnl_pct=pnl_pct,
            )
            db.session.add(position)
            
            # 买入记录
            trade = SimulationTrade(
                session_id=session_id,
                datetime=datetime.utcnow() - timedelta(days=2, hours=random.randint(1, 10)),
                ts_code=data["ts_code"],
                direction="buy",
                price=data["cost_price"],
                volume=data["volume"],
                amount=cost,
                commission=round(cost * 0.0003, 2),
            )
            db.session.add(trade)
        
        db.session.commit()
        print(f"   ✅ 创建了 1 个模拟交易会话，3 个持仓，3 条交易记录")


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 StockQuant Pro - 测试数据构造")
    print("=" * 60)
    print()
    
    app = create_app()
    with app.app_context():
        create_test_stocks()
        create_test_strategies()
        create_test_backtests()
        create_test_simulation()
    
    print()
    print("=" * 60)
    print("✅ 测试数据创建完成！")
    print("=" * 60)
    print()
    print("📊 数据统计：")
    print("   - 股票：10 只")
    print("   - 策略：5 个")
    print("   - 回测：3 个任务")
    print("   - 模拟交易：1 个会话")
    print()
    print("🔗 现在可以访问前端测试：")
    print("   http://localhost:8081")
    print()


if __name__ == "__main__":
    main()

"""
重新计算��用 reversal_5d 的策略回测

reversal_5d 数据已补充完成（从10条 → 523,390条）

需要重新回测的策略：
1. 震荡组合 (ID=20) - 直接使用 reversal_5d
2. v2_adaptive 引擎 - 包含震荡组合
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models.stock import Stock
from models.factor_combo import FactorCombo
from services.scoring_engines.simple_conservative import SimpleConservativeEngine
from services.scoring_engines.v2_adaptive import AdaptiveEngine
from sqlalchemy import text
import json

print("=" * 80)
print("重新计算受影响的策略回测")
print("=" * 80)
print()

app = create_app()

with app.app_context():
    from utils.database import db
    from models.bar_data import BarData
    from models.factor_data import FactorData

    # 获取150只优质主板股票
    print("[1/3] 获取股票池...")
    print("-" * 80)

    # 获取主板股票代码
    all_stocks = db.session.query(BarData.ts_code).distinct().all()
    main_board = [ts_code for (ts_code,) in all_stocks
                  if ts_code.startswith('60') or ts_code.startswith('00')]

    # 排除ST股票
    non_st_stocks = [s for s in main_board if 'ST' not in s]

    # 检查数据完整性
    quality_stocks = []
    for ts_code in non_st_stocks[:300]:  # 检查前300只
        # 检查2023年数据量
        count_2023 = BarData.query.filter(
            BarData.ts_code == ts_code,
            BarData.trade_date >= '20230101',
            BarData.trade_date <= '20231231'
        ).count()

        # 检查因子数据
        factor_count = FactorData.query.filter(
            FactorData.ts_code == ts_code
        ).count()

        # 2023年至少有200条K线数据，且有因子数据
        if count_2023 >= 200 and factor_count >= 500:
            quality_stocks.append(ts_code)

        if len(quality_stocks) >= 150:
            break

    stocks = quality_stocks
    print(f"  ✅ 获取到 {len(stocks)} 只股票")
    print()

    # 回测配置
    backtest_config = {
        "start_date": "20240101",
        "end_date": "20260210",
        "initial_capital": 1000000,
        "commission": 0.0001,
        "slippage": 0.0001,
        "take_profit_ratio": 0.15,
        "stop_loss_ratio": -0.08
    }

    # 需要回测的策略
    strategies = [
        {"id": 20, "name": "震荡组合", "engine": "simple_conservative"},
        {"id": "v2_adaptive", "name": "v2_adaptive自适应引擎", "engine": "v2_adaptive"}
    ]

    results = []

    # 逐个回测
    for i, strategy in enumerate(strategies):
        print(f"[{i+2}/3] 回测: {strategy['name']}")
        print("-" * 80)

        # 创建回测引擎
        if strategy["engine"] == "simple_conservative":
            engine = SimpleConservativeEngine()
            factor_combo_id = strategy["id"]
        else:
            engine = AdaptiveEngine()
            factor_combo_id = None  # v2_adaptive 会自动选择因子组合

        print(f"  🔧 引擎: {strategy['engine']}")
        print(f"  📊 股票池: {len(stocks)} 只")
        print(f"  📅 期间: 2024-01-01 至 2026-02-10")
        print()

        # 执行回测
        print(f"  ⏳ 开始回测...")
        try:
            result = engine.run_backtest(
                factor_combo_id=factor_combo_id,
                stocks=stocks,
                start_date=backtest_config["start_date"],
                end_date=backtest_config["end_date"],
                initial_capital=backtest_config["initial_capital"],
                commission=backtest_config["commission"],
                slippage=backtest_config["slippage"],
                backtest_params=backtest_config
            )

            # 打印结果
            print()
            print("  🎯 回测结果:")
            print(f"  📊 总收益率: {result.get('total_return', 0):>7.2f}%")
            print(f"  📈 夏普比率: {result.get('sharpe_ratio', 0):>7.2f}")
            print(f"  📉 最大回撤: {result.get('max_drawdown', 0):>7.2f}%")
            print(f"  💼 交易次数: {result.get('trade_count', 0):>6}笔")
            print()

            results.append({
                "name": strategy["name"],
                "result": result
            })

        except Exception as e:
            print(f"  ❌ 回测失败: {e}")
            import traceback
            traceback.print_exc()
            print()

    # 总结
    print("=" * 80)
    print("📋 重新回测总结")
    print("=" * 80)
    print()

    print("策略名称                  收益率      夏普比率    最大回撤    交易次数")
    print("-" * 80)
    for r in results:
        result = r["result"]
        total_return = result.get("total_return", 0)
        sharpe_ratio = result.get("sharpe_ratio", 0)
        max_drawdown = result.get("max_drawdown", 0)
        trade_count = result.get("trade_count", 0)
        print(f"{r['name']:<25} {total_return:>7.2f}%     {sharpe_ratio:>5.2f}      {max_drawdown:>6.2f}%     {trade_count:>4}笔")

    print()
    print("=" * 80)
    print("💡 对比之前的回测结果:")
    print("   震荡组合: 126.15% → ? (reversal_5d 数据从10条 → 523,390条)")
    print("   v2_adaptive: 16.22% → ?")
    print("=" * 80)

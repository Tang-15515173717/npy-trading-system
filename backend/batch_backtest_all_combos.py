"""
批量回测所有因子组合 - StockQuant Pro
遵循 STRATEGY_LESSONS_LEARNED.md 的最佳实践
任务串行执行，一个完成后再执行下一个，避免系统压力
"""
from app import create_app
from models.bar_data import BarData
from models.factor_data import FactorData
from models.factor_combo import FactorCombo
from models.backtest import BacktestTask
from utils.database import db
from services.backtest_service import BacktestService
from datetime import datetime
import json
import time


def get_quality_stocks(limit=150):
    """
    获取优质股票池

    筛选标准（来自 STRATEGY_LESSONS_LEARNED.md）：
    1. 主板股票（60x, 000/001开头）
    2. 数据完整（2023-2026期间）
    3. 排除ST股票
    """
    # 获取主板股票代码
    all_stocks = db.session.query(BarData.ts_code).distinct().all()
    main_board = [ts_code for (ts_code,) in all_stocks
                  if ts_code.startswith('60') or ts_code.startswith('00')]

    # 排除ST股票
    non_st_stocks = [s for s in main_board if 'ST' not in s]

    # 检查数据完整性（2023-2026）
    quality_stocks = []
    for ts_code in non_st_stocks[:limit*2]:  # 检查更多股票以便筛选
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

        if len(quality_stocks) >= limit:
            break

    return quality_stocks


def generate_task_id():
    """生成唯一任务ID（含随机数避免重复）"""
    import random
    return f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"


def run_backtest_and_wait(factor_combo_id, combo_name, stocks, engine_id="simple_conservative"):
    """
    直接调用引擎执行回测并保存结果

    参数：
    - factor_combo_id: 因子组合ID
    - combo_name: 因子组合名称
    - stocks: 股票池列表
    - engine_id: 引擎ID（默认simple_conservative，也可用v2_adaptive）
    """
    from services.scoring_engines import get_engine

    # 根据股票池大小调整参数（来自经验文档）
    stocks_count = len(stocks)
    top_n = max(10, int(stocks_count * 0.10))  # 10%或至少10只
    max_positions = max(5, int(top_n * 0.50))  # 50%的top_n

    # 回测参数
    backtest_params = {
        "top_n": top_n,
        "max_positions": max_positions,
        "take_profit_ratio": 0.15,  # 15%止盈
        "stop_loss_ratio": -0.08,   # -8%止损
        "sell_rank_out": 50,
        "trailing_stop_ratio": 0.10,
        "signal_confirm_days": 2,
        "blacklist_cooldown": 30
    }

    print(f"  📤 准备执行: {combo_name}")
    print(f"     引擎: {engine_id}")
    print(f"     股票池: {len(stocks)}只")
    print(f"     参数: top_n={top_n}, max_positions={max_positions}")

    # 执行回测
    print(f"  ⏳ 开始执行回测...")
    start_time = time.time()

    try:
        # 直接调用引擎
        engine = get_engine(engine_id)
        result = engine.run_backtest(
            factor_combo_id=factor_combo_id,
            stocks=stocks,
            start_date="20240101",  # 样本外测试：2024年开始
            end_date="20260210",
            initial_capital=1000000,
            commission=0.0003,
            slippage=0.0001,
            backtest_params=backtest_params
        )

        elapsed = time.time() - start_time
        print(f"  ✅ 回测完成 (耗时: {elapsed:.1f}秒)")

        # 保存结果到数据库
        task_id_str = generate_task_id()
        task = BacktestTask(
            task_id=task_id_str,
            strategy_name=f"批量回测-{combo_name}",
            scoring_engine_id=engine_id,
            factor_combo_id=factor_combo_id,
            factor_combo_name=combo_name,
            stocks=json.dumps(stocks, ensure_ascii=False),
            start_date="20240101",
            end_date="20260210",
            initial_capital=1000000,
            commission=0.0003,
            slippage=0.0001,
            backtest_params=json.dumps(backtest_params, ensure_ascii=False),
            status="completed",
            result=json.dumps(result, ensure_ascii=False),
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db.session.add(task)
        db.session.commit()
        db.session.refresh(task)

        print(f"  💰 结果已保存到任务 {task.id}")

        return task.to_dict()

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  ❌ 回测失败 (耗时: {elapsed:.1f}秒): {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    app = create_app()

    with app.app_context():
        print("\n" + "="*80)
        print("📊 批量回测所有因子组合（串行执行）")
        print("="*80 + "\n")

        # 1. 获取优质股票池
        print("📋 步骤1：筛选优质股票池...")
        quality_stocks = get_quality_stocks(limit=150)
        print(f"✅ 筛选出 {len(quality_stocks)} 只优质股票")
        print(f"   股票示例: {', '.join(quality_stocks[:5])}...")

        # 2. 获取所有因子组合
        print("\n📋 步骤2：获取所有因子组合...")
        combos = FactorCombo.query.order_by(FactorCombo.id).all()
        print(f"✅ 共有 {len(combos)} 个因子组合")

        # 3. 串行执行回测任务（一个一个来，避免压力）
        print("\n📋 步骤3：串行执行回测任务...")
        print(f"   回测期间: 2024-01-01 至 2026-02-10（样本外测试）")
        print(f"   初始资金: 1,000,000 元")
        print(f"   引擎: simple_conservative")
        print(f"   止盈: 15%, 止损: -8%")
        print(f"   ⚠️  任务将串行执行，一个完成后再执行下一个\n")

        results = []
        total_start_time = time.time()

        for i, combo in enumerate(combos, 1):
            print(f"\n[{i}/{len(combos)}] 正在处理: {combo.name} (ID={combo.id})")
            print("-" * 60)

            result = run_backtest_and_wait(
                factor_combo_id=combo.id,
                combo_name=combo.name,
                stocks=quality_stocks,
                engine_id="simple_conservative"
            )

            if result:
                results.append({
                    "combo_id": combo.id,
                    "combo_name": combo.name,
                    "task_id": result.get("task_id"),
                    "task_db_id": result.get("id"),
                    "result": result
                })

                # 显示简要结果
                if result.get("result"):
                    try:
                        result_data = json.loads(result["result"])
                        stats = result_data.get("statistics", {})
                        total_return = stats.get("total_return", 0)
                        print(f"     💰 总收益率: {total_return:.2f}%")
                    except:
                        pass

        # 4. 额外测试 v2_adaptive 引擎
        print(f"\n[额外任务] 测试 v2_adaptive 自适应引擎...")
        print("-" * 60)

        result_adaptive = run_backtest_and_wait(
            factor_combo_id=18,  # v2_adaptive会忽略这个参数
            combo_name="v2_adaptive 自适应引擎",
            stocks=quality_stocks,
            engine_id="v2_adaptive"
        )

        if result_adaptive:
            results.append({
                "combo_id": 0,
                "combo_name": "v2_adaptive 自适应引擎",
                "task_id": result_adaptive.get("task_id"),
                "task_db_id": result_adaptive.get("id"),
                "result": result_adaptive
            })

            # 显示简要结果
            if result_adaptive.get("result"):
                try:
                    result_data = json.loads(result_adaptive["result"])
                    stats = result_data.get("statistics", {})
                    total_return = stats.get("total_return", 0)
                    print(f"     💰 总收益率: {total_return:.2f}%")
                except:
                    pass

        total_elapsed = time.time() - total_start_time

        print("\n" + "="*80)
        print(f"✅ 批量回测完成！共完成 {len(results)} 个任务")
        print(f"   总耗时: {total_elapsed/60:.1f} 分钟")
        print("="*80)

        # 5. 保存结果
        print("\n📋 步骤4：保存回测结果...")
        with open('batch_backtest_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"💾 结果已保存到: batch_backtest_results.json")

        # 6. 生成总结报告
        print("\n📊 回测结果排行榜（按收益率排序）:")
        print("-" * 100)
        print(f"{'排名':<6} {'因子组合':<30} {'收益率':<12} {'夏普比率':<12} {'最大回撤':<12}")
        print("-" * 100)

        # 解析结果并排序
        parsed_results = []
        for r in results:
            try:
                result_data = json.loads(r["result"]) if r.get("result") else {}
                stats = result_data.get("statistics", {})
                total_return = stats.get("total_return", 0)
                sharpe_ratio = stats.get("sharpe_ratio", 0)
                max_drawdown = stats.get("max_drawdown", 0)
                parsed_results.append({
                    "combo_name": r["combo_name"],
                    "total_return": total_return,
                    "sharpe_ratio": sharpe_ratio,
                    "max_drawdown": max_drawdown
                })
            except Exception as e:
                parsed_results.append({
                    "combo_name": r["combo_name"],
                    "total_return": -999,
                    "sharpe_ratio": 0,
                    "max_drawdown": 0
                })

        parsed_results.sort(key=lambda x: x["total_return"], reverse=True)

        for rank, r in enumerate(parsed_results, 1):
            combo_name = r["combo_name"][:28]
            total_return = r["total_return"]
            sharpe_ratio = r["sharpe_ratio"]
            max_drawdown = r["max_drawdown"]

            if total_return == -999:
                print(f"{rank:<6} {combo_name:<30} {'失败':<12} {'N/A':<12} {'N/A':<12}")
            else:
                print(f"{rank:<6} {combo_name:<30} {total_return:<12.2f} {sharpe_ratio:<12.2f} {max_drawdown:<12.2f}")

        print("-" * 100)

        # 7. 策略推荐
        print("\n💡 策略推荐:")

        top_3 = parsed_results[:3]
        for i, r in enumerate(top_3, 1):
            if r["total_return"] > 10:
                print(f"   {i}. {r['combo_name']} - 收益率 {r['total_return']:.2f}%, 夏普 {r['sharpe_ratio']:.2f} ✅推荐")
            elif r["total_return"] > 0:
                print(f"   {i}. {r['combo_name']} - 收益率 {r['total_return']:.2f}%, 夏普 {r['sharpe_ratio']:.2f} ⚠️可用")
            else:
                print(f"   {i}. {r['combo_name']} - 收益率 {r['total_return']:.2f}% ❌不推荐")

        print()


if __name__ == "__main__":
    main()

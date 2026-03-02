"""
生成批量回测结果报告
"""
from app import create_app
from models.backtest import BacktestTask
import json

app = create_app()
with app.app_context():
    # 获取所有批量回测任务
    tasks = BacktestTask.query.filter(
        BacktestTask.id >= 116
    ).order_by(BacktestTask.id).all()

    print('=' * 100)
    print('📊 批量回测结果总结报告')
    print('=' * 100)
    print()

    # 解析结果
    results = []
    for t in tasks:
        try:
            result_data = json.loads(t.result) if t.result else {}
            stats = result_data.get('statistics', {})
            total_return = stats.get('total_return', 0)
            sharpe_ratio = stats.get('sharpe_ratio', 0)
            max_drawdown = stats.get('max_drawdown', 0)
            trade_count = len(result_data.get('trades', []))

            results.append({
                'id': t.id,
                'combo_name': t.factor_combo_name or t.strategy_name,
                'combo_id': t.factor_combo_id,
                'engine': t.scoring_engine_id,
                'total_return': total_return,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'trade_count': trade_count
            })
        except Exception as e:
            results.append({
                'id': t.id,
                'combo_name': t.factor_combo_name or t.strategy_name,
                'combo_id': t.factor_combo_id,
                'engine': t.scoring_engine_id,
                'total_return': -999,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'trade_count': 0
            })

    # 按收益率排序
    results.sort(key=lambda x: x['total_return'], reverse=True)

    # 打印排行榜
    header = f"{'排名':<6} {'因子组合':<35} {'收益率':<12} {'夏普比率':<12} {'最大回撤':<12} {'交易次数':<10}"
    print(header)
    print('-' * 100)

    for rank, r in enumerate(results, 1):
        combo_name = r['combo_name'][:33]
        total_return = r['total_return']
        sharpe_ratio = r['sharpe_ratio']
        max_drawdown = r['max_drawdown']
        trade_count = r['trade_count']

        if total_return == -999:
            row = f"{rank:<6} {combo_name:<35} {'失败':<12} {'N/A':<12} {'N/A':<12} {trade_count:<10}"
        else:
            row = f"{rank:<6} {combo_name:<35} {total_return:<12.2f} {sharpe_ratio:<12.2f} {max_drawdown:<12.2f} {trade_count:<10}"
        print(row)

    print('-' * 100)
    print()

    # 统计
    positive_count = len([r for r in results if r['total_return'] > 0])
    negative_count = len([r for r in results if r['total_return'] < 0])
    valid_results = [r for r in results if r['total_return'] != -999]
    avg_return = sum([r['total_return'] for r in valid_results]) / len(valid_results) if valid_results else 0

    print(f'📈 统计信息：')
    print(f'   - 总任务数: {len(results)}')
    print(f'   - 盈利策略: {positive_count} 个')
    print(f'   - 亏损策略: {negative_count} 个')
    print(f'   - 平均收益率: {avg_return:.2f}%')
    print()

    # 策略推荐
    print('💡 策略推荐（基于收益率和夏普比率）：')
    print()

    print('✅ 推荐策略（收益率 > 10%）：')
    top_strategies = [r for r in results if r['total_return'] > 10]
    if top_strategies:
        for r in top_strategies[:5]:
            print(f'   {r["combo_name"]} - 收益率 {r["total_return"]:.2f}%, 夏普 {r["sharpe_ratio"]:.2f}, 交易{r["trade_count"]}笔')
    else:
        print('   无（当前所有策略收益率均未超过10%）')

    print()
    print('⚠️  可用策略（收益率 0-10%）：')
    ok_strategies = [r for r in results if 0 < r['total_return'] <= 10]
    if ok_strategies:
        for r in ok_strategies:
            print(f'   {r["combo_name"]} - 收益率 {r["total_return"]:.2f}%')
    else:
        print('   无')

    print()
    print('❌ 不推荐策略（收益率 < 0）：')
    bad_strategies = [r for r in results if r['total_return'] < 0]
    if bad_strategies:
        # 显示最差的3个
        worst = sorted(bad_strategies, key=lambda x: x['total_return'])[:3]
        for r in worst:
            print(f'   {r["combo_name"]} - 收益率 {r["total_return"]:.2f}%')
        print(f'   ... 共 {len(bad_strategies)} 个亏损策略')

    print()
    print('=' * 100)
    print()
    print('📝 关键发现：')

    if avg_return < 0:
        print('   ⚠️  平均收益率为负，说明当前市场环境（2024-2026）对量化策略不友好')
        print('   💡 建议：')
        print('      1. 检查股票池质量（是否包含太多劣质股）')
        print('      2. 调整回测参数（止盈止损、持仓周期等）')
        print('      3. 考虑使用 v2_adaptive 引擎（根据市场状态动态调整）')
    elif avg_return < 5:
        print('   ⚠️  平均收益率较低，策略效果有限')
        print('   💡 建议：优化因子组合或调整参数')
    else:
        print('   ✅ 平均收益率为正，策略整体有效')

    print()

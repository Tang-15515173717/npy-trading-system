"""
查询新批量回测结果（ID>=116）
"""
from app import create_app
from models.backtest import BacktestTask
import json

app = create_app()
with app.app_context():
    # 只查询新的批量回测任务
    tasks = BacktestTask.query.filter(
        BacktestTask.id >= 116
    ).order_by(BacktestTask.id).all()

    print('=' * 80)
    print('📊 新批量回测结果（样本外测试：2024-2026）')
    print('=' * 80)
    print()

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
                'total_return': total_return,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'trade_count': trade_count
            })
        except Exception as e:
            print(f"解析失败: {t.factor_combo_name}, 错误: {e}")

    # 按收益率排序
    results.sort(key=lambda x: x['total_return'], reverse=True)

    # 打印
    print(f"{'排名':<6} {'因子组合':<30} {'收益率':<12} {'夏普比率':<12} {'交易次数':<10}")
    print('-' * 80)

    for rank, r in enumerate(results, 1):
        combo_name = r['combo_name'][:28]
        total_return = r['total_return']
        sharpe_ratio = r['sharpe_ratio']
        trade_count = r['trade_count']

        if total_return > 0:
            print(f'{rank:<6} {combo_name:<30} {total_return:<12.2f} {sharpe_ratio:<12.2f} {trade_count:<10}')
        elif total_return == 0:
            print(f'{rank:<6} {combo_name:<30} {"无交易":<12} {"N/A":<12} {trade_count:<10}')
        else:
            print(f'{rank:<6} {combo_name:<30} {total_return:<12.2f} {sharpe_ratio:<12.2f} {trade_count:<10}')

    print('-' * 80)
    print()

    # 统计
    positive = len([r for r in results if r['total_return'] > 0])
    zero = len([r for r in results if r['total_return'] == 0])
    negative = len([r for r in results if r['total_return'] < 0])
    avg = sum([r['total_return'] for r in results]) / len(results) if results else 0

    print(f'📈 统计：')
    print(f'   总任务数: {len(results)}')
    print(f'   盈利: {positive}个, 无交易: {zero}个, 亏损: {negative}个')
    print(f'   平均收益率: {avg:.2f}%')
    print()

    # 推荐
    print('💡 推荐策略（收益率>10%）：')
    top = [r for r in results if r['total_return'] > 10]
    if top:
        for r in top:
            print(f'   {r["combo_name"]} - {r["total_return"]:.2f}%, 夏普{r["sharpe_ratio"]:.2f}, {r["trade_count"]}笔交易')
    else:
        print('   无（收益率均未超过10%）')

    print()
    print('⚠️  可用策略（收益率0-10%）：')
    ok = [r for r in results if 0 < r['total_return'] <= 10]
    if ok:
        for r in ok:
            print(f'   {r["combo_name"]} - {r["total_return"]:.2f}%')
    else:
        print('   无')

    print()
    print('=' * 80)

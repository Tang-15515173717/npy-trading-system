"""
快速查看3个优化策略的运行状态
"""
from app import create_app
from models.daily_observer import DailyObserverStrategy, DailyObserverRecord
from utils.database import db
from sqlalchemy import func

def get_strategy_status():
    """获取策略状态"""
    app = create_app()
    with app.app_context():
        print("=" * 80)
        print("📊 观测策略运行状态")
        print("=" * 80)
        print()

        for strategy_id in [40, 41, 42]:
            strategy = DailyObserverStrategy.query.get(strategy_id)
            if not strategy:
                continue

            print(f"{'=' * 80}")
            print(f"🎯 策略 {strategy.id}: {strategy.name}")
            print(f"{'=' * 80}")
            print(f"引擎: {strategy.scoring_engine_id}")
            print(f"因子组合: {strategy.factor_combo_id}")
            print(f"状态: {strategy.status}")
            print(f"持仓数: {strategy.max_positions}")
            print(f"止盈/止损: {strategy.take_profit_ratio}/{strategy.stop_loss_ratio}")
            print()

            # 获取最新记录
            latest_record = DailyObserverRecord.query.filter_by(
                strategy_id=strategy_id
            ).order_by(DailyObserverRecord.date.desc()).first()

            if latest_record:
                print(f"📅 最新记录: {latest_record.date}")
                print(f"   总资产: {latest_record.total_value:,.2f} 元")
                print(f"   累计收益: {latest_record.cumulative_return:.2f}%")
                print(f"   当日收益: {latest_record.day_return:.2f}%")
                print(f"   持仓数: {latest_record.holding_count}")
                print(f"   现金: {latest_record.cash:,.2f} 元")
                print(f"   持仓市值: {latest_record.position_value:,.2f} 元")

                # 获取总记录数
                total_records = DailyObserverRecord.query.filter_by(
                    strategy_id=strategy_id
                ).count()
                print(f"   观测天数: {total_records} 天")

                # 获取交易统计
                from models.daily_observer import DailyObserverTrade
                buy_trades = DailyObserverTrade.query.filter_by(
                    strategy_id=strategy_id,
                    direction="buy"
                ).count()
                sell_trades = DailyObserverTrade.query.filter_by(
                    strategy_id=strategy_id,
                    direction="sell"
                ).count()
                print(f"   交易次数: 买入{buy_trades}次, 卖出{sell_trades}次")
            else:
                print("⚠️ 暂无观测记录，请运行策略")

            print()

        print("=" * 80)
        print("📊 三策略对比")
        print("=" * 80)
        print(f"{'策略':<20} {'累计收益':<12} {'最大回撤':<12} {'交易次数':<12} {'胜率':<12}")
        print("-" * 80)

        for strategy_id in [40, 41, 42]:
            strategy = DailyObserverStrategy.query.get(strategy_id)
            if not strategy:
                continue

            latest_record = DailyObserverRecord.query.filter_by(
                strategy_id=strategy_id
            ).order_by(DailyObserverRecord.date.desc()).first()

            if latest_record:
                # 计算最大回撤
                records = DailyObserverRecord.query.filter_by(
                    strategy_id=strategy_id
                ).order_by(DailyObserverRecord.date).all()

                max_dd = 0
                peak = records[0].total_value if records else 1000000
                for r in records:
                    if r.total_value > peak:
                        peak = r.total_value
                    dd = (peak - r.total_value) / peak * 100 if peak > 0 else 0
                    if dd > max_dd:
                        max_dd = dd

                # 计算胜率
                from models.daily_observer import DailyObserverTrade
                total_sells = DailyObserverTrade.query.filter_by(
                    strategy_id=strategy_id,
                    direction="sell"
                ).count()

                profit_sells = db.session.query(DailyObserverTrade).filter(
                    DailyObserverTrade.strategy_id == strategy_id,
                    DailyObserverTrade.direction == "sell",
                    DailyObserverTrade.signal_reason.like("%止盈%")
                ).count()

                win_rate = (profit_sells / total_sells * 100) if total_sells > 0 else 0

                # 总交易次数
                total_trades = DailyObserverTrade.query.filter_by(
                    strategy_id=strategy_id
                ).count()

                print(f"{strategy.name:<20} "
                      f"{latest_record.cumulative_return:>8.2f}%    "
                      f"{max_dd:>8.2f}%    "
                      f"{total_trades:>8}次    "
                      f"{win_rate:>8.1f}%")

        print()
        print("=" * 80)
        print("📍 查看详情:")
        print("   http://localhost:8080/daily-observer")
        print("=" * 80)

if __name__ == "__main__":
    get_strategy_status()

"""
为所有有K线但缺少因子数据的股票计算因子
批量计算并保存到数据库
"""
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models.bar_data import BarData
from models.factor_data import FactorData
from utils.factor_calculator import FactorCalculator
from utils.database import db
import pandas as pd

def print_progress_bar(current, total, prefix='', suffix='', length=50):
    """打印进度条"""
    percent = f"{100 * (current / float(total)):.1f}"
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='', flush=True)
    if current == total:
        print()

def get_missing_factor_stocks():
    """找出���K线但缺少因子数据的股票"""
    print("\n1️⃣ 分析数据情况...")

    # 获取所有有K线数据的股票
    bar_stocks = db.session.query(BarData.ts_code).distinct().all()
    bar_stocks_set = {s[0] for s in bar_stocks}

    # 获取所有有因子数据的股票
    factor_stocks = db.session.query(FactorData.ts_code).distinct().all()
    factor_stocks_set = {s[0] for s in factor_stocks}

    # 找出缺失的股票
    missing_stocks = bar_stocks_set - factor_stocks_set

    print(f"   有K线的股票: {len(bar_stocks_set)}只")
    print(f"   有因子的股票: {len(factor_stocks_set)}只")
    print(f"   缺少因子的股票: {len(missing_stocks)}只")

    return list(missing_stocks), bar_stocks_set

def get_all_trade_dates():
    """获取所有需要计算因子的日期"""
    # 从因子数据中获取日期范围
    dates = db.session.query(FactorData.trade_date).distinct().order_by(
        FactorData.trade_date
    ).all()

    date_list = [d[0] for d in dates]
    print(f"\n2️⃣ 需要计算因子的日期数: {len(date_list)}天")
    print(f"   日期范围: {date_list[0]} ~ {date_list[-1]}")

    return date_list

def calculate_factors_for_stocks(stocks, dates):
    """为指定股票批量计算因子"""
    print(f"\n3️⃣ 开始批量计算因子...")
    print(f"   股票数: {len(stocks)}")
    print(f"   日期数: {len(dates)}")

    fc = FactorCalculator()
    total_records = 0
    skipped_records = 0
    failed_dates = []

    start_time = time.time()

    for date_idx, trade_date in enumerate(dates, 1):
        try:
            # 显示进度
            print_progress_bar(
                date_idx - 1, len(dates),
                prefix=f"[{date_idx}/{len(dates)}]",
                suffix=f"{trade_date}"
            )

            # 批量计算当天所有股票的因子
            result = fc.batch_calculate_vectorized(stocks, trade_date)

            # 保存到数据库
            batch_save_count = 0
            for item in result['results']:
                ts_code = item['ts_code']
                factors = item['factors']

                # 检查是否已存在
                exists = FactorData.query.filter_by(
                    ts_code=ts_code,
                    trade_date=trade_date
                ).first()

                if exists:
                    skipped_records += 1
                    continue

                # 创建因子记录
                factor_record = FactorData(
                    ts_code=ts_code,
                    trade_date=trade_date,
                    return_5d=factors.get('return_5d'),
                    return_20d=factors.get('return_20d'),
                    return_60d=factors.get('return_60d'),
                    volatility_20d=factors.get('volatility_20d'),
                    volume_ratio=factors.get('volume_ratio'),
                    rsi_14=factors.get('rsi_14'),
                    macd=factors.get('macd'),
                    macd_signal=factors.get('macd_signal'),
                    macd_hist=factors.get('macd_hist'),
                )
                db.session.add(factor_record)
                batch_save_count += 1

            # 提交数据库
            db.session.commit()
            total_records += batch_save_count

            # 显示当日结果
            if result['fail_count'] > 0:
                print(f"\n   ⚠️  {trade_date}: 成功{result['success_count']}, 失败{result['fail_count']}")
                if result['failed_stocks'][:5]:
                    print(f"      失败样例: {result['failed_stocks'][:5]}")

        except Exception as e:
            print(f"\n   ❌ {trade_date} 计算失败: {e}")
            db.session.rollback()
            failed_dates.append(trade_date)
            time.sleep(1)
            continue

    print_progress_bar(len(dates), len(dates), prefix="完成", suffix=" " * 30)

    elapsed = time.time() - start_time

    print(f"\n\n✅ 因子计算完成！")
    print(f"   新增记录: {total_records:,}条")
    print(f"   跳过记录: {skipped_records:,}条")
    print(f"   失败日期: {len(failed_dates)}个")
    print(f"   总耗时: {elapsed:.1f}秒 ({elapsed/60:.1f}分钟)")

    if failed_dates:
        print(f"\n⚠️  失败日期列表:")
        for d in failed_dates[:10]:
            print(f"   - {d}")
        if len(failed_dates) > 10:
            print(f"   ... 还有{len(failed_dates)-10}个")

    return total_records

if __name__ == '__main__':
    print("=" * 80)
    print("🚀 批量计算缺失的因子数据")
    print("=" * 80)
    print(f"⏱️  预计耗时: 约2-5分钟")
    print("=" * 80)

    try:
        app = create_app()

        with app.app_context():
            # 第一步：找出缺少因子的股票
            missing_stocks, all_bar_stocks = get_missing_factor_stocks()

            if not missing_stocks:
                print("\n✅ 所有股票的因子数据都已完整！")
                exit(0)

            # 第二步：获取需要计算的日期
            dates = get_all_trade_dates()

            # 第三步：批量计算因子
            records = calculate_factors_for_stocks(missing_stocks, dates)

            # 最终统计
            print(f"\n" + "=" * 80)
            print(f"📊 最终统计")
            print(f"=" * 80)

            # 统计因子数据
            factor_count = db.session.query(FactorData).count()
            factor_stocks = db.session.query(FactorData.ts_code).distinct().count()

            print(f"因子数据总记录: {factor_count:,}条")
            print(f"因子数据股票数: {factor_stocks}只")
            print(f"K线数据股票数: {len(all_bar_stocks)}只")
            print(f"覆盖率: {factor_stocks}/{len(all_bar_stocks)} = {factor_stocks/len(all_bar_stocks)*100:.1f}%")

            print(f"\n✅ 全部完成！")
            print(f"   现在可以用 {factor_stocks} 只股票做因子策略回测了")

    except KeyboardInterrupt:
        print("\n\n⚠️  计算已中断")
        print("💡 提示: 已计算的数据已保存，下次运行会跳过")

    except Exception as e:
        print(f"\n\n❌ 发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

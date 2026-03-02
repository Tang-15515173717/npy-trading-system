"""
补充 reversal_5d 因子数据

reversal_5d = -return_5d

对于所有 return_5d 不为空 但 reversal_5d 为空的记录，直接计算并更新
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from sqlalchemy import text
import pandas as pd

print("=" * 80)
print("补充 reversal_5d 因子数据")
print("=" * 80)
print()

app = create_app()

with app.app_context():
    from utils.database import db

    # 1. 检查当前数据状态
    print("[1/4] 检查当前数据状态...")
    print("-" * 80)

    result = db.session.execute(text("""
        SELECT
            COUNT(CASE WHEN return_5d IS NOT NULL THEN 1 END) as return_5d_count,
            COUNT(CASE WHEN reversal_5d IS NOT NULL THEN 1 END) as reversal_5d_count,
            COUNT(CASE WHEN return_5d IS NOT NULL AND reversal_5d IS NULL THEN 1 END) as missing_count
        FROM factor_data
    """))

    stats = result.fetchone()
    print(f"  return_5d 有数据:        {stats[0]:,} 条")
    print(f"  reversal_5d 有数据:      {stats[1]:,} 条")
    print(f"  需要补充的记录:         {stats[2]:,} 条")
    print()

    if stats[2] == 0:
        print("✅ 数据完整，无需补充")
        sys.exit(0)

    # 2. 显示缺失数据的时间分布
    print("[2/4] 检查缺失数据的时间分布...")
    print("-" * 80)

    result = db.session.execute(text("""
        SELECT
            trade_date,
            COUNT(CASE WHEN return_5d IS NOT NULL AND reversal_5d IS NULL THEN 1 END) as missing_count
        FROM factor_data
        WHERE return_5d IS NOT NULL AND reversal_5d IS NULL
        GROUP BY trade_date
        ORDER BY trade_date DESC
        LIMIT 20
    """))

    print("  最近20天的缺失数据:")
    for row in result:
        print(f"    {row[0]}: {row[1]:>5} 条")
    print()

    # 3. 批量更新 reversal_5d
    print("[3/4] 批量更新 reversal_5d...")
    print("-" * 80)

    # 使用 UPDATE 语句直接计算并更新
    update_sql = """
        UPDATE factor_data
        SET reversal_5d = -return_5d
        WHERE return_5d IS NOT NULL
          AND reversal_5d IS NULL
    """

    result = db.session.execute(text(update_sql))
    db.session.commit()
    updated_count = result.rowcount

    print(f"  ✅ 成功更新 {updated_count:,} 条记录")
    print()

    # 4. 验证更新结果
    print("[4/4] 验证更新结果...")
    print("-" * 80)

    result = db.session.execute(text("""
        SELECT
            COUNT(CASE WHEN return_5d IS NOT NULL THEN 1 END) as return_5d_count,
            COUNT(CASE WHEN reversal_5d IS NOT NULL THEN 1 END) as reversal_5d_count,
            COUNT(CASE WHEN return_5d IS NOT NULL AND reversal_5d IS NULL THEN 1 END) as missing_count
        FROM factor_data
    """))

    stats = result.fetchone()
    print(f"  return_5d 有数据:        {stats[0]:,} 条")
    print(f"  reversal_5d 有数据:      {stats[1]:,} 条")
    print(f"  仍然缺失的记录:         {stats[2]:,} 条")
    print()

    if stats[1] == stats[0]:
        print("✅ reversal_5d 数据补充完成！")
        print("   现在所有有 return_5d 的记录都有 reversal_5d 数据")
    else:
        print(f"⚠️  还有 {stats[2]} 条记录未能更新")

    # 显示一些示例数据
    print()
    print("[示例] 随机查看10条更新后的数据:")
    print("-" * 80)

    sample_df = pd.read_sql_query(text("""
        SELECT ts_code, trade_date, return_5d, reversal_5d
        FROM factor_data
        WHERE reversal_5d IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 10
    """), db.session.bind)

    print(sample_df.to_string(index=False))

    print()
    print("=" * 80)
    print("💡 提示:")
    print("  1. reversal_5d = -return_5d (5日收益率取负)")
    print("  2. 反转因子逻辑：近期下跌的股票(负return)有正reversal(超卖反弹)")
    print("  3. 现在可以使用 reversal_5d 进行回测了")
    print("=" * 80)

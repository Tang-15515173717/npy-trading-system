"""
为所有有K线数据的股票计算因子
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np

print("=" * 60)
print("为所有股票计算因子数据")
print("=" * 60)

engine = create_engine('sqlite:///Users/mac/IdeaProjects/vnpy/database/stock_quant.db')

print("\n[1/3] 检查数据...")

# 获取所有有K线但可能缺少因子的股票
from sqlalchemy import inspect
inspector = inspect(engine)

result = engine.connect().execute(text("""
    SELECT
        b.ts_code,
        COUNT(b.rowid) as bar_count,
        COUNT(f.rowid) as factor_count
    FROM bar_data b
    LEFT JOIN factor_data f ON b.ts_code = f.ts_code AND b.trade_date = f.trade_date
    GROUP BY b.ts_code
    HAVING bar_count > 200
    ORDER BY factor_count ASC
"""))

stocks = result.fetchall()
print(f"✅ 找到 {len(stocks)}只有K线数据的股票")

print(f"\n[2/3] 计算因子数据...")
calculated = 0
skipped = 0

for i, (ts_code, bar_count, factor_count) in stocks[:100]:  # 限制100只
    try:
        print(f"  [{i+1}/{min(100, len(stocks))}] {ts_code}...", end='')

        # 检查是否真的需要计算因子
        result = engine.execute(text("""
            SELECT COUNT(*) FROM factor_data WHERE ts_code = :ts_code
        """), {'ts_code': ts_code})
        actual_factor_count = result.fetchone()[0]

        if actual_factor_count >= bar_count * 0.8:  # 80%的数据已有因子
            print(f" ✅ 已有{actual_factor_count}条，跳过")
            skipped += 1
            continue

        # 获取K线数据
        bars_df = pd.read_sql_query(text("""
            SELECT trade_date, open, high, low, close, vol
            FROM bar_data
            WHERE ts_code = :ts_code AND trade_date >= '20220101'
            ORDER BY trade_date
        """), engine, params={'ts_code': ts_code})

        if len(bars_df) < 200:
            print(f" ❌ 数据不足({len(bars_df)}条)")
            skipped += 1
            continue

        bars_df['trade_date'] = pd.to_datetime(bars_df['trade_date'], format='%Y%m%d')

        # 计算因子
        bars_df['return_1d'] = bars_df['close'].pct_change(1)
        bars_df['return_5d'] = bars_df['close'].pct_change(5)
        bars_df['return_20d'] = bars_df['close'].pct_change(20)
        bars_df['return_60d'] = bars_df['close'].pct_change(60)

        # RSI
        delta = bars_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        bars_df['rsi_14'] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = bars_df['close'].ewm(span=12).mean()
        exp2 = bars_df['close'].ewm(span=26).mean()
        bars_df['macd'] = exp1 - exp2

        # 波动率
        bars_df['volatility_20d'] = bars_df['close'].pct_change().rolling(20).std()

        # 反转
        bars_df['reversal_5d'] = -bars_df['return_5d']

        # 删除NaN
        bars_df = bars_df.dropna(subset=['rsi_14', 'macd'])

        # 保存因子
        added = 0
        for _, row in bars_df.iterrows():
            trade_date = row['trade_date'].strftime('%Y%m%d')

            # 检查是否存在
            existing = engine.execute(text("""
                SELECT id FROM factor_data
                WHERE ts_code = :ts_code AND trade_date = :date
            """), {'ts_code': ts_code, 'date': trade_date})

            if existing.fetchone():
                continue

            engine.execute(text("""
                INSERT INTO factor_data (ts_code, trade_date, return_5d, return_20d, return_60d, rsi_14, macd, volatility_20d, reversal_5d)
                VALUES (:ts_code, :date, :r5d, :r20d, :r60d, :rsi, :macd, :vol, :rev)
            """), {
                'ts_code': ts_code,
                'date': trade_date,
                'r5d': float(row['return_5d']) if not pd.isna(row['return_5d']) else None,
                'r20d': float(row['return_20d']) if not pd.isna(row['return_20d']) else None,
                'r60d': float(row['return_60d']) if not pd.isna(row['return_60d']) else None,
                'rsi': float(row['rsi_14']) if not pd.isna(row['rsi_14']) else None,
                'macd': float(row['macd']) if not pd.isna(row['macd']) else None,
                'vol': float(row['volatility_20d']) if not pd.isna(row['volatility_20d']) else None,
                'rev': float(row['reversal_5d']) if not pd.isna(row['reversal_5d']) else None
            })
            added += 1

        print(f" ✅ ({added}条)")
        calculated += 1

    except Exception as e:
        print(f" ❌ {e}")
        skipped += 1
        continue

print(f"\n[3/3] 完成")
print(f"✅ 计算完成: {calculated}只")
print(f"⊙ 跳过: {skipped}只")

print("\n" + "=" * 60)
print("因子计算完成！现在运行优化后的v2策略回测")
print("=" * 60)

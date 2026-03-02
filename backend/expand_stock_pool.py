"""
扩充股票池 - 从93只扩充到1000只
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.database import db
from models.bar_data import BarData
from models.factor_data import FactorData
from models.stock import Stock
import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# 创建Flask应用上下文
from app import app

# 设置TuShare Token
ts.set_token('c581961ccacd6c2f01c196364402ef122a6a51335354bb01ab24c7a1')
pro = ts.pro_api()

print("=" * 60)
print("扩充股票池计划")
print("=" * 60)

with app.app_context():
    # 1. 获取股票列表
    print("\n[1/5] 获取股票列表...")
    try:
        # 使用stock_basic接口
        stock_list = pro.stock_basic(exchange='', list_status='L')
        print(f"✅ 获取到 {len(stock_list)} 只股票")
    except Exception as e:
        print(f"❌ 获取股票列表失败: {e}")
        # 降级方案：直接使用数据库中的股票
        existing_stocks = db.session.query(Stock.ts_code).all()
        stock_list = [{'ts_code': s.ts_code} for s in existing_stocks]
        print(f"✅ 使用数据库中 {len(stock_list)} 只股票")
except Exception as e:
    print(f"❌ 获取股票列表失败: {e}")
    # 降级方案：直接使用数据库中的股票
    existing_stocks = db.session.query(Stock.ts_code).all()
    stock_list = [{'ts_code': s.ts_code} for s in existing_stocks]
    print(f"✅ 使用数据库中 {len(stock_list)} 只股票")
except Exception as e:
    print(f"❌ ���取股票列表失败: {e}")
    sys.exit(1)

# 2. 筛选沪深300+中证500成分股
print("\n[2/5] 筛选优质股票...")

# 获取沪深300
try:
    hs300 = pro.index_weight(index_code='000300.SH')  # 沪深300
    hs300_codes = hs300['con_code'].str.replace('SH.', '').tolist()
    print(f"✅ 沪深300: {len(hs300_codes)}只")
except:
    hs300_codes = []
    print("⚠️  沪深300获取失败")

# 获取中证500
try:
    zz500 = pro.index_weight(index_code='000905.SH')  # 中证500
    zz500_codes = zz500['con_code'].str.replace('SH.', '').tolist()
    print(f"✅ 中证500: {len(zz500_codes)}只")
except:
    zz500_codes = []
    print("⚠️  中证500获取失败")

# 合并去重
target_stocks = list(set(hs300_codes + zz500_codes))
print(f"✅ 目标股票池: {len(target_stocks)}只")

# 3. 查找已有数据的股票
print("\n[3/5] 检查已有数据...")
existing_bars = db.session.query(BarData.ts_code).distinct().all()
existing_stocks = set([b.ts_code for b in existing_bars])

new_stocks = [s for s in target_stocks if s not in existing_stocks]
print(f"✅ 已有数据: {len(existing_stocks)}只")
print(f"📝 待下载: {len(new_stocks)}只")

if not new_stocks:
    print("\n✅ 所有股票已有数据，无需下载")
    sys.exit(0)

# 4. 下载K线数据（分批处理）
print("\n[4/5] 下载K线数据...")
downloaded_stocks = []
batch_size = 100
start_date = '20220101'
end_date = datetime.now().strftime('%Y%m%d')

for i in range(0, min(len(new_stocks), 500), batch_size):
    batch = new_stocks[i:i+batch_size]

    try:
        print(f"  下载批次 {i//batch_size + 1}: {len(batch)}只股票...", end='')

        for ts_code in batch[:10]:  # 每批只处理10只，避免超时
            try:
                # 转换代码格式：600000.SH -> 600000
                code = ts_code.split('.')[0]

                df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)

                if df.empty:
                    continue

                # 保存数据
                count = 0
                for _, row in df.iterrows():
                    existing = BarData.query.filter_by(
                        ts_code=ts_code,
                        trade_date=row['trade_date']
                    ).first()

                    if existing:
                        continue

                    bar = BarData(
                        ts_code=ts_code,
                        trade_date=row['trade_date'],
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        vol=float(row['vol']),
                        amount=float(row['amount'])
                    )
                    db.session.add(bar)
                    count += 1

                db.session.commit()
                downloaded_stocks.append(ts_code)

            except Exception as e:
                print(f"\n    {ts_code} 失败: {e}")
                continue

        print(f" ✅ ({len(downloaded_stocks)}只)")

    except Exception as e:
        print(f" ❌ 批次失败: {e}")
        db.session.rollback()
        continue

print(f"\n✅ K线数据下载完成: {len(downloaded_stocks)}只")

# 5. 计算因子数据
print("\n[5/5] 计算因子数据...")
stocks_need_factors = [s for s in downloaded_stocks if s not in existing_stocks or
                          BarData.query.filter_by(ts_code=s).count() > 100]

if not stocks_need_factors:
    print("✅ 无需计算因子（已是最新）")
else:
    print(f"  待计算因子: {len(stocks_need_factors)}只")

    # 获取所有有数据的日期
    all_dates = db.session.query(BarData.trade_date).filter(
        BarData.trade_date >= '20220101'
    ).distinct().order_by(BarData.trade_date).all()
    all_dates = [d[0] for d in all_dates]

    factors_calculated = 0

    for ts_code in stocks_need_factors[:50]:  # 限制50只
        try:
            print(f"  计算 {ts_code} 因子...", end='')

            # 获取K线数据
            bars = BarData.query.filter(
                BarData.ts_code == ts_code,
                BarData.trade_date >= '20220101'
            ).order_by(BarData.trade_date).all()

            if len(bars) < 100:
                print(f" ❌ 数据不足({len(bars)}条)")
                continue

            # 转换为DataFrame
            df = pd.DataFrame([{
                'trade_date': b.trade_date,
                'open': b.open,
                'high': b.high,
                'low': b.low,
                'close': b.close,
                'vol': b.vol
            } for b in bars])

            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
            df = df.sort_values('trade_date').reset_index(drop=True)

            # 计算因子
            df['return_1d'] = df['close'].pct_change(1)
            df['return_5d'] = df['close'].pct_change(5)
            df['return_20d'] = df['close'].pct_change(20)
            df['return_60d'] = df['close'].pct_change(60)

            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi_14'] = 100 - (100 / (1 + rs))

            # MACD
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = exp1 - exp2

            # 波动率
            df['volatility_20d'] = df['close'].pct_change().rolling(20).std()

            # 反转
            df['reversal_5d'] = -df['return_5d']

            # 保存因子
            count = 0
            for _, row in df.iterrows():
                if pd.isna(row['rsi_14']) or pd.isna(row['macd']):
                    continue

                trade_date = row['trade_date'].strftime('%Y%m%d')

                # 检查是否已存在
                existing = FactorData.query.filter_by(
                    ts_code=ts_code,
                    trade_date=trade_date
                ).first()

                if existing:
                    # 更新
                    existing.return_5d = float(row['return_5d']) if not pd.isna(row['return_5d']) else None
                    existing.return_20d = float(row['return_20d']) if not pd.isna(row['return_20d']) else None
                    existing.return_60d = float(row['return_60d']) if not pd.isna(row['return_60d']) else None
                    existing.rsi_14 = float(row['rsi_14']) if not pd.isna(row['rsi_14']) else None
                    existing.macd = float(row['macd']) if not pd.isna(row['macd']) else None
                    existing.volatility_20d = float(row['volatility_20d']) if not pd.isna(row['volatility_20d']) else None
                    existing.reversal_5d = float(row['reversal_5d']) if not pd.isna(row['reversal_5d']) else None
                else:
                    factor = FactorData(
                        ts_code=ts_code,
                        trade_date=trade_date,
                        return_5d=float(row['return_5d']) if not pd.isna(row['return_5d']) else None,
                        return_20d=float(row['return_20d']) if not pd.isna(row['return_20d']) else None,
                        return_60d=float(row['return_60d']) if not pd.isna(row['return_60d']) else None,
                        rsi_14=float(row['rsi_14']) if not pd.isna(row['rsi_14']) else None,
                        macd=float(row['macd']) if not pd.isna(row['macd']) else None,
                        volatility_20d=float(row['volatility_20d']) if not pd.isna(row['volatility_20d']) else None,
                        reversal_5d=float(row['reversal_5d']) if not pd.isna(row['reversal_5d']) else None
                    )
                    db.session.add(factor)
                    count += 1

            db.session.commit()
            factors_calculated += 1
            print(f" ✅ ({count}条)")

        except Exception as e:
            print(f" ❌ {e}")
            continue

    print(f"\n✅ 因子计算完成: {factors_calculated}只股票")

print("\n" + "=" * 60)
print("扩充股票池完成！")
print("=" * 60)

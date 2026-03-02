"""
批量因子计算脚本 - StockQuant Pro
为所有历史行情数据计算因子值
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd
import numpy as np
from datetime import datetime
import time
import sys

# 数据库配置
DATABASE_URL = "sqlite:///../../database/stock_quant.db"

# 创建数据库引擎
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def get_trading_dates(session):
    """获取所有交易日"""
    result = session.execute(text("SELECT DISTINCT trade_date FROM bar_data ORDER BY trade_date"))
    return [row[0] for row in result.fetchall()]


def get_stocks(session):
    """获取所有股票"""
    result = session.execute(text("SELECT ts_code FROM stocks WHERE ts_code IS NOT NULL"))
    return [{'ts_code': row[0]} for row in result.fetchall()]


def get_stock_bars(session, ts_code):
    """获取单只股票的所有行情数据"""
    result = session.execute(
        text("SELECT trade_date, close, vol, amount FROM bar_data WHERE ts_code = :ts_code ORDER BY trade_date"),
        {"ts_code": ts_code}
    )
    return {row[0]: {'close': float(row[1] or 0), 'vol': float(row[2] or 0), 'amount': float(row[3] or 0)}
            for row in result.fetchall()}


def calculate_factors_for_stock(bars_dict, trade_date, hist_dates):
    """为单只股票在特定日期计算因子"""
    if trade_date not in bars_dict:
        return None

    # 获取历史数据
    df_data = []
    for d in hist_dates:
        if d in bars_dict:
            df_data.append({
                'trade_date': d,
                'close': bars_dict[d]['close'],
                'vol': bars_dict[d]['vol'],
                'amount': bars_dict[d]['amount']
            })

    if len(df_data) < 60:
        return None

    df = pd.DataFrame(df_data)

    # 验证最新日期
    if df['trade_date'].iloc[-1] != trade_date:
        return None

    factors = {}
    close_t = df['close'].iloc[-1]

    # 收益率因子
    if len(df) >= 6:
        close_t5 = df['close'].iloc[-6]
        if close_t5 > 0:
            factors['return_5d'] = round((close_t - close_t5) / close_t5, 4)

    if len(df) >= 21:
        close_t20 = df['close'].iloc[-21]
        if close_t20 > 0:
            factors['return_20d'] = round((close_t - close_t20) / close_t20, 4)

    if len(df) >= 61:
        close_t60 = df['close'].iloc[-61]
        if close_t60 > 0:
            factors['return_60d'] = round((close_t - close_t60) / close_t60, 4)

    # 波动率因子
    if len(df) >= 21:
        returns = df['close'].pct_change().tail(20)
        std_20d = returns.std()
        factors['volatility_20d'] = round(std_20d * np.sqrt(250), 4) if not pd.isna(std_20d) else None

    # 量比
    if len(df) >= 5:
        avg_vol = df['vol'].iloc[-5:].mean()
        today_vol = df['vol'].iloc[-1]
        factors['volume_ratio'] = round(today_vol / avg_vol, 2) if avg_vol > 0 else None

    # RSI
    if len(df) >= 15:
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rs_value = float(rs.iloc[-1]) if not pd.isna(rs.iloc[-1]) else 50
        factors['rsi_14'] = round(100 - (100 / (1 + rs_value)), 2) if rs_value > 0 else 50

    # MACD
    if len(df) >= 27:
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        macd_series = ema12 - ema26
        signal_series = macd_series.ewm(span=9, adjust=False).mean()
        hist_series = macd_series - signal_series
        factors['macd'] = round(float(macd_series.iloc[-1]), 4)
        factors['macd_signal'] = round(float(signal_series.iloc[-1]), 4)
        factors['macd_hist'] = round(float(hist_series.iloc[-1]), 4)

    return factors if factors else None


def calculate_all_factors():
    """为所有股票和所有交易日计算因子"""
    start_time = time.time()

    session = Session()

    print("=" * 70)
    print("🚀 开始批量计算因子数据（覆盖所有日期）")
    print("=" * 70)

    try:
        # 1. 获取所有股票
        stocks = get_stocks(session)
        print(f"\n📊 共有 {len(stocks)} 只股票需要处理")

        # 2. 获取所有交易日
        trade_dates = get_trading_dates(session)
        print(f"📅 共有 {len(trade_dates)} 个交易日 ({trade_dates[0]} ~ {trade_dates[-1]})")

        print(f"\n⚙️  开始计算...")
        print("=" * 70)

        total_inserted = 0
        total_updated = 0
        total_errors = 0
        total_skipped = 0

        stock_count = 0
        for stock in stocks:
            stock_count += 1
            ts_code = stock['ts_code']

            # 获取该股票的所有行情数据
            bars_dict = get_stock_bars(session, ts_code)

            if not bars_dict:
                continue

            # 获取排序后的日期列表
            stock_dates = sorted(bars_dict.keys())

            # 为每个交易日计算因子（从第61天开始）
            for i, trade_date in enumerate(stock_dates):
                if i < 60:
                    continue

                # 获取最近61天的日期
                hist_dates = stock_dates[i-60:i+1]

                try:
                    factors = calculate_factors_for_stock(bars_dict, trade_date, hist_dates)

                    if not factors:
                        total_skipped += 1
                        continue

                    # 检查是否已存在
                    existing = session.execute(
                        text("SELECT id FROM factor_data WHERE ts_code = :ts_code AND trade_date = :trade_date"),
                        {"ts_code": ts_code, "trade_date": trade_date}
                    ).fetchone()

                    if existing:
                        # 更新
                        set_clauses = [f"{k} = :{k}" for k in factors.keys()]
                        set_clauses.append("updated_at = :now")
                        params = {**factors, "ts_code": ts_code, "trade_date": trade_date, "now": datetime.now()}
                        session.execute(
                            text(f"UPDATE factor_data SET {', '.join(set_clauses)} WHERE ts_code = :ts_code AND trade_date = :trade_date"),
                            params
                        )
                        total_updated += 1
                    else:
                        # 插入
                        columns = ["ts_code", "trade_date", "created_at", "updated_at"] + list(factors.keys())
                        placeholders = [":ts_code", ":trade_date", ":created_at", ":updated_at"] + [f":{k}" for k in factors.keys()]
                        params = {"ts_code": ts_code, "trade_date": trade_date,
                                 "created_at": datetime.now(), "updated_at": datetime.now(), **factors}
                        session.execute(
                            text(f"INSERT INTO factor_data ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"),
                            params
                        )
                        total_inserted += 1

                    # 每500条提交一次
                    if (total_inserted + total_updated) % 500 == 0:
                        session.commit()
                        print(f"  📈 已处理 {total_inserted + total_updated} 条...")

                except Exception as e:
                    total_errors += 1
                    if total_errors <= 5:
                        print(f"  ❌ 错误 [{ts_code}, {trade_date}]: {e}")

            # 每20只股票打印进度
            if stock_count % 20 == 0 or stock_count == len(stocks):
                print(f"  ✅ [{stock_count}/{len(stocks)}] {ts_code} 完成, 累计: 新增{total_inserted}, 更新{total_updated}")

        # 提交剩余数据
        session.commit()

        # 统计结果
        elapsed = time.time() - start_time

        # 验证结果
        result = session.execute(text("SELECT COUNT(*) FROM factor_data")).fetchone()
        total_records = result[0] if result else 0

        result = session.execute(text("SELECT COUNT(DISTINCT trade_date) FROM factor_data")).fetchone()
        trading_days = result[0] if result else 0

        result = session.execute(text("SELECT COUNT(DISTINCT ts_code) FROM factor_data")).fetchone()
        stocks_with_data = result[0] if result else 0

        print("\n" + "=" * 70)
        print("✅ 批量因子计算完成!")
        print(f"⏱️  总耗时: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分钟)")
        print(f"📊 新增记录: {total_inserted:,}")
        print(f"🔄 更新记录: {total_updated:,}")
        print(f"❌ 错误数量: {total_errors}")
        print(f"⏭️  跳过数量: {total_skipped:,}")
        print(f"\n📋 验证结果:")
        print(f"   - factor_data 总记录: {total_records:,}")
        print(f"   - 有数据的交易日: {trading_days}")
        print(f"   - 有数据的股票: {stocks_with_data}")
        print("=" * 70)

    finally:
        session.close()


if __name__ == "__main__":
    calculate_all_factors()

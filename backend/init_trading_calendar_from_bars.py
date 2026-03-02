"""
从现有K线数据初始化交易日历（备用方案）
使用已有K线数据中的日期作为交易日，周末/节假日作为非交易日
"""
import os
import sys
import sqlite3
from datetime import datetime, timedelta

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stock_quant.db")


def is_weekend(date_str):
    """判断是否是周末"""
    date_obj = datetime.strptime(date_str, "%Y%m%d")
    return date_obj.weekday() >= 5  # 5=周六, 6=周日


def init_from_bar_data(start_date="20240101", end_date="20271231"):
    """从K线数据初始化交易日历"""
    print(f'📡 从K线数据初始化交易日历 ({start_date} ~ {end_date})...')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 从K线数据中提取所有交易日期
    print('📊 从K线数据提取交易日...')
    cursor.execute("""
        SELECT DISTINCT trade_date
        FROM bar_data
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, (start_date, end_date))

    trading_dates = [row[0] for row in cursor.fetchall()]
    print(f'   找到 {len(trading_dates)} 个交易日')

    if len(trading_dates) == 0:
        print('❌ 没有找到K线数据，请先下载K线数据')
        conn.close()
        return False

    # 2. 生成日期范围内的所有日期
    print('📅 生成完整日期列表...')
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")

    all_dates = []
    current = start
    while current <= end:
        all_dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)

    print(f'   共 {len(all_dates)} 天')

    # 3. 判断每个日期是否为交易日
    trading_set = set(trading_dates)
    added = 0
    updated = 0

    print('💾 写入交易日历...')
    for date_str in all_dates:
        is_trading = date_str in trading_set
        is_weekend_flag = is_weekend(date_str)
        is_holiday = (not is_trading) and (not is_weekend_flag)

        # 检查记录是否存在
        cursor.execute("SELECT cal_date FROM trading_calendar WHERE cal_date = ?", (date_str,))
        existing = cursor.fetchone()

        if existing:
            # 更新
            updated += 1
            cursor.execute("""
                UPDATE trading_calendar
                SET is_trading_day = ?, is_weekend = ?, is_holiday = ?, updated_at = datetime('now')
                WHERE cal_date = ?
            """, (is_trading, is_weekend_flag, is_holiday, date_str))
        else:
            # 插入
            added += 1
            holiday_name = "节假日" if is_holiday else None
            cursor.execute("""
                INSERT INTO trading_calendar (cal_date, is_trading_day, is_weekend, is_holiday, holiday_name, exchange, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'SSE', datetime('now'), datetime('now'))
            """, (date_str, is_trading, is_weekend_flag, is_holiday, holiday_name))

    conn.commit()
    conn.close()

    print(f'✅ 初始化成功！新增{added}条，更新{updated}条')
    print(f'   交易日: {len(trading_dates)}天')
    print(f'   非交易日: {len(all_dates) - len(trading_dates)}天')

    return True


def get_stats():
    """获取统计信息"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 总记录数
    cursor.execute("SELECT COUNT(*) FROM trading_calendar")
    total = cursor.fetchone()[0]

    # 交易日数
    cursor.execute("SELECT COUNT(*) FROM trading_calendar WHERE is_trading_day = 1")
    trading_days = cursor.fetchone()[0]

    # 非交易日数
    non_trading_days = total - trading_days

    # 周末数
    cursor.execute("SELECT COUNT(*) FROM trading_calendar WHERE is_weekend = 1")
    weekends = cursor.fetchone()[0]

    # 节假日数
    cursor.execute("SELECT COUNT(*) FROM trading_calendar WHERE is_holiday = 1")
    holidays = cursor.fetchone()[0]

    # 日期范围
    cursor.execute("SELECT MIN(cal_date), MAX(cal_date) FROM trading_calendar")
    min_date, max_date = cursor.fetchone()

    conn.close()

    return {
        'total': total,
        'trading_days': trading_days,
        'non_trading_days': non_trading_days,
        'weekends': weekends,
        'holidays': holidays,
        'date_range': {'earliest': min_date, 'latest': max_date}
    }


def check_dates():
    """检查一些关键日期"""
    print('\n📊 检查关键日期...')

    test_dates = [
        ('20250210', '春节假期'),
        ('20250205', '工作日'),
        ('20250208', '周六'),
        ('20250209', '周日'),
    ]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for date, desc in test_dates:
        cursor.execute("""
            SELECT is_trading_day, is_weekend, is_holiday, holiday_name
            FROM trading_calendar
            WHERE cal_date = ?
        """, (date,))

        result = cursor.fetchone()
        if result:
            is_trading, is_weekend, is_holiday, holiday_name = result
            if is_trading:
                status = '✅ 交易日'
            elif is_weekend:
                status = '❌ 非交易日(周末)'
            elif is_holiday:
                status = f'❌ 非交易日({holiday_name or "节假日"})'
            else:
                status = '❌ 非交易日'
            print(f'   {date} ({desc}): {status}')
        else:
            print(f'   {date} ({desc}): ❓ 无记录')

    conn.close()


def main():
    # 从K线数据初始化（2024-2027）
    if not init_from_bar_data('20240101', '20271231'):
        return

    # 获取统计
    print('\n📈 交易日历统计:')
    stats = get_stats()
    for key, value in stats.items():
        if key != 'date_range':
            print(f'   {key}: {value}')
        else:
            print(f'   日期范围: {value["earliest"]} ~ {value["latest"]}')

    # 检查一些关键日期
    check_dates()

    print('\n✅ 交易日历初始化完成！')


if __name__ == '__main__':
    main()

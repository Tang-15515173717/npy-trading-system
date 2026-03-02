"""
数据库迁移：创建 trading_calendar 表
运行方式：cd backend && python init_trading_calendar.py
"""
import sqlite3
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stock_quant.db")


def migrate():
    """创建 trading_calendar 表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查表是否已存在
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='trading_calendar'
    """)
    exists = cursor.fetchone()

    if exists:
        print("ℹ️  trading_calendar 表已存在，跳过创建")
    else:
        print("📊 正在创建 trading_calendar 表...")
        cursor.execute("""
            CREATE TABLE trading_calendar (
                cal_date VARCHAR(8) PRIMARY KEY NOT NULL,
                is_trading_day BOOLEAN NOT NULL DEFAULT 1,
                is_weekend BOOLEAN DEFAULT 0,
                is_holiday BOOLEAN DEFAULT 0,
                holiday_name VARCHAR(50),
                exchange VARCHAR(10) DEFAULT 'SSE',
                created_at DATETIME,
                updated_at DATETIME
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX idx_trading_calendar_is_trading
            ON trading_calendar(is_trading_day)
        """)
        cursor.execute("""
            CREATE INDEX idx_trading_calendar_exchange
            ON trading_calendar(exchange)
        """)

        conn.commit()
        print("✅ trading_calendar 表创建成功")

        # 显示表结构
        print("\n📋 trading_calendar 表结构:")
        cursor.execute("PRAGMA table_info(trading_calendar)")
        columns = cursor.fetchall()
        for col in columns:
            col_id, name, type_, notnull, default, pk = col
            pk_str = " (PK)" if pk else ""
            null_str = "NULL" if not notnull else "NOT NULL"
            print(f"  - {name}: {type_} {null_str}{pk_str}")

    conn.close()
    print("\n✅ 迁移完成")


if __name__ == "__main__":
    migrate()

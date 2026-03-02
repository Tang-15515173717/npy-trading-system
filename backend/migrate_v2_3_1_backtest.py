"""
数据库迁移脚本 v2.3.1 - 支持因子打分回测模式
将 backtest_tasks 表的 strategy_id 和 strategy_name 字段改为可空
"""
import sqlite3
import os
from datetime import datetime

def migrate_backtest_tasks():
    print("=" * 60)
    print("数据库迁移 v2.3.1 - 支持因子打分回测模式")
    print("=" * 60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 获取数据库路径
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'stock_quant.db')
    print(f"\n数据库路径: {db_path}")

    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. 检查当前表结构
        print("\n1️⃣ 检查当前表结构...")
        cursor.execute("PRAGMA table_info(backtest_tasks)")
        columns = cursor.fetchall()
        print(f"当前 backtest_tasks 表结构:")
        for col in columns:
            print(f"  - {col[1]}: {col[2]} (nullable: {not col[3]})")

        # 2. 检查 strategy_id 是否为 NOT NULL
        cursor.execute("PRAGMA table_info(backtest_tasks)")
        columns_info = {row[1]: row for row in cursor.fetchall()}
        strategy_id_info = columns_info.get('strategy_id')
        strategy_name_info = columns_info.get('strategy_name')

        # PRAGMA 返回: (cid, name, type, notnull, dflt_value, pk)
        # notnull=1 表示 NOT NULL，notnull=0 表示可以为 NULL
        if strategy_id_info and strategy_id_info[3] == 1:  # notnull == 1 表示 NOT NULL
            print("\n2️⃣ 检测到 strategy_id 为 NOT NULL，需要迁移...")

            # SQLite 不支持直接修改列为 nullable，需要重建表
            print("\n3️⃣ 开始重建表...")

            # 3. 创建新表
            cursor.execute("""
                CREATE TABLE backtest_tasks_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id VARCHAR(50) UNIQUE NOT NULL,
                    strategy_id INTEGER,
                    strategy_name VARCHAR(100),
                    factor_combo_id INTEGER,
                    stocks TEXT NOT NULL,
                    start_date VARCHAR(8) NOT NULL,
                    end_date VARCHAR(8) NOT NULL,
                    initial_capital NUMERIC(15, 2) DEFAULT 1000000,
                    commission NUMERIC(6, 6) DEFAULT 0.0003,
                    slippage NUMERIC(5, 2) DEFAULT 0.01,
                    benchmark VARCHAR(20),
                    status VARCHAR(20) DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    result TEXT,
                    error_msg TEXT,
                    started_at DATETIME,
                    completed_at DATETIME,
                    created_at DATETIME,
                    scoring_config_id INTEGER,
                    signal_strategy_id INTEGER
                )
            """)
            print("✅ 创建新表 backtest_tasks_new")

            # 4. 复制数据
            print("\n4️⃣ 迁移数据...")
            cursor.execute("""
                INSERT INTO backtest_tasks_new
                SELECT * FROM backtest_tasks
            """)
            affected_rows = cursor.rowcount
            print(f"✅ 迁移了 {affected_rows} 条记录")

            # 5. 删除旧表
            print("\n5️⃣ 删除旧表...")
            cursor.execute("DROP TABLE backtest_tasks")
            print("✅ 删除旧表 backtest_tasks")

            # 6. 重命名新表
            print("\n6️⃣ 重命名新表...")
            cursor.execute("ALTER TABLE backtest_tasks_new RENAME TO backtest_tasks")
            print("✅ 重命名为 backtest_tasks")

            # 7. 重建索引
            print("\n7️⃣ 重建索引...")
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_backtest_tasks_task_id ON backtest_tasks(task_id)",
                "CREATE INDEX IF NOT EXISTS idx_backtest_tasks_strategy_id ON backtest_tasks(strategy_id)",
                "CREATE INDEX IF NOT EXISTS idx_backtest_tasks_factor_combo_id ON backtest_tasks(factor_combo_id)",
                "CREATE INDEX IF NOT EXISTS idx_backtest_tasks_status ON backtest_tasks(status)",
            ]
            for idx_sql in indexes:
                cursor.execute(idx_sql)
            print("✅ 索引重建完成")

            # 8. 验证新表结构
            print("\n8️⃣ 验证新表结构...")
            cursor.execute("PRAGMA table_info(backtest_tasks)")
            new_columns = cursor.fetchall()
            print("✅ 新表结构:")
            for col in new_columns:
                if col[1] in ['strategy_id', 'strategy_name']:
                    print(f"  📌 {col[1]}: {col[2]} (nullable: {not col[3]}) ✓")

        else:
            print("\n✅ strategy_id 已经是可空字段，无需迁移")

        # 提交更改
        conn.commit()
        print("\n" + "=" * 60)
        print("✅ 数据库迁移完成！")
        print("=" * 60)

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_backtest_tasks()

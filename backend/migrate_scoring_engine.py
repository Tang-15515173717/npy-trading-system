"""
数据库迁移：为 backtest_tasks 表添加 scoring_engine_id 字段。
运行方式：cd backend && python migrate_scoring_engine.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stock_quant.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查列是否已存在
    cursor.execute("PRAGMA table_info(backtest_tasks)")
    columns = [col[1] for col in cursor.fetchall()]

    if "scoring_engine_id" not in columns:
        cursor.execute("ALTER TABLE backtest_tasks ADD COLUMN scoring_engine_id TEXT")
        print("✅ 已添加 scoring_engine_id 列")
    else:
        print("ℹ️  scoring_engine_id 列已存在，跳过")

    conn.commit()
    conn.close()
    print("✅ 迁移完成")

if __name__ == "__main__":
    migrate()

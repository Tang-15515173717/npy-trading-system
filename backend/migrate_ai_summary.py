"""
数据库迁移：为 backtest_tasks 表添加 AI 总结字段
- ai_summary: TEXT 存储 AI 生成的 markdown 总结
- ai_summary_at: DATETIME 记录生成时间
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

    added = []

    if "ai_summary" not in columns:
        cursor.execute("ALTER TABLE backtest_tasks ADD COLUMN ai_summary TEXT")
        added.append("ai_summary")

    if "ai_summary_at" not in columns:
        cursor.execute("ALTER TABLE backtest_tasks ADD COLUMN ai_summary_at DATETIME")
        added.append("ai_summary_at")

    conn.commit()
    conn.close()

    if added:
        print(f"✅ 迁移成功，新增字段：{', '.join(added)}")
    else:
        print("ℹ️  字段已存在，无需迁移")


if __name__ == "__main__":
    migrate()

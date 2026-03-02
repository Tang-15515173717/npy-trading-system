import sqlite3
from flask import Flask
from config import config
import os

def migrate_db_schema():
    print("开始检查数据库表结构...")
    
    # 获取数据库路径
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'stock_quant.db')
    print(f"Database Path: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取 factor_data 表的所有列
    cursor.execute("PRAGMA table_info(factor_data)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"现有列: {columns}")
    
    # 需要添加的列
    new_columns = [
        ('macd_signal', 'REAL'),
        ('macd_hist', 'REAL'),
        ('beta', 'REAL'),
        ('rsi_14', 'REAL')
        # 其他列如果需要也可以加，目前只解决报错的
    ]
    
    for col_name, col_type in new_columns:
        if col_name not in columns:
            try:
                print(f"正在添加列: {col_name}...")
                cursor.execute(f"ALTER TABLE factor_data ADD COLUMN {col_name} {col_type}")
                print(f"✅ 添加成功: {col_name}")
            except Exception as e:
                print(f"❌ 添加失败 {col_name}: {e}")
        else:
            print(f"ℹ️  列已存在: {col_name}")
            
    conn.commit()
    conn.close()
    print("迁移完成！")

if __name__ == "__main__":
    migrate_db_schema()

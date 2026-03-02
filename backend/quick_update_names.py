"""
快速更新股票名称 - 简化版
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tushare as ts
import sqlite3

# 配置
TOKEN = "c581961ccacd6c2f01c196364402ef122a6a51335354bb01ab24c7a1"
DB_PATH = "/Users/mac/IdeaProjects/vnpy/database/stock_quant.db"

print("=" * 80)
print("🔄 快速更新股票名称")
print("=" * 80)

# 初始化TuShare
ts.set_token(TOKEN)
pro = ts.pro_api()

# 连接数据库
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 获取需要更新的股票
cursor.execute("SELECT ts_code FROM stocks WHERE name = ts_code")
stocks_to_update = [row[0] for row in cursor.fetchall()]

print(f"📊 需要更新: {len(stocks_to_update)} 只")
print()

success = 0
failed = 0

for idx, ts_code in enumerate(stocks_to_update, 1):
    try:
        print(f"[{idx}/{len(stocks_to_update)}] {ts_code}...", end=' ', flush=True)
        
        # 获取股票信息
        df = pro.stock_basic(ts_code=ts_code, fields='ts_code,name')
        
        if df.empty:
            print("❌ 未找到")
            failed += 1
            continue
        
        name = df.iloc[0]['name']
        
        # 更新数据库
        cursor.execute("UPDATE stocks SET name = ? WHERE ts_code = ?", (name, ts_code))
        conn.commit()
        
        print(f"✅ {name}")
        success += 1
        
        # 限速
        if idx % 10 == 0:
            import time
            time.sleep(3)
        
    except Exception as e:
        print(f"❌ {str(e)[:30]}")
        failed += 1
        conn.rollback()

conn.close()

print()
print("=" * 80)
print(f"✅ 成功: {success} 只")
print(f"❌ 失败: {failed} 只")
print("=" * 80)
print("\n✅ 完成！刷新前端页面即可")

"""
批量更新所有股票名称 - 一次性获取全部
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
print("🔄 批量更新股票名称（一次性获取全部）")
print("=" * 80)

# 初始化TuShare
ts.set_token(TOKEN)
pro = ts.pro_api()

# 一次性获取所有A股基本信息（不传ts_code参数）
print("\n📊 正在获取A股市场所有股票信息...")
try:
    df = pro.stock_basic(
        exchange='',
        list_status='L',
        fields='ts_code,name,area,industry,market,list_date'
    )
    print(f"✅ 获取到 {len(df)} 只股票信息")
except Exception as e:
    print(f"❌ TuShare API调用失败: {str(e)}")
    print("\n⚠️  使用备用方案：从已有的18只扩展...")
    # 如果失败，至少更新已有的18只
    df = None

if df is not None:
    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取数据库中的股票列表
    cursor.execute("SELECT ts_code FROM stocks")
    db_stocks = {row[0] for row in cursor.fetchall()}
    
    print(f"📊 数据库中有 {len(db_stocks)} 只股票需要更新名称")
    print()
    
    success = 0
    skipped = 0
    not_found = 0
    
    for ts_code in db_stocks:
        # 从DataFrame中查找对应股票
        stock_info = df[df['ts_code'] == ts_code]
        
        if stock_info.empty:
            print(f"⚠️  {ts_code} - 未在TuShare找到")
            not_found += 1
            continue
        
        row = stock_info.iloc[0]
        name = row['name']
        area = row['area'] if row['area'] and str(row['area']) != 'nan' else None
        industry = row['industry'] if row['industry'] and str(row['industry']) != 'nan' else None
        market = row['market'] if row['market'] and str(row['market']) != 'nan' else None
        list_date = row['list_date'] if row['list_date'] and str(row['list_date']) != 'nan' else None
        
        try:
            # 更新数据库
            cursor.execute("""
                UPDATE stocks 
                SET name = ?, area = ?, industry = ?, market = ?, list_date = ?
                WHERE ts_code = ?
            """, (name, area, industry, market, list_date, ts_code))
            conn.commit()
            
            print(f"✅ {ts_code:12} → {name}")
            success += 1
            
        except Exception as e:
            print(f"❌ {ts_code} - 数据库更新失败: {str(e)[:30]}")
            conn.rollback()
    
    conn.close()
    
    print()
    print("=" * 80)
    print("📊 更新完成统计")
    print("=" * 80)
    print(f"✅ 成功更新: {success} 只")
    print(f"⚠️  未找到: {not_found} 只")
    print(f"⏭️  跳过: {skipped} 只")
    print("=" * 80)
    
    # 验证
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE name != ts_code")
    updated_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM stocks")
    total_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n✅ 数据库状态:")
    print(f"   已更新名称: {updated_count}/{total_count} ({updated_count/total_count*100:.1f}%)")
    print()
    print("✅ 完成！刷新前端页面即可看到真实股票名称")
    print()

else:
    print("\n❌ 无法获取股票信息，请稍后重试")

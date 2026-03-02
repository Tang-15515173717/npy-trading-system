"""
同步股票基本信息到数据库
从bar_data表提取所有ts_code，获取股票基本信息并写入stocks表
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models.stock import Stock
from models.bar_data import BarData
from utils.database import db

def sync_stock_info():
    """同步股票基本信息"""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("🔄 同步股票基本信息到数据库")
        print("=" * 80)
        
        # 1. 获取bar_data中所有不同的ts_code
        print("\n📊 步骤1：查询已下载数据的股票代码...")
        ts_codes = db.session.query(BarData.ts_code).distinct().all()
        ts_codes = [code[0] for code in ts_codes]
        
        print(f"✅ 找到 {len(ts_codes)} 只股票有K线数据")
        print(f"   代码：{', '.join(ts_codes[:10])}{'...' if len(ts_codes) > 10 else ''}")
        
        # 2. 检查stocks表已有数据
        print("\n📊 步骤2：检查stocks表现有数据...")
        existing_stocks = Stock.query.all()
        existing_codes = {stock.ts_code for stock in existing_stocks}
        
        print(f"✅ stocks表已有 {len(existing_stocks)} 条记录")
        
        # 3. 需要新增的股票
        new_codes = [code for code in ts_codes if code not in existing_codes]
        
        if not new_codes:
            print("\n✅ 所有股票信息已同步，无需操作")
            return
        
        print(f"\n📊 步骤3：需要新增 {len(new_codes)} 只股票信息")
        
        # 4. 简单映射：使用代码作为名称
        print("\n🔄 开始创建股票记录...")
        
        success_count = 0
        failed_count = 0
        
        for idx, ts_code in enumerate(new_codes, 1):
            try:
                print(f"[{idx}/{len(new_codes)}] 处理 {ts_code}...", end=' ')
                
                # 解析交易所和股票代码
                if ts_code.endswith('.SH'):
                    exchange = 'SSE'
                    symbol = ts_code.replace('.SH', '')
                elif ts_code.endswith('.SZ'):
                    exchange = 'SZSE'
                    symbol = ts_code.replace('.SZ', '')
                else:
                    exchange = 'OTHER'
                    symbol = ts_code
                
                # 使用ts_code作为名称（后续可以通过API更新）
                name = ts_code
                
                # 创建股票记录
                stock = Stock(
                    ts_code=ts_code,
                    symbol=symbol,
                    name=name,
                    exchange=exchange,
                    status='active'
                )
                
                db.session.add(stock)
                db.session.commit()
                
                success_count += 1
                print(f"✅")
                
            except Exception as e:
                failed_count += 1
                db.session.rollback()
                print(f"❌ {str(e)[:30]}")
        
        # 5. 完成统计
        print("\n" + "=" * 80)
        print("📊 同步完成统计")
        print("=" * 80)
        print(f"✅ 成功同步: {success_count} 只")
        print(f"❌ 失败: {failed_count} 只")
        print(f"📊 stocks表总记录: {len(existing_stocks) + success_count}")
        print("=" * 80)
        print()
        print("✅ 同步完成！现在可以在前端页面看到股票列表了")
        print()

if __name__ == '__main__':
    try:
        sync_stock_info()
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()

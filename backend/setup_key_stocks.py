"""
标记沪深300重点股票并下载完整历史数据
- 从AKShare获取沪深300成分股列表
- 标记为 stock_type='key'
- 下载这些股票的完整历史数据（最近2年）
- 标记 has_full_data=True
"""
import sys
sys.path.insert(0, '/Users/mac/IdeaProjects/vnpy/backend')

from app import create_app
from models.stock import Stock
from models.bar_data import BarData
from utils.database import db
import akshare as ak
from datetime import datetime, timedelta
from time import sleep

def get_hs300_stocks():
    """获取沪深300成分股列表"""
    print("\n" + "="*80)
    print("📥 获取沪深300成分股列表...")
    print("="*80)
    
    try:
        # 使用AKShare获取沪深300成分股
        df = ak.index_stock_cons(symbol="000300")
        
        if df is None or df.empty:
            print("❌ 未获取到数据")
            return []
        
        print(f"✅ 获取到 {len(df)} 只成分股")
        
        # 转换代码格式
        stocks = []
        for _, row in df.iterrows():
            code = row['品种代码']
            # 转换为标准格式
            if code.startswith('6'):
                ts_code = f"{code}.SH"
            elif code.startswith(('0', '3')):
                ts_code = f"{code}.SZ"
            else:
                continue
            stocks.append(ts_code)
        
        return stocks
    
    except Exception as e:
        print(f"❌ 获取失败：{e}")
        import traceback
        traceback.print_exc()
        return []

def mark_key_stocks(stock_codes):
    """标记重点股票"""
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*80)
        print(f"🏷️  标记 {len(stock_codes)} 只重点股票...")
        print("="*80)
        
        marked_count = 0
        not_found_count = 0
        
        for ts_code in stock_codes:
            try:
                stock = Stock.query.filter_by(ts_code=ts_code).first()
                
                if stock:
                    stock.stock_type = 'key'
                    marked_count += 1
                else:
                    print(f"   ⚠️  未找到：{ts_code}")
                    not_found_count += 1
                
                if marked_count % 50 == 0:
                    db.session.commit()
                    print(f"   进度：{marked_count}/{len(stock_codes)}")
            
            except Exception as e:
                print(f"   ❌ 标记 {ts_code} 失败：{e}")
                continue
        
        db.session.commit()
        
        print(f"\n✅ 标记完成！")
        print(f"   成功：{marked_count} 只")
        print(f"   未找到：{not_found_count} 只")
        
        return marked_count

def download_key_stocks_data(limit=None):
    """下载重点股票的完整历史数据（最近2年）"""
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*80)
        print("📥 下载重点股票历史数据...")
        print("="*80)
        
        # 查询所有重点股票
        if limit:
            stocks = Stock.query.filter_by(stock_type='key').limit(limit).all()
            print(f"⚠️  测试模式：只下载前 {limit} 只")
        else:
            stocks = Stock.query.filter_by(stock_type='key').all()
        
        print(f"股票总数：{len(stocks)}")
        
        # 计算日期范围（最近2年）
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=730)).strftime('%Y%m%d')
        
        print(f"时间范围：{start_date} ~ {end_date} (2年)")
        
        success_count = 0
        fail_count = 0
        
        for idx, stock in enumerate(stocks, 1):
            try:
                print(f"\n[{idx}/{len(stocks)}] {stock.name} ({stock.ts_code})")
                
                symbol = stock.ts_code.split('.')[0]
                
                # 使用AKShare获取日K线
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                
                if df is None or df.empty:
                    print(f"   ⚠️  无数据")
                    fail_count += 1
                    continue
                
                # 保存到数据库
                saved = 0
                for _, row in df.iterrows():
                    try:
                        trade_date = row['日期'].replace('-', '')
                        
                        # 检查是否已存在
                        exists = BarData.query.filter_by(
                            ts_code=stock.ts_code,
                            trade_date=trade_date
                        ).first()
                        
                        if exists:
                            continue
                        
                        bar = BarData(
                            ts_code=stock.ts_code,
                            trade_date=trade_date,
                            open=float(row['开盘']),
                            high=float(row['最高']),
                            low=float(row['最低']),
                            close=float(row['收盘']),
                            vol=int(row['成交量']),
                            amount=float(row['成交额']) if '成交额' in row else None
                        )
                        db.session.add(bar)
                        saved += 1
                    
                    except Exception as e:
                        print(f"   ❌ 保存K线失败：{e}")
                        continue
                
                # 标记为有完整数据
                if saved > 0:
                    stock.has_full_data = True
                
                db.session.commit()
                print(f"   ✅ 保存 {saved} 条K线，标记为完整数据")
                success_count += 1
                
                # 礼貌性延迟
                if idx % 5 == 0:
                    sleep(1)
                
            except Exception as e:
                print(f"   ❌ 下载失败：{e}")
                db.session.rollback()
                fail_count += 1
                
                # 如果连续失败太多，等待更长时间
                if fail_count > 3:
                    print("   ⏳ 等待5秒...")
                    sleep(5)
                    fail_count = 0  # 重置失败计数
                
                continue
        
        print("\n" + "="*80)
        print("📊 下载完成统计")
        print("="*80)
        print(f"成功：{success_count} 只")
        print(f"失败：{fail_count} 只")
        print(f"总计：{len(stocks)} 只")

if __name__ == '__main__':
    print("\n🚀 沪深300重点股票标记与数据下载")
    print("="*80)
    
    # 第一步：获取沪深300成分股
    hs300_codes = get_hs300_stocks()
    
    if not hs300_codes:
        print("\n❌ 未获取到沪深300成分股列表")
        exit(1)
    
    # 第二步：标记重点股票
    marked = mark_key_stocks(hs300_codes)
    
    if marked > 0:
        # 第三步：下载历史数据
        print("\n" + "="*80)
        print("是否下载重点股票的完整历史数据（2年）？")
        print("="*80)
        print(f"共 {marked} 只股票需要下载")
        print("\n选项：")
        print("1. 下载所有重点股票数据（推荐，需30-60分钟）")
        print("2. 测试模式：只下载前10只")
        print("3. 跳过数据下载")
        
        choice = input("\n请选择 (1/2/3): ").strip()
        
        if choice == '1':
            print("\n⏳ 开始下载所有重点股票数据...")
            download_key_stocks_data()
        elif choice == '2':
            print("\n⏳ 测试模式：下载前10只...")
            download_key_stocks_data(limit=10)
        else:
            print("\n✅ 跳过数据下载")
    
    print("\n" + "="*80)
    print("🎉 全部完成！")
    print("="*80)

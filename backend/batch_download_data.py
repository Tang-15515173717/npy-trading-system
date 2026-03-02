"""
批量下载股票数据脚本
支持断点续传、智能限速、进度显示
"""
import sys
import os
import time
from datetime import datetime

# 添加backend路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from services.data_service import DataService

# A股市场常用股票列表（精选100只）
STOCK_LIST = [
    # 银行板块
    '601398.SH', '601939.SH', '601288.SH', '600036.SH', '601328.SH',
    '600000.SH', '600015.SH', '600016.SH', '601988.SH', '601818.SH',
    '000001.SZ', '002142.SZ',
    
    # 证券板块
    '600030.SH', '601688.SH', '600999.SH', '600958.SH', '601788.SH',
    
    # 保险板块
    '601318.SH', '601601.SH', '601336.SH',
    
    # 白酒板块
    '600519.SH', '000858.SZ', '000568.SZ', '000596.SZ', '603369.SH',
    
    # 医药板块
    '600276.SH', '000661.SZ', '002044.SZ', '300760.SZ', '600436.SH',
    '002007.SZ', '300015.SZ', '603259.SH', '000538.SZ',
    
    # 科技板块
    '600570.SH', '002415.SZ', '000725.SZ', '002230.SZ', '300059.SZ',
    '002475.SZ', '603986.SH', '688012.SH', '688981.SH',
    
    # 新能源汽车
    '002594.SZ', '300750.SZ', '600741.SH', '603799.SH', '002129.SZ',
    
    # 光伏板块
    '601012.SH', '688005.SH', '601865.SH', '300274.SZ', '002459.SZ',
    
    # 芯片半导体
    '688981.SH', '603501.SH', '002371.SZ', '300782.SZ', '688008.SH',
    
    # 房地产
    '000002.SZ', '001979.SZ', '600048.SH', '000069.SZ',
    
    # 家电板块
    '000333.SZ', '600690.SH', '000651.SZ', '002050.SZ',
    
    # 食品饮料
    '600887.SH', '603288.SH', '002568.SZ', '600809.SH',
    
    # 石油化工
    '601857.SH', '600028.SH', '000301.SZ', '601233.SH',
    
    # 钢铁有色
    '601899.SH', '600019.SH', '000878.SZ', '601600.SH',
    
    # 煤炭电力
    '601088.SH', '601898.SH', '600011.SH', '600900.SH',
    
    # 航空航天
    '600029.SH', '601021.SH', '600893.SH',
    
    # 互联网
    '300059.SZ', '002024.SZ', '300033.SZ',
    
    # 其他蓝筹
    '601919.SH', '601888.SH', '601668.SH', '600585.SH',
    '600104.SH', '600690.SH', '601111.SH', '601166.SH'
]

def print_progress_bar(current, total, prefix='', suffix='', length=50):
    """打印进度条"""
    percent = f"{100 * (current / float(total)):.1f}"
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='', flush=True)
    if current == total:
        print()

def batch_download_data():
    """批量下载股票数据"""
    app = create_app()
    
    with app.app_context():
        data_service = DataService()
        
        print("=" * 80)
        print("🚀 StockQuant Pro - 批量数据下载")
        print("=" * 80)
        print(f"📊 计划下载股票数量: {len(STOCK_LIST)}")
        print(f"📅 数据时间范围: 2023-01-01 ~ 2026-01-29")
        print(f"⏱️  预计耗时: {len(STOCK_LIST) * 2}秒 (约{len(STOCK_LIST) * 2 // 60}分钟)")
        print("=" * 80)
        print()
        
        # 统计信息
        success_count = 0
        failed_count = 0
        skipped_count = 0
        total_records = 0
        failed_stocks = []
        
        start_time = time.time()
        
        # 批量下载
        for idx, ts_code in enumerate(STOCK_LIST, 1):
            try:
                # 显示当前进度
                prefix = f"[{idx}/{len(STOCK_LIST)}]"
                suffix = f"正在下载: {ts_code}"
                print_progress_bar(idx - 1, len(STOCK_LIST), prefix=prefix, suffix=suffix)
                
                # 调用下载服务（注意：API需要列表格式）
                result = data_service.download_stock_data(
                    ts_codes=[ts_code],  # 传入列表
                    start_date='20230101',
                    end_date='20260129',
                    freq='D'
                )
                
                # 统计结果（批量API返回格式）
                if result.get('success_count', 0) > 0:
                    success_count += 1
                    stored = result.get('stored_records', 0)
                    total_records += stored
                    status = f"✅ {ts_code}: 新增{stored}条"
                elif result.get('fail_count', 0) > 0:
                    failed_count += 1
                    failed_stocks.append(ts_code)
                    status = f"❌ {ts_code}: 失败"
                else:
                    skipped_count += 1
                    status = f"⏭️  {ts_code}: 已是最新"
                
                # 打印详细信息
                print_progress_bar(idx, len(STOCK_LIST), prefix=prefix, suffix=status + " " * 20)
                
                # API限速：每次请求间隔1-2秒
                time.sleep(1.5)
                
            except Exception as e:
                failed_count += 1
                failed_stocks.append(ts_code)
                print(f"\n⚠️  错误 - {ts_code}: {str(e)}")
                time.sleep(2)
        
        # 最终统计
        elapsed_time = time.time() - start_time
        
        print()
        print("=" * 80)
        print("📊 下载完成统计")
        print("=" * 80)
        print(f"✅ 成功下载: {success_count} 只")
        print(f"⏭️  已是最新: {skipped_count} 只")
        print(f"❌ 下载失败: {failed_count} 只")
        print(f"📈 总计新增: {total_records:,} 条记录")
        print(f"⏱️  总耗时: {elapsed_time:.1f}秒 ({elapsed_time/60:.1f}分钟)")
        print(f"⚡ 平均速度: {len(STOCK_LIST)/elapsed_time*60:.1f} 只/分钟")
        print("=" * 80)
        
        # 显示失败列表
        if failed_stocks:
            print()
            print("⚠️  失败股票列表:")
            for stock in failed_stocks:
                print(f"   - {stock}")
            print()
            print("💡 提示: 失败的股票可能是因为:")
            print("   1. TuShare API限速（每分钟最多200次调用）")
            print("   2. 股票代码不存在或已退市")
            print("   3. 网络连接问题")
            print("   4. 可以稍后重新运行脚本下载失败的股票")
        
        print()
        print("✅ 全部完成！可以在前端【数据下载】页面查看数据")
        print()

if __name__ == '__main__':
    try:
        batch_download_data()
    except KeyboardInterrupt:
        print("\n\n⚠️  下载已中断")
        print("💡 提示: 下次运行会自动跳过已下载的数据（增量下载）")
    except Exception as e:
        print(f"\n\n❌ 发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

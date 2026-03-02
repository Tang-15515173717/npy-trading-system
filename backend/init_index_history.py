"""
初始化指数历史数据
下载主要指数近3年的日K线数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from services.index_data_service import IndexDataService
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_index_history(years: int = 3):
    """
    初始化指数历史数据
    
    Args:
        years: 下载近N年数据（默认3年）
    """
    print("\n" + "="*80)
    print("📊 指数历史数据初始化")
    print("="*80)
    
    # 计算日期范围
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=365 * years)).strftime('%Y%m%d')
    
    print(f"\n配置信息：")
    print(f"  时间范围：{start_date} - {end_date} (近{years}年)")
    print(f"  指数数量：{len(IndexDataService.MAIN_INDICES)}")
    print(f"  指数列表：")
    for ts_code, name in IndexDataService.MAIN_INDICES.items():
        print(f"    - {name} ({ts_code})")
    
    # 确认
    confirm = input("\n确认开始下载？[y/N]: ")
    if confirm.lower() != 'y':
        print("已取消")
        return
    
    print("\n" + "="*80)
    print("开始下载...")
    print("="*80 + "\n")
    
    # 下载数据
    total_saved = 0
    for i, (ts_code, name) in enumerate(IndexDataService.MAIN_INDICES.items(), 1):
        print(f"\n[{i}/{len(IndexDataService.MAIN_INDICES)}] {name} ({ts_code})")
        print("-" * 80)
        
        count = IndexDataService.save_daily_data(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )
        
        total_saved += count
        print(f"✅ 保存了 {count} 条记录")
    
    # 统计
    print("\n" + "="*80)
    print("📊 下载完成统计")
    print("="*80)
    print(f"  总共保存：{total_saved} 条记录")
    print(f"  时间范围：{start_date} - {end_date}")
    
    # 查看数据库统计
    print("\n数据库统计：")
    stats = IndexDataService.get_stats()
    for ts_code, info in stats.items():
        print(f"  {info['name']:10} - {info['count']:4}条  最新：{info['latest_date']}")
    
    print("\n" + "="*80)
    print("🎉 指数历史数据初始化完成！")
    print("="*80 + "\n")


def quick_update_today():
    """快速更新今天的数据"""
    print("\n" + "="*80)
    print("📦 快速更新今日数据")
    print("="*80 + "\n")
    
    today = datetime.now().strftime('%Y%m%d')
    total = IndexDataService.update_all_indices(start_date=today, end_date=today)
    
    print(f"\n✅ 更新完成！共 {total} 条记录")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='指数数据初始化工具')
    parser.add_argument('--years', type=int, default=3, help='下载近N年数据（默认3年）')
    parser.add_argument('--today', action='store_true', help='仅更新今日数据')
    
    args = parser.parse_args()
    
    # 需要先创建数据库
    print("⚠️  请确保已创建数据库表！")
    print("   如未创建，请先运行：")
    print("   python")
    print("   >>> from app import create_app")
    print("   >>> from utils.database import db")
    print("   >>> app = create_app()")
    print("   >>> with app.app_context():")
    print("   ...     db.create_all()")
    print()
    
    if args.today:
        quick_update_today()
    else:
        init_index_history(years=args.years)

"""
指数数据定时更新服务
- 交易时段：每15分钟更新实时数据（内存缓存）
- 收盘后：保存日K线到数据库
"""
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class IndexScheduler:
    """指数数据定时更新服务"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.cache = {}  # 内存缓存
        self.last_update = None
        
    def start(self):
        """启动定时任务"""
        print("\n" + "="*80)
        print("🔄 指数数据定时更新服务")
        print("="*80)
        
        # 立即执行一次
        self.update_index_data()
        
        # 【任务1】交易时段：每15分钟更新实时数据（内存）
        self.scheduler.add_job(
            self.update_index_data,
            'cron',
            day_of_week='mon-fri',  # 周一到周五
            hour='9-14',             # 9:00-14:59
            minute='*/15',           # 每15分钟：00, 15, 30, 45
            timezone='Asia/Shanghai'
        )
        
        # 14:45 到 15:15（覆盖收盘时段）
        self.scheduler.add_job(
            self.update_index_data,
            'cron',
            day_of_week='mon-fri',
            hour=14,
            minute='45,55',
            timezone='Asia/Shanghai'
        )
        
        self.scheduler.add_job(
            self.update_index_data,
            'cron',
            day_of_week='mon-fri',
            hour=15,
            minute='0,5,15',  # 15:00, 15:05, 15:15
            timezone='Asia/Shanghai'
        )
        
        # 【任务2】收盘后：保存日K线到数据库
        self.scheduler.add_job(
            self.save_daily_to_db,
            'cron',
            day_of_week='mon-fri',
            hour=15,
            minute=30,  # 15:30 保存
            timezone='Asia/Shanghai'
        )
        
        self.scheduler.start()
        print("✅ 定时任务已启动")
        print(f"   实时数据：交易时段每15分钟（内存缓存）")
        print(f"   日K线：每天15:30保存到数据库")
        print(f"   运行时间：周一至周五 9:00-15:30")
        print("="*80 + "\n")
    
    def update_index_data(self):
        """更新实时指数数据（内存缓存）"""
        now = datetime.now()
        print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] 🔄 更新实时指数数据...")
        
        try:
            import akshare as ak
            
            # 获取实时指数行情
            df = ak.stock_zh_index_spot()
            
            if df is None or df.empty:
                print("❌ 未获取到数据")
                return
            
            # 转换为字典格式
            data = {}
            for _, row in df.iterrows():
                code = row['代码']
                data[code] = {
                    'code': code,
                    'name': row['名称'],
                    'price': float(row['最新价']),
                    'change': float(row['涨跌额']),
                    'change_pct': float(row['涨跌幅']),
                    'open': float(row['今开']),
                    'high': float(row['最高']),
                    'low': float(row['最低']),
                    'pre_close': float(row['昨收']),
                    'volume': float(row['成交量']),
                    'amount': float(row['成交额']),
                    'update_time': now.strftime('%Y-%m-%d %H:%M:%S')
                }
            
            # 更新缓存
            self.cache = data
            self.last_update = now
            
            # 显示部分数据
            main_indices = ['000001', '399001', '000300', '399006']
            print(f"✅ 成功更新 {len(data)} 个指数（内存），主要指数：")
            for code in main_indices:
                if code in data:
                    idx = data[code]
                    change_symbol = '+' if idx['change_pct'] > 0 else ''
                    print(f"   {idx['name']:8} {idx['price']:8.2f}  "
                          f"{change_symbol}{idx['change_pct']:6.2f}%")
            
        except ImportError:
            print("❌ AKShare 未安装，请执行：pip install akshare")
        except Exception as e:
            print(f"❌ 更新失败：{e}")
    
    def save_daily_to_db(self):
        """收盘后保存日K线到数据库"""
        now = datetime.now()
        print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] 📦 保存日K线到数据库...")
        
        try:
            from services.index_data_service import IndexDataService
            
            today = now.strftime('%Y%m%d')
            total = IndexDataService.update_all_indices(
                start_date=today,
                end_date=today
            )
            
            print(f"✅ 日K线保存完成！共 {total} 条新记录")
            
        except Exception as e:
            logger.error(f"❌ 保存日K线失败：{e}")
            print(f"❌ 保存日K线失败：{e}")
    
    def get_index_data(self, code=None):
        """
        获取指数数据（从缓存）
        
        Args:
            code: 指数代码（如 '000001'），不传则返回所有
        
        Returns:
            dict or None
        """
        if code:
            return self.cache.get(code)
        return {
            'data': self.cache,
            'last_update': self.last_update.strftime('%Y-%m-%d %H:%M:%S') if self.last_update else None,
            'count': len(self.cache)
        }
    
    def get_main_indices(self):
        """获取主要指数数据"""
        main_codes = ['000001', '399001', '000300', '000016', '399006', '000688']
        result = {}
        for code in main_codes:
            if code in self.cache:
                result[code] = self.cache[code]
        return result
    
    def stop(self):
        """停止定时任务"""
        self.scheduler.shutdown()
        print("⏹️  指数数据定时任务已停止")


# 全局实例
index_scheduler = IndexScheduler()


if __name__ == "__main__":
    # 测试
    print("📊 测试指数数据定时更新服务\n")
    
    scheduler = IndexScheduler()
    scheduler.start()
    
    # 等待一段时间
    import time
    print("\n等待更新...")
    time.sleep(5)
    
    # 获取数据
    print("\n📊 当前缓存的指数数据：")
    data = scheduler.get_main_indices()
    for code, info in data.items():
        print(f"\n{info['name']} ({code}):")
        print(f"  最新价：{info['price']:.2f}")
        print(f"  涨跌幅：{info['change_pct']:.2f}%")
        print(f"  更新时间：{info['update_time']}")
    
    print("\n✅ 测试完成")
    print("提示：在实际应用中，定时任务会在后台持续运行")

"""
数据监听策略 - 第三阶段实战
只监听，不交易，理解实时数据流
"""

from vnpy_ctastrategy import CtaTemplate
from vnpy.trader.object import TickData, BarData

class DataMonitorStrategy(CtaTemplate):
    """
    数据监听策略
    功能：监听实时数据，打印日志，不执行交易
    """
    
    author = "VeighNa学习者"
    
    # 策略参数
    monitor_interval = 10  # 每10个tick打印一次
    
    # 策略变量
    tick_count = 0
    bar_count = 0
    last_price = 0
    highest_price = 0
    lowest_price = 999999
    
    # 变量列表（需要保存的变量）
    variables = [
        "tick_count",
        "bar_count",
        "last_price",
        "highest_price",
        "lowest_price"
    ]
    
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """初始化"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
    
    def on_init(self):
        """策略初始化"""
        self.write_log("=" * 50)
        self.write_log("📊 数据监听策略 - 初始化")
        self.write_log(f"监控合约: {self.vt_symbol}")
        self.write_log(f"监控间隔: 每 {self.monitor_interval} 个tick")
        self.write_log("=" * 50)
        
        # 注释掉load_bar，简化版不需要历史数据
        # self.load_bar(10)
    
    def on_start(self):
        """策略启动"""
        self.write_log("🚀 策略启动 - 开始监听实时数据")
        self.write_log("等待数据推送...")
    
    def on_stop(self):
        """策略停止"""
        self.write_log("=" * 50)
        self.write_log("⏹️  策略停止")
        self.write_log(f"总计接收 Tick: {self.tick_count} 个")
        self.write_log(f"总计接收 Bar: {self.bar_count} 个")
        self.write_log(f"最后价格: {self.last_price}")
        self.write_log(f"最高价格: {self.highest_price}")
        self.write_log(f"最低价格: {self.lowest_price}")
        self.write_log("=" * 50)
    
    def on_tick(self, tick: TickData):
        """
        收到逐笔行情推送（实时数据）
        这是最快的数据更新
        """
        self.tick_count += 1
        self.last_price = tick.last_price
        
        # 更新最高最低价
        if tick.last_price > self.highest_price:
            self.highest_price = tick.last_price
        if tick.last_price < self.lowest_price:
            self.lowest_price = tick.last_price
        
        # 每N个tick打印一次
        if self.tick_count % self.monitor_interval == 0:
            self.write_log(
                f"📊 Tick #{self.tick_count:>6} | "
                f"时间: {tick.datetime.strftime('%H:%M:%S')} | "
                f"最新价: {tick.last_price:>8.2f} | "
                f"买一: {tick.bid_price_1:>8.2f} | "
                f"卖一: {tick.ask_price_1:>8.2f} | "
                f"成交量: {tick.volume:>8}"
            )
    
    def on_bar(self, bar: BarData):
        """
        收到K线数据推送
        K线是聚合后的数据（如1分钟、5分钟）
        """
        self.bar_count += 1
        
        # 计算涨跌幅
        if bar.open_price > 0:
            change_pct = ((bar.close_price - bar.open_price) / bar.open_price) * 100
        else:
            change_pct = 0
        
        self.write_log(
            f"📈 Bar #{self.bar_count:>4} | "
            f"{bar.datetime.strftime('%Y-%m-%d %H:%M')} | "
            f"开: {bar.open_price:>8.2f} | "
            f"高: {bar.high_price:>8.2f} | "
            f"低: {bar.low_price:>8.2f} | "
            f"收: {bar.close_price:>8.2f} | "
            f"量: {bar.volume:>8} | "
            f"涨跌: {change_pct:>+6.2f}%"
        )

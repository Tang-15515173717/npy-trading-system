"""
VeighNa 交易系统主启动器
类似于 Spring Boot 的 Application.java
一键启动整个交易系统
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp

# 导入所有应用模块
from vnpy_ctastrategy import CtaStrategyApp
from vnpy_ctabacktester import CtaBacktesterApp
from vnpy_datamanager import DataManagerApp

# 可选模块（如果没安装会跳过）
try:
    from vnpy_chartwizard import ChartWizardApp
    HAS_CHART = True
except ImportError:
    HAS_CHART = False

try:
    from vnpy_riskmanager import RiskManagerApp
    HAS_RISK = True
except ImportError:
    HAS_RISK = False

# 配置TuShare
import os
import tushare as ts

# 设置TuShare Token
TUSHARE_TOKEN = "c581961ccacd6c2f01c196364402ef122a6a51335354bb01ab24c7a1"
os.environ['TUSHARE_TOKEN'] = TUSHARE_TOKEN
ts.set_token(TUSHARE_TOKEN)


def main():
    """
    主启动函数
    类似于 Spring Boot 的 main 方法
    """
    
    print("=" * 70)
    print("🚀 VeighNa 量化交易系统启动中...")
    print("=" * 70)
    print()
    
    # ========== 1. 创建Qt应用 ==========
    print("📱 初始化图形界面...")
    qapp = create_qapp()
    
    # ========== 2. 创建事件引擎 ==========
    print("⚙️  启动事件引擎...")
    event_engine = EventEngine()
    
    # ========== 3. 创建主引擎 ==========
    print("🔧 初始化主引擎...")
    main_engine = MainEngine(event_engine)
    
    # ========== 4. 加载所有应用 ==========
    print("📦 加载应用模块...")
    
    print("   - CTA策略应用（实盘策略）")
    main_engine.add_app(CtaStrategyApp)
    
    print("   - CTA回测应用（策略回测）")
    main_engine.add_app(CtaBacktesterApp)
    
    print("   - 数据管理应用（历史数据）")
    main_engine.add_app(DataManagerApp)
    
    if HAS_CHART:
        print("   - K线图表应用（图表分析）")
        main_engine.add_app(ChartWizardApp)
    else:
        print("   - K线图表应用（未安装，跳过）")
    
    if HAS_RISK:
        print("   - 风险管理应用（风控系统）")
        main_engine.add_app(RiskManagerApp)
    else:
        print("   - 风险管理应用（未安装，跳过）")
    
    print()
    
    # ========== 5. 创建主窗口 ==========
    print("🖼️  创建主窗口...")
    main_window = MainWindow(main_engine, event_engine)
    
    # 设置窗口标题
    main_window.setWindowTitle("VeighNa Trader - 量化交易系统")
    
    # 最大化显示
    main_window.showMaximized()
    
    print()
    print("=" * 70)
    print("✅ 系统启动完成！")
    print("=" * 70)
    print()
    print("📚 快速指南：")
    print("   1. 功能 → 数据管理：下载历史数据（使用TuShare）")
    print("   2. 功能 → CTA策略：运行实盘策略")
    print("   3. 功能 → CTA回测：回测策略表现")
    print("   4. 系统 → 连接：连接实盘或模拟账户")
    print()
    print("💡 提示：")
    print("   - TuShare已配置（120积分）")
    print("   - 关闭窗口即可退出系统")
    print()
    print("=" * 70)
    
    # ========== 6. 运行应用 ==========
    qapp.exec()
    
    # ========== 7. 清理资源 ==========
    print()
    print("👋 系统正在关闭...")


if __name__ == "__main__":
    """
    程序入口点
    """
    main()

"""
创建多个策略模板 - 不同风格的量化策略
包含：激进型、稳健型、平衡型、趋势型、套利型等
"""
import sys
import json
sys.path.insert(0, '/Users/mac/IdeaProjects/vnpy/backend')

from app import create_app
from models.strategy import Strategy
from utils.database import db
from datetime import datetime

app = create_app()

# 策略模板数据
strategies_data = [
    # 1. 激进型策略
    {
        "name": "双均线突破策略（激进版）",
        "type": "CTA",
        "description": "快速响应的双均线策略，适合波动大的市场。使用5日和10日均线，快速捕捉短期趋势。风险等级：高",
        "params": {
            "fast_window": 5,
            "slow_window": 10,
            "stop_loss": 0.03,      # 3%止损
            "take_profit": 0.08,    # 8%止盈
            "position_pct": 0.8,    # 80%仓位
            "risk_level": "高"
        },
        "status": "active",
        "code": None
    },
    
    # 2. 稳健型策略
    {
        "name": "长期均线趋势策略（稳健版）",
        "type": "CTA",
        "description": "基于长期均线的趋势跟踪策略，适合稳健投资者。使用30日和60日均线，降低交易频率。风险等级：低",
        "params": {
            "fast_window": 30,
            "slow_window": 60,
            "stop_loss": 0.05,      # 5%止损
            "take_profit": 0.15,    # 15%止盈
            "position_pct": 0.5,    # 50%仓位
            "risk_level": "低"
        },
        "status": "active",
        "code": None
    },
    
    # 3. 平衡型策略
    {
        "name": "MACD指标策略（平衡版）",
        "type": "CTA",
        "description": "经典MACD指标策略，平衡风险与收益。适合中等风险偏好的投资者。风险等级：中",
        "params": {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "stop_loss": 0.04,      # 4%止损
            "take_profit": 0.10,    # 10%止盈
            "position_pct": 0.6,    # 60%仓位
            "risk_level": "中"
        },
        "status": "active",
        "code": None
    },
    
    # 4. 趋势突破策略
    {
        "name": "唐奇安通道突破策略",
        "type": "CTA",
        "description": "经典的趋势突破策略，突破20日高点买入，突破10日低点卖出。适合趋势明显的市场。风险等级：中",
        "params": {
            "entry_window": 20,     # 突破20日高点入场
            "exit_window": 10,      # 突破10日低点出场
            "stop_loss": 0.06,      # 6%止损
            "position_pct": 0.7,    # 70%仓位
            "risk_level": "中"
        },
        "status": "active",
        "code": None
    },
    
    # 5. RSI超买超卖策略
    {
        "name": "RSI均值回归策略",
        "type": "CTA",
        "description": "基于RSI指标的均值回归策略。RSI低于30时买入，高于70时卖出。适合震荡市场。风险等级：中",
        "params": {
            "rsi_period": 14,
            "oversold_level": 30,   # 超卖阈值
            "overbought_level": 70, # 超买阈值
            "stop_loss": 0.04,
            "take_profit": 0.08,
            "position_pct": 0.5,
            "risk_level": "中"
        },
        "status": "active",
        "code": None
    },
    
    # 6. 激进短线策略
    {
        "name": "日内短线策略（激进版）",
        "type": "CTA",
        "description": "专注日内交易的短线策略，使用3分钟K线，快进快出。风险较高，适合经验丰富的交易者。风险等级：极高",
        "params": {
            "fast_window": 3,
            "slow_window": 5,
            "stop_loss": 0.02,      # 2%止损
            "take_profit": 0.05,    # 5%止盈
            "position_pct": 0.9,    # 90%仓位
            "max_daily_trades": 5,  # 每日最多5笔
            "risk_level": "极高"
        },
        "status": "active",
        "code": None
    },
    
    # 7. 极度稳健策略
    {
        "name": "价值投资长线策略（极稳健）",
        "type": "Portfolio",
        "description": "基于基本面的长期投资策略。低频交易，重视股息和价值。适合保守投资者。风险等级：极低",
        "params": {
            "holding_period_days": 90,  # 最短持有90天
            "pe_threshold": 15,         # 市盈率阈值
            "pb_threshold": 2,          # 市净率阈值
            "dividend_yield_min": 0.03, # 最低股息率3%
            "position_pct": 0.3,        # 30%仓位
            "stop_loss": 0.15,          # 15%止损
            "risk_level": "极低"
        },
        "status": "active",
        "code": None
    },
    
    # 8. 网格交易策略
    {
        "name": "网格交易策略（震荡市）",
        "type": "Grid",
        "description": "适合震荡市场的网格交易策略。在一定价格区间内设置多个买卖点，低买高卖。风险等级：中",
        "params": {
            "grid_count": 10,       # 网格数量
            "price_range_pct": 0.20, # 价格区间20%
            "single_grid_pct": 0.1, # 单格仓位10%
            "stop_loss": 0.08,
            "risk_level": "中"
        },
        "status": "active",
        "code": None
    },
    
    # 9. 布林带策略
    {
        "name": "布林带突破策略",
        "type": "CTA",
        "description": "基于布林带的突破策略。价格触及下轨买入，触及上轨卖出。风险等级：中",
        "params": {
            "bollinger_period": 20,
            "std_multiplier": 2,    # 标准差倍数
            "stop_loss": 0.05,
            "take_profit": 0.12,
            "position_pct": 0.6,
            "risk_level": "中"
        },
        "status": "active",
        "code": None
    },
    
    # 10. 海龟交易策略
    {
        "name": "海龟交易法则",
        "type": "CTA",
        "description": "经典的海龟交易系统。突破20日高点买入，突破10日低点止损。风险等级：中",
        "params": {
            "entry_breakout": 20,
            "exit_breakout": 10,
            "atr_period": 20,
            "risk_per_trade": 0.02, # 每笔风险2%
            "position_pct": 0.5,
            "risk_level": "中"
        },
        "status": "active",
        "code": None
    },
    
    # 11. 动量策略（激进）
    {
        "name": "动量追涨策略（激进版）",
        "type": "CTA",
        "description": "追踪强势股票的动量策略。连续上涨买入，止盈止损紧密。风险较高。风险等级：高",
        "params": {
            "momentum_period": 5,    # 5日动量
            "momentum_threshold": 0.03, # 3%涨幅阈值
            "stop_loss": 0.03,
            "take_profit": 0.10,
            "position_pct": 0.8,
            "risk_level": "高"
        },
        "status": "active",
        "code": None
    },
    
    # 12. 套利策略
    {
        "name": "统计套利策略",
        "type": "Arbitrage",
        "description": "基于股票对的协整关系进行套利。适合稳健风险偏好，需要较大资金量。风险等级：低",
        "params": {
            "lookback_period": 60,
            "entry_zscore": 2.0,    # Z值阈值
            "exit_zscore": 0.5,
            "position_pct": 0.4,
            "risk_level": "低"
        },
        "status": "active",
        "code": None
    }
]

def create_strategies():
    """创建策略模板"""
    with app.app_context():
        print("\n" + "="*70)
        print("  📋 开始创建策略模板")
        print("="*70)
        
        # 清空现有策略（可选）
        # Strategy.query.delete()
        # db.session.commit()
        # print("✅ 已清空现有策略")
        
        created_count = 0
        
        for strategy_data in strategies_data:
            try:
                # 检查是否已存在
                existing = Strategy.query.filter_by(name=strategy_data["name"]).first()
                if existing:
                    print(f"⚠️  策略已存在，跳过: {strategy_data['name']}")
                    continue
                
                strategy = Strategy(
                    name=strategy_data["name"],
                    type=strategy_data["type"],
                    description=strategy_data["description"],
                    params=json.dumps(strategy_data["params"], ensure_ascii=False),
                    status=strategy_data["status"],
                    code=strategy_data.get("code"),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                db.session.add(strategy)
                created_count += 1
                
                print(f"✅ 创建策略: {strategy_data['name']} ({strategy_data['type']})")
                
            except Exception as e:
                print(f"❌ 创建失败: {strategy_data['name']}")
                print(f"   错误: {e}")
                db.session.rollback()
        
        # 提交所有策略
        try:
            db.session.commit()
            print("\n" + "="*70)
            print(f"🎉 成功创建 {created_count} 个策略模板")
            print("="*70)
            
            # 显示统计
            print("\n📊 策略统计:")
            total = Strategy.query.count()
            cta = Strategy.query.filter_by(type="CTA").count()
            portfolio = Strategy.query.filter_by(type="Portfolio").count()
            grid = Strategy.query.filter_by(type="Grid").count()
            arbitrage = Strategy.query.filter_by(type="Arbitrage").count()
            
            print(f"  总数: {total} 个")
            print(f"  CTA策略: {cta} 个")
            print(f"  组合策略: {portfolio} 个")
            print(f"  网格策略: {grid} 个")
            print(f"  套利策略: {arbitrage} 个")
            
            # 显示所有策略
            print("\n📋 所有策略列表:")
            strategies = Strategy.query.all()
            for s in strategies:
                risk_info = ""
                if s.params:
                    try:
                        params = json.loads(s.params)
                        risk_info = f" - 风险等级: {params.get('risk_level', '未知')}"
                    except:
                        pass
                print(f"  {s.id}. {s.name} - {s.type}{risk_info}")
            
        except Exception as e:
            print(f"\n❌ 提交失败: {e}")
            db.session.rollback()

if __name__ == "__main__":
    create_strategies()

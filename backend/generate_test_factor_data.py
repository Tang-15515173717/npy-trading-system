"""
生成测试因子数据
用于回测测试
"""
from models.factor_data import FactorData
from models.bar_data import BarData
from utils.database import db
from app import create_app
from datetime import datetime, timedelta
import random

def generate_test_factor_data():
    """生成测试因子数据"""
    app = create_app()
    
    with app.app_context():
        # 测试股票列表
        test_stocks = [
            "000001.SZ", "000002.SZ", "000301.SZ", 
            "000333.SZ", "000538.SZ"
        ]
        
        # 生成2025年2月1日-10日的因子数据
        start_date = datetime(2025, 2, 1)
        end_date = datetime(2025, 2, 10)
        
        current = start_date
        generated = 0
        
        while current <= end_date:
            # 跳过周末
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue
            
            trade_date = current.strftime("%Y%m%d")
            
            for ts_code in test_stocks:
                # 检查是否已存在
                existing = FactorData.query.filter_by(
                    ts_code=ts_code,
                    trade_date=trade_date
                ).first()
                
                if existing:
                    print(f"已存在: {ts_code} {trade_date}")
                    continue
                
                # 生成随机因子数据
                factor_data = FactorData(
                    ts_code=ts_code,
                    trade_date=trade_date,
                    # 动量因子
                    return_5d=random.uniform(-0.05, 0.10),
                    return_20d=random.uniform(-0.10, 0.20),
                    return_60d=random.uniform(-0.20, 0.30),
                    rsi_14=random.uniform(30, 70),
                    macd=random.uniform(-1, 1),
                    macd_signal=random.uniform(-1, 1),
                    macd_hist=random.uniform(-0.5, 0.5),
                    # 反转因子
                    reversal_5d=random.uniform(-0.03, 0.03),
                    # 波动率因子
                    volatility_20d=random.uniform(0.01, 0.05),
                    beta=random.uniform(0.8, 1.5),
                    # 流动性因子
                    turnover_rate=random.uniform(1, 10),
                    volume_ratio=random.uniform(0.5, 2.0),
                    # 价值因子
                    pe_ratio=random.uniform(10, 50),
                    pb_ratio=random.uniform(1, 5),
                    ps_ratio=random.uniform(1, 10),
                    dividend_yield=random.uniform(0, 0.05),
                    # 成长因子
                    revenue_growth=random.uniform(-0.1, 0.3),
                    profit_growth=random.uniform(-0.2, 0.5),
                    roe_growth=random.uniform(-0.1, 0.2),
                    # 质量因子
                    roe=random.uniform(0.05, 0.25),
                    gross_margin=random.uniform(0.1, 0.5),
                    debt_ratio=random.uniform(0.2, 0.7),
                    # 盈利因子
                    net_margin=random.uniform(0.05, 0.20),
                    total_asset_turnover=random.uniform(0.3, 1.5),
                    # 行业因子
                    industry_momentum=random.uniform(-0.1, 0.1),
                    industry_pe=random.uniform(15, 40),
                    # 产业链因子
                    upstream_linkage=random.uniform(-0.05, 0.05),
                    downstream_demand=random.uniform(-0.05, 0.05),
                    # 情绪因子
                    news_sentiment=random.uniform(-1, 1),
                    news_heat=random.uniform(0, 100),
                    social_heat=random.uniform(0, 100),
                    # 分析师因子
                    analyst_rating=random.uniform(1, 5),
                    rating_trend=random.uniform(-1, 1),
                )
                
                db.session.add(factor_data)
                generated += 1
                
                if generated % 10 == 0:
                    db.session.commit()
                    print(f"已生成 {generated} 条因子数据...")
            
            current += timedelta(days=1)
        
        db.session.commit()
        print(f"\n✅ 完成！共生成 {generated} 条测试因子数据")
        print(f"股票数：{len(test_stocks)}")
        print(f"日期范围：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    generate_test_factor_data()

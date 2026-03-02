"""
数据库迁移脚本 - v2.0 添加量化因子表
Version: 2.0
Date: 2026-01-30
Description: 添加5张因子相关表，支持量化因子体系
"""

import sys
import os

# 添加backend目录到路径
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app import create_app
from utils.database import db
from sqlalchemy import text
from datetime import datetime


def migrate_v2_0_add_factor_tables():
    """
    v2.0 数据库迁移：添加5张因子表
    
    新增表：
    1. factor_data - 因子数据表
    2. factor_library - 因子库表
    3. factor_ic - 因子IC值表
    4. factor_selection - 因子选股记录表
    5. supply_chain - 产业链关系表
    """
    
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("🔄 开始执行 v2.0 数据库迁移...")
        print("=" * 60)
        
        # 1. 创建 factor_data 表
        print("\n📊 创建 factor_data 表（因子数据）...")
        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS factor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code VARCHAR(20) NOT NULL,
                    trade_date VARCHAR(8) NOT NULL,
                    
                    -- 动量因子
                    return_5d REAL,
                    return_20d REAL,
                    return_60d REAL,
                    rsi_14 REAL,
                    macd REAL,
                    
                    -- 反转因子
                    reversal_5d REAL,
                    
                    -- 波动率因子
                    volatility_20d REAL,
                    beta REAL,
                    
                    -- 流动性因子
                    turnover_rate REAL,
                    volume_ratio REAL,
                    
                    -- 价值因子
                    pe_ratio REAL,
                    pb_ratio REAL,
                    ps_ratio REAL,
                    dividend_yield REAL,
                    
                    -- 成长因子
                    revenue_growth REAL,
                    profit_growth REAL,
                    roe_growth REAL,
                    
                    -- 质量因子
                    roe REAL,
                    gross_margin REAL,
                    debt_ratio REAL,
                    
                    -- 盈利因子
                    net_margin REAL,
                    total_asset_turnover REAL,
                    
                    -- 行业因子
                    industry_momentum REAL,
                    industry_pe REAL,
                    
                    -- 产业链因子
                    upstream_linkage REAL,
                    downstream_demand REAL,
                    
                    -- 情绪因子
                    news_sentiment REAL,
                    news_heat REAL,
                    social_heat REAL,
                    
                    -- 分析师因子
                    analyst_rating REAL,
                    rating_trend REAL,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(ts_code, trade_date)
                )
            """))
            
            # 创建索引
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_factor_data_ts_code ON factor_data(ts_code)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_factor_data_trade_date ON factor_data(trade_date)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_factor_data_return_20d ON factor_data(return_20d)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_factor_data_pe_ratio ON factor_data(pe_ratio)"))
            
            print("✅ factor_data 表创建成功")
        except Exception as e:
            print(f"❌ factor_data 表创建失败: {e}")
        
        # 2. 创建 factor_library 表
        print("\n📚 创建 factor_library 表（因子库）...")
        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS factor_library (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    factor_code VARCHAR(50) NOT NULL UNIQUE,
                    factor_name VARCHAR(100) NOT NULL,
                    factor_category VARCHAR(20) NOT NULL,
                    factor_desc TEXT,
                    calculation_method TEXT,
                    data_source VARCHAR(50),
                    is_active BOOLEAN DEFAULT 1,
                    ic_mean REAL,
                    ir_value REAL,
                    win_rate REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # 创建索引
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_factor_library_category ON factor_library(factor_category)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_factor_library_is_active ON factor_library(is_active)"))
            
            print("✅ factor_library 表创建成功")
        except Exception as e:
            print(f"❌ factor_library 表创建失败: {e}")
        
        # 3. 创建 factor_ic 表
        print("\n📈 创建 factor_ic 表（因子IC值）...")
        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS factor_ic (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    factor_code VARCHAR(50) NOT NULL,
                    trade_date VARCHAR(8) NOT NULL,
                    ic_value REAL,
                    rank_ic REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(factor_code, trade_date)
                )
            """))
            
            # 创建索引
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_factor_ic_factor_code ON factor_ic(factor_code)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_factor_ic_trade_date ON factor_ic(trade_date)"))
            
            print("✅ factor_ic 表创建成功")
        except Exception as e:
            print(f"❌ factor_ic 表创建失败: {e}")
        
        # 4. 创建 factor_selection 表
        print("\n🎯 创建 factor_selection 表（因子选股记录）...")
        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS factor_selection (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    selection_name VARCHAR(100) NOT NULL,
                    selection_date VARCHAR(8) NOT NULL,
                    factor_config TEXT NOT NULL,
                    stock_count INTEGER,
                    selected_stocks TEXT,
                    avg_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # 创建索引
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_factor_selection_date ON factor_selection(selection_date)"))
            
            print("✅ factor_selection 表创建成功")
        except Exception as e:
            print(f"❌ factor_selection 表创建失败: {e}")
        
        # 5. 创建 supply_chain 表
        print("\n🏭 创建 supply_chain 表（产业链关系）...")
        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS supply_chain (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chain_name VARCHAR(100) NOT NULL,
                    ts_code VARCHAR(20) NOT NULL,
                    chain_position VARCHAR(50),
                    upstream_stocks TEXT,
                    downstream_stocks TEXT,
                    is_leader BOOLEAN DEFAULT 0,
                    industry VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # 创建索引
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_supply_chain_name ON supply_chain(chain_name)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_supply_chain_ts_code ON supply_chain(ts_code)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_supply_chain_is_leader ON supply_chain(is_leader)"))
            
            print("✅ supply_chain 表创建成功")
        except Exception as e:
            print(f"❌ supply_chain 表创建失败: {e}")
        
        # 提交更改
        db.session.commit()
        print("\n" + "=" * 60)
        print("✅ v2.0 数据库迁移完成！")
        print("=" * 60)
        
        # 插入初始因子库数据
        print("\n📚 插入初始因子库数据...")
        insert_initial_factors()
        
        # 插入示例产业链数据
        print("\n🏭 插入示例产业链数据...")
        insert_sample_supply_chain()


def insert_initial_factors():
    """插入初始因子库数据"""
    
    initial_factors = [
        # 动量因子
        {'factor_code': 'return_5d', 'factor_name': '5日收益率', 'factor_category': 'momentum', 'factor_desc': '过去5个交易日的收益率', 'calculation_method': '(close_t - close_t-5) / close_t-5', 'data_source': 'kline', 'is_active': 1},
        {'factor_code': 'return_20d', 'factor_name': '20日收益率', 'factor_category': 'momentum', 'factor_desc': '过去20个交易日的收益率', 'calculation_method': '(close_t - close_t-20) / close_t-20', 'data_source': 'kline', 'is_active': 1},
        {'factor_code': 'return_60d', 'factor_name': '60日收益率', 'factor_category': 'momentum', 'factor_desc': '过去60个交易日的收益率', 'calculation_method': '(close_t - close_t-60) / close_t-60', 'data_source': 'kline', 'is_active': 1},
        {'factor_code': 'rsi_14', 'factor_name': 'RSI相对强弱指标', 'factor_category': 'momentum', 'factor_desc': '14日RSI指标', 'calculation_method': 'RSI(14)', 'data_source': 'kline', 'is_active': 1},
        {'factor_code': 'macd', 'factor_name': 'MACD', 'factor_category': 'momentum', 'factor_desc': 'MACD差离值', 'calculation_method': 'MACD(12,26,9)', 'data_source': 'kline', 'is_active': 1},
        
        # 价值因子
        {'factor_code': 'pe_ratio', 'factor_name': '市盈率', 'factor_category': 'value', 'factor_desc': 'Price/Earnings', 'calculation_method': 'PE', 'data_source': 'financial', 'is_active': 1},
        {'factor_code': 'pb_ratio', 'factor_name': '市净率', 'factor_category': 'value', 'factor_desc': 'Price/Book', 'calculation_method': 'PB', 'data_source': 'financial', 'is_active': 1},
        {'factor_code': 'ps_ratio', 'factor_name': '市销率', 'factor_category': 'value', 'factor_desc': 'Price/Sales', 'calculation_method': 'PS', 'data_source': 'financial', 'is_active': 1},
        {'factor_code': 'dividend_yield', 'factor_name': '股息率', 'factor_category': 'value', 'factor_desc': '股息收益率', 'calculation_method': 'Dividend/Price', 'data_source': 'financial', 'is_active': 1},
        
        # 成长因子
        {'factor_code': 'revenue_growth', 'factor_name': '营收增长率', 'factor_category': 'growth', 'factor_desc': '营业收入增长率', 'calculation_method': '(Revenue_t - Revenue_t-1) / Revenue_t-1', 'data_source': 'financial', 'is_active': 1},
        {'factor_code': 'profit_growth', 'factor_name': '利润增长率', 'factor_category': 'growth', 'factor_desc': '净利润增长率', 'calculation_method': '(Profit_t - Profit_t-1) / Profit_t-1', 'data_source': 'financial', 'is_active': 1},
        {'factor_code': 'roe_growth', 'factor_name': 'ROE增长率', 'factor_category': 'growth', 'factor_desc': 'ROE增长率', 'calculation_method': '(ROE_t - ROE_t-1) / ROE_t-1', 'data_source': 'financial', 'is_active': 1},
        
        # 质量因子
        {'factor_code': 'roe', 'factor_name': 'ROE净资产收益率', 'factor_category': 'quality', 'factor_desc': '净资产收益率', 'calculation_method': 'Net Income / Shareholders Equity', 'data_source': 'financial', 'is_active': 1},
        {'factor_code': 'gross_margin', 'factor_name': '毛利率', 'factor_category': 'quality', 'factor_desc': '销售毛利率', 'calculation_method': '(Revenue - COGS) / Revenue', 'data_source': 'financial', 'is_active': 1},
        {'factor_code': 'debt_ratio', 'factor_name': '资产负债率', 'factor_category': 'quality', 'factor_desc': '负债与资产比率', 'calculation_method': 'Total Debt / Total Assets', 'data_source': 'financial', 'is_active': 1},
    ]
    
    try:
        for factor in initial_factors:
            db.session.execute(text("""
                INSERT OR IGNORE INTO factor_library 
                (factor_code, factor_name, factor_category, factor_desc, calculation_method, data_source, is_active)
                VALUES (:factor_code, :factor_name, :factor_category, :factor_desc, :calculation_method, :data_source, :is_active)
            """), factor)
        
        db.session.commit()
        print(f"✅ 插入了 {len(initial_factors)} 个因子")
    except Exception as e:
        print(f"❌ 插入因子失败: {e}")
        db.session.rollback()


def insert_sample_supply_chain():
    """插入示例产业链数据"""
    
    sample_chains = [
        # 新能源汽车产业链
        {'chain_name': '新能源汽车', 'ts_code': '300750.SZ', 'chain_position': '上游-锂矿', 'upstream_stocks': '[]', 'downstream_stocks': '[]', 'is_leader': 1, 'industry': '电池'},
        {'chain_name': '新能源汽车', 'ts_code': '002594.SZ', 'chain_position': '中游-电池', 'upstream_stocks': '["300750.SZ"]', 'downstream_stocks': '["600104.SH"]', 'is_leader': 1, 'industry': '汽车'},
        {'chain_name': '新能源汽车', 'ts_code': '600104.SH', 'chain_position': '下游-整车', 'upstream_stocks': '["002594.SZ"]', 'downstream_stocks': '[]', 'is_leader': 0, 'industry': '汽车'},
        
        # 半导体产业链
        {'chain_name': '半导体', 'ts_code': '688981.SH', 'chain_position': '上游-设备', 'upstream_stocks': '[]', 'downstream_stocks': '["688008.SH"]', 'is_leader': 1, 'industry': '半导体'},
        {'chain_name': '半导体', 'ts_code': '688008.SH', 'chain_position': '中游-制造', 'upstream_stocks': '["688981.SH"]', 'downstream_stocks': '["002241.SZ"]', 'is_leader': 1, 'industry': '半导体'},
        {'chain_name': '半导体', 'ts_code': '002241.SZ', 'chain_position': '下游-封测', 'upstream_stocks': '["688008.SH"]', 'downstream_stocks': '[]', 'is_leader': 0, 'industry': '半导体'},
    ]
    
    try:
        for chain in sample_chains:
            db.session.execute(text("""
                INSERT OR IGNORE INTO supply_chain 
                (chain_name, ts_code, chain_position, upstream_stocks, downstream_stocks, is_leader, industry)
                VALUES (:chain_name, :ts_code, :chain_position, :upstream_stocks, :downstream_stocks, :is_leader, :industry)
            """), chain)
        
        db.session.commit()
        print(f"✅ 插入了 {len(sample_chains)} 条产业链数据")
    except Exception as e:
        print(f"❌ 插入产业链数据失败: {e}")
        db.session.rollback()


if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════╗
    ║   StockQuant Pro - v2.0 数据库迁移        ║
    ║   添加量化因子模块（5张新表）              ║
    ╚═══════════════════════════════════════════╝
    """)
    
    try:
        migrate_v2_0_add_factor_tables()
        print("\n🎉 迁移成功！现在可以使用因子功能了。\n")
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}\n")
        import traceback
        traceback.print_exc()

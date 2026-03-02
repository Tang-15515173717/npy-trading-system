"""
数据库迁移脚本 - 添加技术指标字段
v2.3 - 添加 macd_signal 和 macd_hist 字段
"""
from utils.database import db
from models.factor_data import FactorData
from models.factor_library import FactorLibrary

def migrate_add_technical_indicators():
    """添加技术指标字段到 factor_data 表"""
    
    print("\n" + "="*60)
    print("🔧 开始数据库迁移：添加技术指标字段")
    print("="*60 + "\n")
    
    try:
        # 1. 添加新字段（如果使用SQLite，需要手动添加）
        # SQLite不支持ALTER TABLE ADD COLUMN，所以字段已在模型中定义
        # 只需要创建表即可
        db.create_all()
        print("✅ 数据库表结构已更新")
        
        # 2. 添加新因子到因子库
        new_factors = [
            {
                'factor_code': 'rsi_14',
                'factor_name': 'RSI(14)',
                'factor_category': 'momentum',
                'factor_desc': '14日相对强弱指标，衡量价格变动的速度和幅度',
                'calculation_method': 'RSI = 100 - (100 / (1 + RS))，RS = 平均涨幅 / 平均跌幅',
                'data_source': 'K线数据',
                'is_active': True
            },
            {
                'factor_code': 'macd',
                'factor_name': 'MACD',
                'factor_category': 'momentum',
                'factor_desc': 'MACD指标（DIF值），快慢EMA的差值',
                'calculation_method': 'MACD = EMA(12) - EMA(26)',
                'data_source': 'K线数据',
                'is_active': True
            },
            {
                'factor_code': 'macd_signal',
                'factor_name': 'MACD信号线',
                'factor_category': 'momentum',
                'factor_desc': 'MACD信号线（DEA值），MACD的9日EMA',
                'calculation_method': 'Signal = EMA(MACD, 9)',
                'data_source': 'K线数据',
                'is_active': True
            },
            {
                'factor_code': 'macd_hist',
                'factor_name': 'MACD柱状图',
                'factor_category': 'momentum',
                'factor_desc': 'MACD柱状图，MACD与信号线的差值',
                'calculation_method': 'Histogram = MACD - Signal',
                'data_source': 'K线数据',
                'is_active': True
            },
            {
                'factor_code': 'beta',
                'factor_name': 'Beta系数',
                'factor_category': 'risk',
                'factor_desc': '相对于市场指数的系统性风险系数',
                'calculation_method': 'Beta = Cov(股票收益率, 市场收益率) / Var(市场收益率)',
                'data_source': 'K线数据',
                'is_active': True
            }
        ]
        
        added_count = 0
        for factor_data in new_factors:
            # 检查是否已存在
            existing = FactorLibrary.query.filter_by(
                factor_code=factor_data['factor_code']
            ).first()
            
            if not existing:
                factor = FactorLibrary(**factor_data)
                db.session.add(factor)
                print(f"✅ 添加因子: {factor_data['factor_name']} ({factor_data['factor_code']})")
                added_count += 1
            else:
                print(f"ℹ️  因子已存在: {factor_data['factor_name']} ({factor_data['factor_code']})")
        
        db.session.commit()
        
        print(f"\n✅ 迁移完成！新增 {added_count} 个因子")
        print("="*60 + "\n")
        
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    from app import create_app
    
    app = create_app()
    with app.app_context():
        migrate_add_technical_indicators()

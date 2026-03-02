"""
数据库初始化脚本 - StockQuant Pro v2.3
创建打分配置和信号策略配置表
"""
from utils.database import db, init_db
from models.scoring_config import ScoringConfig
from models.signal_strategy_config import SignalStrategyConfig
import json


def init_scoring_configs():
    """初始化默认打分配置"""
    default_configs = [
        {
            "name": "保守型打分方案",
            "description": "适合保守型投资者的打分配置，使用稳定的分位数排名方法",
            "normalization_method": "percentile",
            "outlier_method": "winsorize",
            "outlier_lower_bound": 0.01,
            "outlier_upper_bound": 0.99,
            "min_stocks": 50,
            "industry_neutral": False
        },
        {
            "name": "激进型打分方案",
            "description": "适合激进型投资者的打分配置，使用Z-Score保留原始分布特征",
            "normalization_method": "zscore",
            "outlier_method": "clip",
            "outlier_lower_bound": 0.05,
            "outlier_upper_bound": 0.95,
            "min_stocks": 30,
            "industry_neutral": False
        },
        {
            "name": "平衡型打分方案",
            "description": "平衡���打分配置，使用Min-Max标准化",
            "normalization_method": "minmax",
            "outlier_method": "winsorize",
            "outlier_lower_bound": 0.02,
            "outlier_upper_bound": 0.98,
            "min_stocks": 40,
            "industry_neutral": False
        }
    ]

    for config_data in default_configs:
        existing = ScoringConfig.query.filter_by(name=config_data["name"]).first()
        if not existing:
            config = ScoringConfig(**config_data)
            db.session.add(config)
            print(f"✓ 创建打分配置: {config_data['name']}")
        else:
            print(f"- 打分配置已存在: {config_data['name']}")

    db.session.commit()


def init_signal_strategies():
    """初始化默认信号策略"""
    default_strategies = [
        {
            "name": "保守型买卖策略",
            "description": "追求稳定收益，控制风险",
            "buy_strategy_type": "threshold",
            "buy_params": json.dumps({"min_score": 80, "max_rank": 30}),
            "sell_take_profit_ratio": 0.10,
            "sell_stop_loss_ratio": -0.05,
            "sell_rank_out": 50,
            "sell_score_below": 70,
            "sell_enable_technical": False,
            "position_method": "equal",
            "max_positions": 15,
            "single_position_max_ratio": 0.1
        },
        {
            "name": "激进型买卖策略",
            "description": "追求高收益，能承受高波动",
            "buy_strategy_type": "top_n",
            "buy_params": json.dumps({"top_n": 15}),
            "sell_take_profit_ratio": 0.20,
            "sell_stop_loss_ratio": -0.10,
            "sell_rank_out": 20,
            "sell_score_below": 60,
            "sell_enable_technical": False,
            "position_method": "score_weighted",
            "max_positions": 10,
            "single_position_max_ratio": 0.2
        },
        {
            "name": "多因子共振策略",
            "description": "多个因子同时满足条件才买入，更加严格",
            "buy_strategy_type": "multi_factor_resonance",
            "buy_params": json.dumps({
                "factor_rules": {
                    "return_20d": {"min": 10, "direction": "long"},
                    "pe_ratio": {"min": 30, "direction": "short"}
                }
            }),
            "sell_take_profit_ratio": 0.15,
            "sell_stop_loss_ratio": -0.08,
            "sell_rank_out": 30,
            "sell_score_below": 65,
            "sell_enable_technical": False,
            "position_method": "equal",
            "max_positions": 10,
            "single_position_max_ratio": 0.15
        }
    ]

    for strategy_data in default_strategies:
        existing = SignalStrategyConfig.query.filter_by(name=strategy_data["name"]).first()
        if not existing:
            strategy = SignalStrategyConfig(**strategy_data)
            db.session.add(strategy)
            print(f"✓ 创建信号策略: {strategy_data['name']}")
        else:
            print(f"- 信号策略已存在: {strategy_data['name']}")

    db.session.commit()


def init_v23_data():
    """初始化v2.3数据"""
    print("\n" + "="*50)
    print("初始化 v2.3 多因子打分回测系统数据")
    print("="*50 + "\n")

    print("1. 初始化打分配置...")
    init_scoring_configs()

    print("\n2. 初始化信号策略...")
    init_signal_strategies()

    print("\n✓ v2.3 数据初始化完成！")
    print("="*50 + "\n")


if __name__ == "__main__":
    from app import create_app
    app = create_app()

    with app.app_context():
        # 先创建所有表（如果不存在）
        db.create_all()
        print("✓ 数据库表检查完成\n")

        # 初始化v2.3数据
        init_v23_data()

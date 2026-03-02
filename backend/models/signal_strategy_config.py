"""
信号策略配置模型 - StockQuant Pro
买入卖出信号策略配置
"""
from datetime import datetime
from utils.database import db
import json


class SignalStrategyConfig(db.Model):
    """信号策略配置表"""

    __tablename__ = "signal_strategy_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    # 买入策略
    buy_strategy_type = db.Column(db.String(50), default='top_n')  # top_n/threshold/multi_factor_resonance/technical_breakout
    buy_params = db.Column(db.Text)  # JSON: {"top_n": 20} or {"factor_rules": {...}}

    # 卖出策略
    sell_take_profit_ratio = db.Column(db.Float, default=0.15)
    sell_stop_loss_ratio = db.Column(db.Float, default=-0.08)
    sell_rank_out = db.Column(db.Integer, default=30)
    sell_score_below = db.Column(db.Float)
    sell_enable_technical = db.Column(db.Boolean, default=False)
    sell_technical_params = db.Column(db.Text)  # JSON

    # 仓位管理
    position_method = db.Column(db.String(20), default='equal')  # equal/score_weighted
    max_positions = db.Column(db.Integer, default=10)
    single_position_max_ratio = db.Column(db.Float, default=0.2)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """转为字典，供 API 返回"""
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "buy_strategy_type": self.buy_strategy_type,
            "sell_take_profit_ratio": self.sell_take_profit_ratio,
            "sell_stop_loss_ratio": self.sell_stop_loss_ratio,
            "sell_rank_out": self.sell_rank_out,
            "sell_score_below": self.sell_score_below,
            "sell_enable_technical": self.sell_enable_technical,
            "position_method": self.position_method,
            "max_positions": self.max_positions,
            "single_position_max_ratio": self.single_position_max_ratio,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        # 解析 JSON 字段
        try:
            d["buy_params"] = json.loads(self.buy_params) if self.buy_params else {}
        except:
            d["buy_params"] = {}
        try:
            d["sell_technical_params"] = json.loads(self.sell_technical_params) if self.sell_technical_params else {}
        except:
            d["sell_technical_params"] = {}
        return d

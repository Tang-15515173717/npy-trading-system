"""
每日推荐记录模型
记录每天收盘后生成的明日操作建议，便于追溯和对比
"""
from datetime import datetime
from utils.database import db


class DailyRecommendation(db.Model):
    """每日推荐记录"""
    __tablename__ = "daily_recommendations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    strategy_id = db.Column(db.Integer, nullable=False, index=True)
    strategy_name = db.Column(db.String(100))
    
    # 日期信息
    record_date = db.Column(db.String(8), nullable=False, index=True)  # 记录日期（收盘后）
    execution_date = db.Column(db.String(8), nullable=False)  # 执行日期（明天）
    
    # 资产信息
    total_value = db.Column(db.Float)
    cash = db.Column(db.Float)
    
    # 持仓信息（JSON）
    holdings = db.Column(db.Text)  # [{ts_code, name, buy_price, current_price, volume}]
    
    # 明日推荐信息（JSON）
    buy_signals = db.Column(db.Text)  # [{ts_code, name, price, volume, reason}]
    sell_signals = db.Column(db.Text)  # [{ts_code, name, price, volume, reason}]
    
    # 元数据
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # 唯一约束：同一策略同一天只能有一条记录
    __table_args__ = (
        db.UniqueConstraint('strategy_id', 'record_date', name='uix_strategy_record_date'),
    )

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "record_date": self.record_date,
            "execution_date": self.execution_date,
            "total_value": self.total_value,
            "cash": self.cash,
            "holdings": json.loads(self.holdings) if self.holdings else [],
            "buy_signals": json.loads(self.buy_signals) if self.buy_signals else [],
            "sell_signals": json.loads(self.sell_signals) if self.sell_signals else [],
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None
        }

"""
因子IC模型 - Factor IC
存储因子IC值时序数据
"""
from utils.database import db
from datetime import datetime


class FactorIC(db.Model):
    """因子IC表 - 存储因子IC值的时间序列"""
    
    __tablename__ = 'factor_ic'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    factor_code = db.Column(db.String(50), nullable=False, index=True)
    trade_date = db.Column(db.String(8), nullable=False, index=True)
    ic_value = db.Column(db.Float)       # IC值
    rank_ic = db.Column(db.Float)        # RankIC值
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    __table_args__ = (
        db.UniqueConstraint('factor_code', 'trade_date', name='unique_factor_date'),
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'factor_code': self.factor_code,
            'trade_date': self.trade_date,
            'ic_value': self.ic_value,
            'rank_ic': self.rank_ic,
        }

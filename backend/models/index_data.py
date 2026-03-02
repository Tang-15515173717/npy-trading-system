"""
指数数据模型
存储日K线数据用于回测和历史图表
"""
from utils.database import db
from datetime import datetime


class IndexDaily(db.Model):
    """指数日K线数据"""
    __tablename__ = 'index_daily'
    
    id = db.Column(db.Integer, primary_key=True)
    ts_code = db.Column(db.String(20), nullable=False, index=True, comment='指数代码 000001.SH')
    trade_date = db.Column(db.String(8), nullable=False, index=True, comment='交易日期 20260130')
    open = db.Column(db.Float, comment='开盘价')
    close = db.Column(db.Float, comment='收盘价')
    high = db.Column(db.Float, comment='最高价')
    low = db.Column(db.Float, comment='最低价')
    volume = db.Column(db.BigInteger, comment='成交量')
    amount = db.Column(db.Float, comment='成交额')
    change_pct = db.Column(db.Float, comment='涨跌幅%')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    
    # 唯一约束：同一指数同一天只能有一条记录
    __table_args__ = (
        db.UniqueConstraint('ts_code', 'trade_date', name='uq_index_date'),
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'ts_code': self.ts_code,
            'trade_date': self.trade_date,
            'open': self.open,
            'close': self.close,
            'high': self.high,
            'low': self.low,
            'volume': self.volume,
            'amount': self.amount,
            'change_pct': self.change_pct,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
    
    def __repr__(self):
        return f'<IndexDaily {self.ts_code} {self.trade_date}>'

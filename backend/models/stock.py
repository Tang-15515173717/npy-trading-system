"""
股票基本信息模型 - StockQuant Pro
对应 README 中 stocks 表结构，兼容 SQLite。
"""
from datetime import datetime
from utils.database import db


class Stock(db.Model):
    """股票基本信息"""

    __tablename__ = "stocks"

    ts_code = db.Column(db.String(20), primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    area = db.Column(db.String(20))
    industry = db.Column(db.String(50))
    market = db.Column(db.String(20))
    exchange = db.Column(db.String(10), nullable=False)
    list_date = db.Column(db.String(8))
    list_status = db.Column(db.String(1), default="L")
    stock_type = db.Column(db.String(10), default="normal", comment="股票类型: key=重点股票(沪深300),normal=普通股票")
    has_full_data = db.Column(db.Boolean, default=False, comment="是否有完整历史数据(用于回测)")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """转为字典，供 API 返回"""
        return {
            "ts_code": self.ts_code,
            "symbol": self.symbol,
            "name": self.name,
            "area": self.area,
            "industry": self.industry,
            "market": self.market,
            "exchange": self.exchange,
            "list_date": self.list_date,
            "stock_type": self.stock_type,
            "has_full_data": self.has_full_data,
        }

    def __repr__(self) -> str:
        return f"<Stock {self.ts_code} {self.name}>"

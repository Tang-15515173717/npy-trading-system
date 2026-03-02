"""
K 线数据模型 - StockQuant Pro
对应 README 中 bar_data 表结构，兼容 SQLite。
"""
from utils.database import db


class BarData(db.Model):
    """K 线数据"""

    __tablename__ = "bar_data"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ts_code = db.Column(db.String(20), nullable=False, index=True)
    trade_date = db.Column(db.String(8), nullable=False, index=True)
    open = db.Column(db.Numeric(10, 2), nullable=False)
    high = db.Column(db.Numeric(10, 2), nullable=False)
    low = db.Column(db.Numeric(10, 2), nullable=False)
    close = db.Column(db.Numeric(10, 2), nullable=False)
    pre_close = db.Column(db.Numeric(10, 2))
    change = db.Column(db.Numeric(10, 2))
    pct_chg = db.Column(db.Numeric(10, 2))
    vol = db.Column(db.Numeric(20, 2))
    amount = db.Column(db.Numeric(20, 2))
    freq = db.Column(db.String(1), default="D")
    created_at = db.Column(db.DateTime, default=db.func.now())

    __table_args__ = (db.UniqueConstraint("ts_code", "trade_date", "freq", name="uk_code_date_freq"),)

    def to_dict(self) -> dict:
        """转为字典，供 API 返回"""
        return {
            "ts_code": self.ts_code,
            "trade_date": self.trade_date,
            "open": float(self.open) if self.open is not None else None,
            "high": float(self.high) if self.high is not None else None,
            "low": float(self.low) if self.low is not None else None,
            "close": float(self.close) if self.close is not None else None,
            "pre_close": float(self.pre_close) if self.pre_close is not None else None,
            "change": float(self.change) if self.change is not None else None,
            "pct_chg": float(self.pct_chg) if self.pct_chg is not None else None,
            "vol": float(self.vol) if self.vol is not None else None,
            "amount": float(self.amount) if self.amount is not None else None,
        }

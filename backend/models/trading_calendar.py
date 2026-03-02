"""
交易日历模型 - StockQuant Pro
用于存储A股交易日历，判断是否为交易日
"""
from datetime import datetime
from utils.database import db


class TradingCalendar(db.Model):
    """交易日历"""

    __tablename__ = "trading_calendar"

    cal_date = db.Column(db.String(8), primary_key=True, comment="日历日期 YYYYMMDD")
    is_trading_day = db.Column(db.Boolean, default=True, nullable=False, comment="是否为交易日")
    is_weekend = db.Column(db.Boolean, default=False, comment="是否为周末")
    is_holiday = db.Column(db.Boolean, default=False, comment="是否为节假日")
    holiday_name = db.Column(db.String(50), comment="节假日名称，如：春节、国庆节")
    exchange = db.Column(db.String(10), default="SSE", comment="交易所，SSE=上交所,SZSE=深交所")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def to_dict(self) -> dict:
        """转为字典，供 API 返回"""
        return {
            "cal_date": self.cal_date,
            "is_trading_day": self.is_trading_day,
            "is_weekend": self.is_weekend,
            "is_holiday": self.is_holiday,
            "holiday_name": self.holiday_name,
            "exchange": self.exchange,
        }

    def __repr__(self) -> str:
        status = "交易日" if self.is_trading_day else f"非交易日({self.holiday_name or '周末'})"
        return f"<TradingCalendar {self.cal_date} {status}>"

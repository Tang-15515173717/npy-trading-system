"""
模拟交易模型 - StockQuant Pro
对应 README 中 simulation_sessions、simulation_positions、simulation_trades 表结构，兼容 SQLite。
"""
from datetime import datetime as dt
from utils.database import db


class SimulationSession(db.Model):
    """模拟交易会话模型"""

    __tablename__ = "simulation_sessions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(50), unique=True, nullable=False)
    strategy_id = db.Column(db.Integer, nullable=False, index=True)
    strategy_name = db.Column(db.String(100), nullable=False)
    initial_capital = db.Column(db.Numeric(15, 2), nullable=False)
    current_capital = db.Column(db.Numeric(15, 2))
    status = db.Column(db.String(20), default="running", index=True)
    started_at = db.Column(db.DateTime, default=dt.utcnow)
    stopped_at = db.Column(db.DateTime)

    def to_dict(self) -> dict:
        """转为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "initial_capital": float(self.initial_capital) if self.initial_capital else None,
            "current_capital": float(self.current_capital) if self.current_capital else None,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
        }


class SimulationPosition(db.Model):
    """模拟交易持仓模型"""

    __tablename__ = "simulation_positions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(50), nullable=False, index=True)
    ts_code = db.Column(db.String(20), nullable=False)
    volume = db.Column(db.Integer, nullable=False)
    available = db.Column(db.Integer, nullable=False)
    cost_price = db.Column(db.Numeric(10, 2), nullable=False)
    current_price = db.Column(db.Numeric(10, 2))
    market_value = db.Column(db.Numeric(15, 2))
    pnl = db.Column(db.Numeric(15, 2))
    pnl_pct = db.Column(db.Numeric(10, 2))
    updated_at = db.Column(db.DateTime, default=dt.utcnow, onupdate=dt.utcnow)

    __table_args__ = (
        db.UniqueConstraint("session_id", "ts_code", name="uk_session_code"),
    )

    def to_dict(self) -> dict:
        """转为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "ts_code": self.ts_code,
            "volume": self.volume,
            "available": self.available,
            "cost_price": float(self.cost_price) if self.cost_price else None,
            "current_price": float(self.current_price) if self.current_price else None,
            "market_value": float(self.market_value) if self.market_value else None,
            "pnl": float(self.pnl) if self.pnl else None,
            "pnl_pct": float(self.pnl_pct) if self.pnl_pct else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SimulationTrade(db.Model):
    """模拟交易记录模型"""

    __tablename__ = "simulation_trades"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(50), nullable=False, index=True)
    datetime = db.Column(db.DateTime, nullable=False, index=True)
    ts_code = db.Column(db.String(20), nullable=False, index=True)
    direction = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    volume = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    commission = db.Column(db.Numeric(10, 2))
    created_at = db.Column(db.DateTime, default=dt.utcnow)

    def to_dict(self) -> dict:
        """转为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "datetime": self.datetime.isoformat() if self.datetime else None,
            "ts_code": self.ts_code,
            "direction": self.direction,
            "price": float(self.price) if self.price else None,
            "volume": self.volume,
            "amount": float(self.amount) if self.amount else None,
            "commission": float(self.commission) if self.commission else None,
        }

"""
每日模拟观测系统 - 数据库模型
============================
用于记录每日模拟观测的策略配置、观测记录和模拟交易。

功能：
1. 策略配置：配置观测的策略（使用哪个因子组合、参数等）
2. 每日观测：记录每日观测的状态、选股结果、资金情况
3. 模拟交易：记录模拟的买入/卖出操作
4. 数据补齐：跟踪哪些日期已处理，启动时自动补齐

作者：Claude Code
日期：2026-02-11
"""
from datetime import datetime
from utils.database import db
import json


class DailyObserverStrategy(db.Model):
    """
    观测策略配置表

    用于配置要观测的策略，每个策略独立运行、独立展示。
    """

    __tablename__ = "daily_observer_strategies"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, comment="租户ID（SaaS多租户隔离）")
    name = db.Column(db.String(100), nullable=False, comment="策略名称")
    description = db.Column(db.Text, comment="策略描述")

    # 策略配置
    factor_combo_id = db.Column(db.Integer, nullable=False, comment="因子组合ID")
    scoring_engine_id = db.Column(db.String(50), default="simple_conservative", comment="打分引擎ID")

    # 选股参数
    stock_pool = db.Column(db.Text, comment="股票池JSON，默认使用150只优质股票")
    top_n = db.Column(db.Integer, default=15, comment="每日选股数量")
    max_positions = db.Column(db.Integer, default=7, comment="最大持仓数量")

    # 交易参数
    take_profit_ratio = db.Column(db.Float, default=0.15, comment="止盈比例")
    stop_loss_ratio = db.Column(db.Float, default=-0.08, comment="止损比例")
    sell_rank_out = db.Column(db.Integer, default=50, comment="排名跌出多少名则卖出")
    signal_confirm_days = db.Column(db.Integer, default=1, comment="信号确认天数")
    blacklist_cooldown = db.Column(db.Integer, default=30, comment="黑名单冷却天数")
    rank_drop_threshold = db.Column(db.Integer, default=15, comment="排名下降超过N位则卖出")
    initial_capital = db.Column(db.Float, default=1000000.0, comment="初始资金")

    # 运行状态
    status = db.Column(db.String(20), default="active", comment="active/inactive/paused")
    last_run_date = db.Column(db.String(8), comment="上次运行的日期")
    start_date = db.Column(db.String(8), default="20250901", comment="观测起始日期（YYYYMMDD格式）")

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联关系
    records = db.relationship("DailyObserverRecord", backref="strategy", lazy="dynamic",
                             cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """转为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "factor_combo_id": self.factor_combo_id,
            "scoring_engine_id": self.scoring_engine_id,
            "stock_pool": json.loads(self.stock_pool) if self.stock_pool else [],
            "top_n": self.top_n,
            "max_positions": self.max_positions,
            "take_profit_ratio": self.take_profit_ratio,
            "stop_loss_ratio": self.stop_loss_ratio,
            "sell_rank_out": self.sell_rank_out,
            "signal_confirm_days": self.signal_confirm_days,
            "blacklist_cooldown": self.blacklist_cooldown,
            "rank_drop_threshold": self.rank_drop_threshold if self.rank_drop_threshold else 15,
            "initial_capital": self.initial_capital if self.initial_capital else 1000000.0,
            "status": self.status,
            "last_run_date": self.last_run_date,
            "start_date": self.start_date,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DailyObserverRecord(db.Model):
    """
    每日观测记录表

    记录每日的观测结果，包括选股、收益、资金等信息。
    """

    __tablename__ = "daily_observer_records"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey("daily_observer_strategies.id"), nullable=False)

    # 日期信息
    date = db.Column(db.String(8), nullable=False, comment="观测日期 YYYYMMDD")

    # 选股结果
    selected_stocks = db.Column(db.Text, comment="当日选出的股票JSON")
    scores = db.Column(db.Text, comment="当日各股票得分JSON")

    # 资金情况
    capital = db.Column(db.Numeric(15, 2), default=1000000, comment="当前资金")
    position_value = db.Column(db.Numeric(15, 2), default=0, comment="持仓市值")
    cash = db.Column(db.Numeric(15, 2), default=0, comment="可用资金")

    # 收益统计
    day_return = db.Column(db.Float, default=0, comment="当日收益率")
    cumulative_return = db.Column(db.Float, default=0, comment="累计收益率")
    total_value = db.Column(db.Numeric(15, 2), default=0, comment="总资产（资金+持仓）")

    # 持仓信息
    holdings = db.Column(db.Text, comment="当前持仓JSON")
    holding_count = db.Column(db.Integer, default=0, comment="持仓数量")

    # 状态
    status = db.Column(db.String(20), default="pending", comment="pending/running/completed")
    error_msg = db.Column(db.Text, comment="错误信息")

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联关系
    trades = db.relationship("DailyObserverTrade", backref="record", lazy="dynamic",
                            cascade="all, delete-orphan")

    # 联合唯一约束
    __table_args__ = (
        db.UniqueConstraint('strategy_id', 'date', name='uq_strategy_date'),
    )

    def to_dict(self) -> dict:
        """转为字典"""
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "date": self.date,
            "selected_stocks": json.loads(self.selected_stocks) if self.selected_stocks else [],
            "scores": json.loads(self.scores) if self.scores else {},
            "capital": float(self.capital) if self.capital else 0,
            "position_value": float(self.position_value) if self.position_value else 0,
            "cash": float(self.cash) if self.cash else 0,
            "day_return": float(self.day_return) if self.day_return else 0,
            "cumulative_return": float(self.cumulative_return) if self.cumulative_return else 0,
            "total_value": float(self.total_value) if self.total_value else 0,
            "holdings": json.loads(self.holdings) if self.holdings else [],
            "holding_count": self.holding_count or 0,
            "status": self.status,
            "error_msg": self.error_msg,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DailyObserverTrade(db.Model):
    """
    模拟交易记录表

    记录每个策略的模拟买卖操作。
    """

    __tablename__ = "daily_observer_trades"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey("daily_observer_strategies.id"), nullable=False)
    record_id = db.Column(db.Integer, db.ForeignKey("daily_observer_records.id", ondelete="CASCADE"), nullable=False)

    # 交易信息
    date = db.Column(db.String(8), nullable=False, comment="交易日期")
    ts_code = db.Column(db.String(20), nullable=False, comment="股票代码")
    direction = db.Column(db.String(10), nullable=False, comment="buy/sell")
    price = db.Column(db.Numeric(10, 2), nullable=False, comment="成交价格")
    volume = db.Column(db.Integer, nullable=False, comment="成交数量")
    amount = db.Column(db.Numeric(15, 2), nullable=False, comment="成交金额")
    commission = db.Column(db.Numeric(10, 2), default=0, comment="手续费")

    # 信号信息
    signal_reason = db.Column(db.String(100), comment="触发原因")
    composite_score = db.Column(db.Float, comment="综合得分")
    rank = db.Column(db.Integer, comment="当日排名")

    # 持仓信息
    position_id = db.Column(db.String(50), comment="持仓ID，用于追踪")

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        """转为字典"""
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "record_id": self.record_id,
            "date": self.date,
            "ts_code": self.ts_code,
            "direction": self.direction,
            "price": float(self.price) if self.price else None,
            "volume": self.volume,
            "amount": float(self.amount) if self.amount else None,
            "commission": float(self.commission) if self.commission else 0,
            "signal_reason": self.signal_reason,
            "composite_score": float(self.composite_score) if self.composite_score else None,
            "rank": self.rank,
            "position_id": self.position_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

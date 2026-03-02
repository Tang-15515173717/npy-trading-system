"""
回测模型 - StockQuant Pro
回测任务与交易记录，对应 README 中 backtest_tasks 和 backtest_trades 表结构，兼容 SQLite。
"""
from datetime import datetime
from utils.database import db
import json


class BacktestTask(db.Model):
    """回测任务模型"""

    __tablename__ = "backtest_tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True, index=True, comment="租户ID")  # 🆕 SaaS租户隔离
    task_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    strategy_id = db.Column(db.Integer, nullable=True, index=True)  # 🆕 v2.3.1: 改为可空，支持因子打分回测模式
    strategy_name = db.Column(db.String(100), nullable=True)  # 🆕 v2.3.1: 改为可空
    factor_combo_id = db.Column(db.Integer, nullable=True, index=True)  # v2.1 双驱动：因子组合ID，空为仅策略
    stocks = db.Column(db.Text, nullable=False)  # JSON 字符串
    start_date = db.Column(db.String(8), nullable=False)
    end_date = db.Column(db.String(8), nullable=False)
    initial_capital = db.Column(db.Numeric(15, 2), default=1000000)
    commission = db.Column(db.Numeric(6, 6), default=0.0003)
    slippage = db.Column(db.Numeric(5, 2), default=0.01)
    benchmark = db.Column(db.String(20))
    status = db.Column(db.String(20), default="pending", index=True)
    progress = db.Column(db.Integer, default=0)
    result = db.Column(db.Text)  # JSON 字符串
    error_msg = db.Column(db.Text)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # v2.3 多因子打分回测系统扩展
    scoring_config_id = db.Column(db.Integer, nullable=True, index=True)  # 打分配置ID
    signal_strategy_id = db.Column(db.Integer, nullable=True, index=True)  # 信号策略ID
    # v2.4 AI 智能总结（DeepSeek 大模型生成，持久化存储）
    ai_summary = db.Column(db.Text, nullable=True)  # markdown 格式的 AI 分析报告
    ai_summary_at = db.Column(db.DateTime, nullable=True)  # AI 总结生成时间
    # v2.5 打分引擎版本化
    scoring_engine_id = db.Column(db.String(50), nullable=True)  # 使用的打分引擎版本ID
    # v2.6 回测参数完整记录
    backtest_params = db.Column(db.Text, nullable=True)  # JSON: top_n, max_positions, stop_loss 等
    factor_combo_name = db.Column(db.String(100), nullable=True)  # 因子组合名称快照

    def to_dict(self) -> dict:
        """转为字典，供 API 返回"""
        # 🆕 v2.3.1: 添加类型转换的安全处理，防止旧数据字段错误导致崩溃
        def safe_float(value, default=0.0):
            """安全地将值转换为float"""
            try:
                if value is None:
                    return default
                # 如果是字符串，尝试转换
                if isinstance(value, str):
                    value = value.strip()
                    # 空字符串返回默认值
                    if not value:
                        return default
                    # 检查是否看起来像股票代码（包含字母且有点）
                    if '.' in value and any(c.isalpha() for c in value):
                        return default  # 这是股票代码，不是数字
                    return float(value)
                return float(value)
            except (ValueError, TypeError):
                return default

        # 🆕 v2.3.1: 安全的日期格式化函数
        def safe_datetime_format(dt):
            """安全地将datetime对象格式化为ISO字符串"""
            if dt is None:
                return None
            try:
                if isinstance(dt, str):
                    return dt
                return dt.isoformat()
            except Exception:
                return None

        result_dict = {
            "id": self.id,
            "tenant_id": self.tenant_id,  # 🆕 租户ID
            "task_id": self.task_id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "factor_combo_id": self.factor_combo_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": safe_float(self.initial_capital, 1000000),
            "commission": safe_float(self.commission, 0.0003),
            "slippage": safe_float(self.slippage, 0.001),
            "benchmark": str(self.benchmark) if self.benchmark else None,
            "status": str(self.status) if self.status else "unknown",
            "progress": int(self.progress) if self.progress is not None else 0,
            "error_msg": self.error_msg,
            "started_at": safe_datetime_format(self.started_at),
            "completed_at": safe_datetime_format(self.completed_at),
            "created_at": safe_datetime_format(self.created_at),
            # v2.3 多因子打分回测系统扩展
            "scoring_config_id": self.scoring_config_id,
            "signal_strategy_id": self.signal_strategy_id,
            # v2.4 AI 总结
            "ai_summary": self.ai_summary,
            "ai_summary_at": safe_datetime_format(self.ai_summary_at),
            # v2.5 打分引擎版本
            "scoring_engine_id": self.scoring_engine_id,
            # v2.6 回测参数
            "backtest_params": json.loads(self.backtest_params) if self.backtest_params else None,
            "factor_combo_name": self.factor_combo_name,
        }
        # 解析 JSON 字段
        try:
            if self.stocks:
                parsed = json.loads(self.stocks)
                # 🆕 确保返回的是数组
                result_dict["stocks"] = parsed if isinstance(parsed, list) else []
            else:
                result_dict["stocks"] = []
        except:
            result_dict["stocks"] = []
        try:
            result_dict["result"] = json.loads(self.result) if self.result else None
        except:
            result_dict["result"] = None
        return result_dict


class BacktestTrade(db.Model):
    """回测交易记录模型"""

    __tablename__ = "backtest_trades"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True, index=True, comment="租户ID")  # 🆕 SaaS租户隔离
    task_id = db.Column(db.String(50), nullable=False, index=True)
    trade_date = db.Column(db.String(8), nullable=False)
    ts_code = db.Column(db.String(20), nullable=False, index=True)
    direction = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    volume = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    commission = db.Column(db.Numeric(10, 2))
    factor_combo_id = db.Column(db.Integer, nullable=True)
    factor_combo_name = db.Column(db.String(100), nullable=True)
    strategy_id = db.Column(db.Integer, nullable=True)
    strategy_name = db.Column(db.String(100), nullable=True)
    signal_reason = db.Column(db.String(50), nullable=True)
    composite_score = db.Column(db.Float, nullable=True)  # v2.2 该笔交易时的因子综合分，便于复盘
    rank = db.Column(db.Integer, nullable=True)  # v2.2 该笔交易时在当日候选池中的排名（1-based）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        """转为字典；含 date/stock 别名便于前端与 API 文档一致"""
        d = {
            "id": self.id,
            "tenant_id": self.tenant_id,  # 🆕 租户ID
            "task_id": self.task_id,
            "trade_date": self.trade_date,
            "ts_code": self.ts_code,
            "direction": self.direction,
            "price": float(self.price) if self.price else None,
            "volume": self.volume,
            "amount": float(self.amount) if self.amount else None,
            "commission": float(self.commission) if self.commission else None,
            "factor_combo_id": self.factor_combo_id,
            "factor_combo_name": self.factor_combo_name,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "signal_reason": self.signal_reason,
            "composite_score": float(self.composite_score) if self.composite_score is not None else None,
            "rank": self.rank,
        }
        d["date"] = self.trade_date
        d["stock"] = self.ts_code
        return d

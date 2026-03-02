"""
策略模型 - StockQuant Pro
对应 README 中 strategies 表结构，兼容 SQLite。
"""
from datetime import datetime
from utils.database import db
import json


class Strategy(db.Model):
    """策略模型"""

    __tablename__ = "strategies"
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True, index=True, comment="租户ID")  # 🆕 SaaS租户隔离

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False, index=True)
    status = db.Column(db.String(20), default="draft", index=True)
    description = db.Column(db.Text)
    params = db.Column(db.Text)  # JSON 字符串
    code = db.Column(db.Text)
    backtest_result = db.Column(db.Text)  # JSON 字符串
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """转为字典，供 API 返回"""
        result = {
            "id": self.id,
            "tenant_id": self.tenant_id,  # 🆕 租户ID
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        # 解析 JSON 字段
        try:
            result["params"] = json.loads(self.params) if self.params else None
        except:
            result["params"] = None
        try:
            result["backtest_result"] = json.loads(self.backtest_result) if self.backtest_result else None
        except:
            result["backtest_result"] = None
        return result

    def __repr__(self) -> str:
        return f"<Strategy {self.id} {self.name}>"

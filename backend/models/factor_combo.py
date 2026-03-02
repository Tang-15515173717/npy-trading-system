"""
因子组合模型 - StockQuant Pro
双驱动：可保存的选股方案（因子配置 + 选股规则）。
"""
from datetime import datetime
from utils.database import db
import json


class FactorCombo(db.Model):
    """因子组合表"""

    __tablename__ = "factor_combo"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    factor_config = db.Column(db.Text, nullable=False)  # JSON: {"factors": [{"factor_code": "return_20d", "params": {"n": 20}}]}
    selection_rule = db.Column(db.Text, nullable=False)   # JSON: {"type": "topk", "k": 50} or {"type": "threshold", "field": "return_20d", "min": 0.05}
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """转为字典，供 API 返回"""
        d = {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        try:
            d["factor_config"] = json.loads(self.factor_config) if self.factor_config else {}
        except Exception:
            d["factor_config"] = {}
        try:
            d["selection_rule"] = json.loads(self.selection_rule) if self.selection_rule else {}
        except Exception:
            d["selection_rule"] = {}
        return d

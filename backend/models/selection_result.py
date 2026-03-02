"""
选股结果快照模型 - StockQuant Pro
按交易日 + 因子组合产出的候选股票列表，供回测与选股历史查询。
"""
from datetime import datetime
from utils.database import db
import json


class SelectionResult(db.Model):
    """选股结果表（按日快照）"""

    __tablename__ = "selection_result"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    trade_date = db.Column(db.String(8), nullable=False, index=True)  # YYYYMMDD
    factor_combo_id = db.Column(db.Integer, nullable=False, index=True)
    stock_list = db.Column(db.Text, nullable=False)  # JSON: ["000001.SZ", ...] or [{"ts_code","name","rank","score"}]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        """转为字典"""
        d = {
            "id": self.id,
            "trade_date": self.trade_date,
            "factor_combo_id": self.factor_combo_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        try:
            d["stock_list"] = json.loads(self.stock_list) if self.stock_list else []
        except Exception:
            d["stock_list"] = []
        return d

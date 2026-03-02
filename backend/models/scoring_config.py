"""
打分配置模型 - StockQuant Pro
因子标准化和打分方法配置
"""
from datetime import datetime
from utils.database import db


class ScoringConfig(db.Model):
    """打分配置表"""

    __tablename__ = "scoring_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    # 标准化方法
    normalization_method = db.Column(db.String(20), default='percentile')  # zscore/minmax/percentile

    # 极端值处理
    outlier_method = db.Column(db.String(20), default='winsorize')  # winsorize/trim/clip
    outlier_lower_bound = db.Column(db.Float, default=0.01)
    outlier_upper_bound = db.Column(db.Float, default=0.99)

    # 其他参数
    min_stocks = db.Column(db.Integer, default=50)
    industry_neutral = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """转为字典，供 API 返回"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "normalization_method": self.normalization_method,
            "outlier_method": self.outlier_method,
            "outlier_lower_bound": self.outlier_lower_bound,
            "outlier_upper_bound": self.outlier_upper_bound,
            "min_stocks": self.min_stocks,
            "industry_neutral": self.industry_neutral,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

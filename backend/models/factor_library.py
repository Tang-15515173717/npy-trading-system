"""
因子库模型 - Factor Library
存储因子元数据和统计信息
"""
from utils.database import db
from datetime import datetime


class FactorLibrary(db.Model):
    """因子库表 - 存储因子定义和有效性指标"""
    
    __tablename__ = 'factor_library'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    factor_code = db.Column(db.String(50), nullable=False, unique=True, index=True)
    factor_name = db.Column(db.String(100), nullable=False)
    factor_category = db.Column(db.String(20), nullable=False, index=True)
    factor_desc = db.Column(db.Text)
    calculation_method = db.Column(db.Text)
    data_source = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    # 因子有效性指标
    ic_mean = db.Column(db.Float)        # 平均IC值
    ir_value = db.Column(db.Float)       # IR值（信息比率）
    win_rate = db.Column(db.Float)       # 胜率
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'factor_code': self.factor_code,
            'factor_name': self.factor_name,
            'factor_category': self.factor_category,
            'factor_desc': self.factor_desc,
            'calculation_method': self.calculation_method,
            'data_source': self.data_source,
            'is_active': self.is_active,
            'ic_mean': self.ic_mean,
            'ir_value': self.ir_value,
            'win_rate': self.win_rate,
        }

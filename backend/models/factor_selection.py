"""
因子选股记录模型 - Factor Selection
存储因子选股的历史记录
"""
from utils.database import db
from datetime import datetime
import json


class FactorSelection(db.Model):
    """因子选股记录表"""
    
    __tablename__ = 'factor_selection'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    selection_name = db.Column(db.String(100), nullable=False)
    selection_date = db.Column(db.String(8), nullable=False, index=True)
    factor_config = db.Column(db.Text, nullable=False)  # JSON格式
    stock_count = db.Column(db.Integer)
    selected_stocks = db.Column(db.Text)  # JSON格式
    avg_score = db.Column(db.Float)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def get_factor_config(self):
        """获取因子配置（解析JSON）"""
        if self.factor_config:
            return json.loads(self.factor_config)
        return {}
    
    def set_factor_config(self, config: dict):
        """设置因子配置（转为JSON）"""
        self.factor_config = json.dumps(config, ensure_ascii=False)
    
    def get_selected_stocks(self):
        """获取选中的股票列表（解析JSON）"""
        if self.selected_stocks:
            return json.loads(self.selected_stocks)
        return []
    
    def set_selected_stocks(self, stocks: list):
        """设置选中的股票列表（转为JSON）"""
        self.selected_stocks = json.dumps(stocks, ensure_ascii=False)
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'selection_name': self.selection_name,
            'selection_date': self.selection_date,
            'factor_config': self.get_factor_config(),
            'stock_count': self.stock_count,
            'selected_stocks': self.get_selected_stocks(),
            'avg_score': self.avg_score,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }

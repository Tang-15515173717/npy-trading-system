"""
产业链模型 - Supply Chain
存储产业链关系和龙头股票
"""
from utils.database import db
from datetime import datetime


class SupplyChain(db.Model):
    """产业链表"""
    
    __tablename__ = 'supply_chain'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    chain_name = db.Column(db.String(100), nullable=False, index=True)
    ts_code = db.Column(db.String(20), nullable=False, index=True)
    chain_position = db.Column(db.String(50))  # 如：上游-锂矿、中游-电池
    upstream_stocks = db.Column(db.Text)       # JSON格式：上游股票列表
    downstream_stocks = db.Column(db.Text)     # JSON格式：下游股票列表
    is_leader = db.Column(db.Boolean, default=False, index=True)
    industry = db.Column(db.String(50))
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        """转换为字典"""
        import json
        return {
            'id': self.id,
            'chain_name': self.chain_name,
            'ts_code': self.ts_code,
            'chain_position': self.chain_position,
            'upstream_stocks': json.loads(self.upstream_stocks) if self.upstream_stocks else [],
            'downstream_stocks': json.loads(self.downstream_stocks) if self.downstream_stocks else [],
            'is_leader': self.is_leader,
            'industry': self.industry,
        }

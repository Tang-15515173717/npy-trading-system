"""
支付相关数据模型
"""
from utils.database import db
from datetime import datetime


class PaymentOrder(db.Model):
    """支付订单表"""
    __tablename__ = 'payment_orders'

    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(64), unique=True, nullable=False, index=True, comment='商户订单号')
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True, comment='租户ID')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='用户ID')

    # 订单信息
    plan_type = db.Column(db.String(20), nullable=False, comment='套餐类型')
    amount = db.Column(db.Integer, nullable=False, comment='金额（分）')
    body = db.Column(db.String(200), nullable=False, comment='商品描述')

    # 支付信息
    pay_type = db.Column(db.String(20), nullable=False, comment='支付类型: alipay/wechat')
    pay_url = db.Column(db.Text, comment='支付链接')
    transaction_id = db.Column(db.String(64), comment='第三方订单号')

    # 订单状态: pending/paid/failed/closed/refunded
    status = db.Column(db.String(20), default='pending', nullable=False, index=True, comment='订单状态')

    # 时间字段
    paid_at = db.Column(db.DateTime, comment='支付时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关联
    tenant = db.relationship('Tenant', backref='payment_orders')
    user = db.relationship('User', backref='payment_orders')

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'order_no': self.order_no,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'plan_type': self.plan_type,
            'amount': self.amount,
            'amount_yuan': round(self.amount / 100, 2),  # 转换为元
            'body': self.body,
            'pay_type': self.pay_type,
            'pay_url': self.pay_url,
            'transaction_id': self.transaction_id,
            'status': self.status,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class PaymentRecord(db.Model):
    """支付记录表 - 记录所有支付流水"""
    __tablename__ = 'payment_records'

    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(64), nullable=False, index=True, comment='商户订单号')
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True, comment='租户ID')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='用户ID')

    # 支付信息
    pay_type = db.Column(db.String(20), nullable=False, comment='支付类型')
    transaction_id = db.Column(db.String(64), nullable=False, comment='第三方订单号')
    amount = db.Column(db.Integer, nullable=False, comment='金额（分）')

    # 套餐信息
    plan_type = db.Column(db.String(20), nullable=False, comment='购买的套餐类型')

    # 支付状态: success/failed/refunded
    status = db.Column(db.String(20), default='success', nullable=False, comment='状态')

    # 回调数据
    notify_data = db.Column(db.Text, comment='回调原始数据')

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, comment='创建时间')

    # 关联
    tenant = db.relationship('Tenant', backref='payment_records')
    user = db.relationship('User', backref='payment_records')

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'order_no': self.order_no,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'pay_type': self.pay_type,
            'transaction_id': self.transaction_id,
            'amount': self.amount,
            'amount_yuan': round(self.amount / 100, 2),
            'plan_type': self.plan_type,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

"""
用户与租户模型 - SaaS量化交易平台
实现多租户用户认证体系
"""
from datetime import datetime
from utils.database import db
from werkzeug.security import generate_password_hash, check_password_hash


class Tenant(db.Model):
    """租户模型 - SaaS多租户"""

    __tablename__ = "tenants"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True, comment="租户名称")
    plan = db.Column(db.String(20), default="basic", comment="套餐: basic/pro/enterprise")
    max_strategies = db.Column(db.Integer, default=5, comment="最大策略数")
    max_backtests_per_day = db.Column(db.Integer, default=10, comment="每日最大回测次数")
    max_observers = db.Column(db.Integer, default=2, comment="最大观测数")
    is_active = db.Column(db.Boolean, default=True, comment="是否激活")
    
    # 🆕 试用和过期管理
    is_trial = db.Column(db.Boolean, default=True, comment="是否试用期")
    trial_end_date = db.Column(db.DateTime, nullable=True, comment="试用期结束日期")
    expire_date = db.Column(db.DateTime, nullable=True, comment="套餐过期日期")
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关联用户
    users = db.relationship("User", backref="tenant", lazy="dynamic")
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if not self.expire_date:
            return False
        return datetime.utcnow() > self.expire_date
    
    def is_trial_expired(self) -> bool:
        """检查试用期是否过期"""
        if not self.is_trial or not self.trial_end_date:
            return False
        return datetime.utcnow() > self.trial_end_date
    
    def get_status(self) -> str:
        """获取账号状态"""
        if not self.is_active:
            return "disabled"
        if self.is_trial:
            if self.is_trial_expired():
                return "trial_expired"
            return "trial"
        if self.is_expired():
            return "expired"
        return "active"

    def to_dict(self) -> dict:
        """转为字典"""
        status = self.get_status()
        return {
            "id": self.id,
            "name": self.name,
            "plan": self.plan,
            "max_strategies": self.max_strategies,
            "max_backtests_per_day": self.max_backtests_per_day,
            "is_active": self.is_active,
            "is_trial": self.is_trial,
            "trial_end_date": self.trial_end_date.isoformat() if self.trial_end_date else None,
            "expire_date": self.expire_date.isoformat() if self.expire_date else None,
            "status": status,
            "is_expired": self.is_expired(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Tenant {self.name}>"


class User(db.Model):
    """用户模型"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True, comment="邮箱")
    password_hash = db.Column(db.String(256), nullable=False, comment="密码哈希")
    username = db.Column(db.String(80), nullable=True, comment="用户名")
    
    # 租户关联
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True, comment="租户ID")
    
    # 角色与权限
    role = db.Column(db.String(20), default="member", comment="角色: admin/member/viewer")
    is_active = db.Column(db.Boolean, default=True, comment="是否激活")
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    last_login_at = db.Column(db.DateTime, nullable=True, comment="最后登录时间")

    def set_password(self, password: str) -> None:
        """设置密码（自动哈希）"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        """转为字典（不包含敏感信息）"""
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "tenant_id": self.tenant_id,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.email}>"

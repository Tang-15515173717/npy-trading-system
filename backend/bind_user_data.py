#!/usr/bin/env python3
"""
绑定现有数据到用户账号
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, '/Users/mac/IdeaProjects/vnpy/backend')

# 创建Flask app
from flask import Flask
from utils.database import init_db

PROJECT_ROOT = Path('/Users/mac/IdeaProjects/vnpy')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{PROJECT_ROOT}/database/stock_quant.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
init_db(app)

from utils.database import db
from models.user import User
from models.backtest import BacktestTask
from models.daily_observer import DailyObserverStrategy

def bind_data_to_user(email: str):
    """绑定所有数据到指定用户"""
    with app.app_context():
        # 查询用户
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f'❌ 用户 {email} 不存在')
            return
        
        print(f'✅ 找到用户: {user.email}')
        print(f'   租户ID: {user.tenant_id}')
        print(f'   用户ID: {user.id}')
        print()
        
        # 更新所有没有租户ID的回测记录
        backtest_null = BacktestTask.query.filter_by(tenant_id=None).count()
        print(f'📊 发现 {backtest_null} 条未绑定的回测记录')
        
        if backtest_null > 0:
            BacktestTask.query.filter_by(tenant_id=None).update({'tenant_id': user.tenant_id})
            print(f'✅ 已绑定 {backtest_null} 条回测记录到租户ID: {user.tenant_id}')
        
        # 更新所有没有租户ID的观测策略
        observer_null = DailyObserverStrategy.query.filter_by(tenant_id=None).count()
        print(f'📊 发现 {observer_null} 条未绑定的观测策略')
        
        if observer_null > 0:
            DailyObserverStrategy.query.filter_by(tenant_id=None).update({'tenant_id': user.tenant_id})
            print(f'✅ 已绑定 {observer_null} 条观测策略到租户ID: {user.tenant_id}')
        
        db.session.commit()
        print()
        print('🎉 绑定完成！')
        
        # 验证结果
        print()
        print('📈 验证结果：')
        total_backtest = BacktestTask.query.filter_by(tenant_id=user.tenant_id).count()
        total_observer = DailyObserverStrategy.query.filter_by(tenant_id=user.tenant_id).count()
        print(f'   回测记录总数: {total_backtest}')
        print(f'   观测策略总数: {total_observer}')

if __name__ == '__main__':
    email = 'demotest@example.com'
    bind_data_to_user(email)

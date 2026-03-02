#!/usr/bin/env python3
"""
数据库迁移脚本 - 添加试用期和过期字段
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, '/Users/mac/IdeaProjects/vnpy/backend')

from flask import Flask
from utils.database import init_db, db
from datetime import datetime, timedelta

PROJECT_ROOT = Path('/Users/mac/IdeaProjects/vnpy')

# 创建Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{PROJECT_ROOT}/database/stock_quant.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
init_db(app)


def migrate_database():
    """迁移数据库"""
    with app.app_context():
        print("\n" + "🔄 数据库迁移开始".center(60, "="))
        print()
        
        # 添加新字段
        try:
            # 检查表结构
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('tenants')]
            
            print(f"📋 当前字段: {columns}")
            print()
            
            # 添加新字段（如果不存在）
            if 'is_trial' not in columns:
                print("➕ 添加 is_trial 字段...")
                db.session.execute(text('ALTER TABLE tenants ADD COLUMN is_trial BOOLEAN DEFAULT 1'))
                
            if 'trial_end_date' not in columns:
                print("➕ 添加 trial_end_date 字段...")
                db.session.execute(text('ALTER TABLE tenants ADD COLUMN trial_end_date DATETIME'))
                
            if 'expire_date' not in columns:
                print("➕ 添加 expire_date 字段...")
                db.session.execute(text('ALTER TABLE tenants ADD COLUMN expire_date DATETIME'))
            
            db.session.commit()
            print("✅ 字段添加完成")
            print()
            
        except Exception as e:
            print(f"⚠️  字段添加警告: {e}")
            print("(可能字段已存在，继续执行...)")
            print()
        
        # 更新现有数据
        from models.user import Tenant
        
        print("📊 更新现有租户数据...")
        tenants = Tenant.query.all()
        
        for tenant in tenants:
            print(f"\n处理租户: {tenant.name} (ID: {tenant.id})")
            
            # 更新套餐（取消免费版）
            if tenant.plan == 'free':
                tenant.plan = 'basic'
                print(f"  ✅ 套餐: free -> basic")
            
            # 设置试用期信息（如果是新租户或旧的free用户）
            if not tenant.trial_end_date:
                # 判断是否是新用户（7天内创建）
                if tenant.created_at and (datetime.utcnow() - tenant.created_at).days <= 7:
                    # 新用户，设置试用期
                    tenant.is_trial = True
                    tenant.trial_end_date = tenant.created_at + timedelta(days=7)
                    print(f"  ✅ 设置试用期: 7天（至 {tenant.trial_end_date.strftime('%Y-%m-%d')}）")
                else:
                    # 老用户，直接给正式版（已经使用很久了）
                    tenant.is_trial = False
                    tenant.trial_end_date = None
                    tenant.expire_date = datetime.utcnow() + timedelta(days=365)  # 赠送1年
                    print(f"  ✅ 老用户赠送1年正式版")
            
            # 更新限制
            if tenant.plan == 'basic':
                tenant.max_strategies = 5
                tenant.max_backtests_per_day = 10
            elif tenant.plan == 'pro':
                tenant.max_strategies = 20
                tenant.max_backtests_per_day = 50
            elif tenant.plan == 'enterprise':
                tenant.max_strategies = 100
                tenant.max_backtests_per_day = 200
        
        db.session.commit()
        print()
        print("=" * 60)
        print("✅ 数据库迁移完成！")
        print()
        
        # 显示统计
        total = Tenant.query.count()
        trial = Tenant.query.filter_by(is_trial=True).count()
        basic = Tenant.query.filter_by(plan='basic').count()
        pro = Tenant.query.filter_by(plan='pro').count()
        enterprise = Tenant.query.filter_by(plan='enterprise').count()
        
        print("📊 统计信息:")
        print(f"  总租户数: {total}")
        print(f"  试用期用户: {trial}")
        print(f"  基础版: {basic}")
        print(f"  专业版: {pro}")
        print(f"  企业版: {enterprise}")


if __name__ == '__main__':
    migrate_database()

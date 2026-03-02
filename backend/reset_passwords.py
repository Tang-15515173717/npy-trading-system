#!/usr/bin/env python3
"""
重置用户密码 - 适配JWT系统
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, '/Users/mac/IdeaProjects/vnpy/backend')

from flask import Flask
from utils.database import init_db, db
from models.user import User

PROJECT_ROOT = Path('/Users/mac/IdeaProjects/vnpy')

# 创建Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{PROJECT_ROOT}/database/stock_quant.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
init_db(app)


def reset_password(email: str, new_password: str):
    """重置用户密码"""
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"❌ 用户 {email} 不存在")
            return
        
        print(f"✅ 找到用户: {user.email} (ID: {user.id})")
        print(f"   用户名: {user.username}")
        print(f"   角色: {user.role}")
        
        # 重置密码
        user.set_password(new_password)
        db.session.commit()
        
        print(f"✅ 密码已重置为: {new_password}")
        print()
        
        # 验证新密码
        if user.check_password(new_password):
            print("✅ 密码验证成功！")
        else:
            print("❌ 密码验证失败！")


if __name__ == '__main__':
    print("\n" + "🔐 重置用户密码".center(60, "="))
    print()
    
    # 重置所有测试账号的密码
    accounts = [
        ("demotest@example.com", "demo123"),
        ("demo@test.com", "demo123"),
        ("test_jwt@example.com", "password123")
    ]
    
    for email, password in accounts:
        reset_password(email, password)
        print()
    
    print("=" * 60)
    print("✅ 所有账号密码重置完成！")
    print()
    print("📝 账号列表：")
    print("  1. demotest@example.com / demo123 (Pro版管理员)")
    print("  2. demo@test.com / demo123 (免费版)")
    print("  3. test_jwt@example.com / password123 (免费版)")

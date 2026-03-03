"""
初始化支付模块数据库表
运行此脚本来创建支付相关的数据库表
"""
from utils.database import db
from models.payment import PaymentOrder, PaymentRecord
from flask import Flask
from config import config


def init_payment_tables():
    """初始化支付表"""
    app = Flask(__name__)
    app.config.from_object(config['default'])
    db.init_app(app)

    with app.app_context():
        print("开始创建支付表...")

        # 创建表
        db.create_all()

        # 检查表是否创建成功
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()

        if 'payment_orders' in tables and 'payment_records' in tables:
            print("✓ 支付表创建成功!")
            print("  - payment_orders (支付订单表)")
            print("  - payment_records (支付记录表)")
        else:
            print("✗ 支付表创建失败，请检查数据库连接")
            return False

        return True


if __name__ == '__main__':
    init_payment_tables()

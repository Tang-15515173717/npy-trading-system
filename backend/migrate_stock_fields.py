"""
数据库迁移：添加股票分类字段
- stock_type: 股票类型（key=重点股票, normal=普通股票）
- has_full_data: 是否有完整历史数据（用于回测筛选）
"""
import sys
sys.path.insert(0, '/Users/mac/IdeaProjects/vnpy/backend')

from app import create_app
from utils.database import db
from models.stock import Stock
from sqlalchemy import text

def migrate_add_stock_fields():
    """添加新字段到stocks表"""
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*80)
        print("📊 数据库迁移：添加股票分类字段")
        print("="*80)
        
        try:
            # 检查字段是否已存在
            result = db.session.execute(text("PRAGMA table_info(stocks)"))
            columns = [row[1] for row in result]
            
            # 添加 stock_type 字段
            if 'stock_type' not in columns:
                print("\n1️⃣ 添加 stock_type 字段...")
                db.session.execute(text(
                    "ALTER TABLE stocks ADD COLUMN stock_type VARCHAR(10) DEFAULT 'normal'"
                ))
                db.session.commit()
                print("   ✅ stock_type 字段添加成功")
            else:
                print("\n1️⃣ stock_type 字段已存在")
            
            # 添加 has_full_data 字段
            if 'has_full_data' not in columns:
                print("\n2️⃣ 添加 has_full_data 字段...")
                db.session.execute(text(
                    "ALTER TABLE stocks ADD COLUMN has_full_data BOOLEAN DEFAULT 0"
                ))
                db.session.commit()
                print("   ✅ has_full_data 字段添加成功")
            else:
                print("\n2️⃣ has_full_data 字段已存在")
            
            print("\n" + "="*80)
            print("✅ 数据库迁移完成！")
            print("="*80)
            
        except Exception as e:
            print(f"❌ 迁移失败：{e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    migrate_add_stock_fields()

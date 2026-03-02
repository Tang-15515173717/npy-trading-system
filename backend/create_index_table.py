"""
创建指数数据表 - 一键脚本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from utils.database import db
from models.index_data import IndexDaily

def create_index_table():
    """创建指数数据表"""
    print("\n" + "="*80)
    print("📊 创建指数数据表")
    print("="*80 + "\n")
    
    app = create_app()
    
    with app.app_context():
        try:
            # 创建表
            db.create_all()
            
            # 检查表是否存在
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'index_daily' in tables:
                print("✅ index_daily 表创建成功")
                
                # 显示表结构
                columns = inspector.get_columns('index_daily')
                print("\n表结构：")
                for col in columns:
                    print(f"  - {col['name']:15} {col['type']}")
                
                # 显示索引
                indexes = inspector.get_indexes('index_daily')
                if indexes:
                    print("\n索引：")
                    for idx in indexes:
                        print(f"  - {idx['name']}: {idx['column_names']}")
                
                print("\n" + "="*80)
                print("🎉 数据表创建完成！")
                print("="*80 + "\n")
                return True
            else:
                print("❌ 表创建失败")
                return False
                
        except Exception as e:
            print(f"❌ 创建失败：{e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = create_index_table()
    sys.exit(0 if success else 1)

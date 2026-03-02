"""
在 Flask 应用启动时初始化指数定时任务

在 backend/app.py 的 create_app() 函数中添加：
"""

from services.index_scheduler import index_scheduler

def create_app():
    app = Flask(__name__)
    
    # ... 其他初始化代码 ...
    
    # 启动指数数据定时更新服务
    with app.app_context():
        index_scheduler.start()
    
    return app

# 或者在 if __name__ == "__main__" 中启动：
if __name__ == "__main__":
    app = create_app()
    
    # 启动指数数据定时任务
    from services.index_scheduler import index_scheduler
    index_scheduler.start()
    
    app.run(host="0.0.0.0", port=5001)

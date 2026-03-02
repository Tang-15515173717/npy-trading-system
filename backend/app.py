"""
Flask 主应用 - StockQuant Pro
Phase 0：基础框架、健康检查、Hello API。
v1.2：集成指数数据定时更新服务
v2.0：集成量化因子模块
"""
from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager
import os

# 导入TuShare Token
import os
import sys
# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
print(f"项目根目录: {project_root}")

try:
    # 延迟导入，避免Application.py中的talib等依赖问题
    import importlib.util
    spec = importlib.util.spec_from_file_location("Application", f"{project_root}/Application.py")
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules["Application"] = module
        spec.loader.exec_module(module)
        TUSHARE_TOKEN = module.TUSHARE_TOKEN
        os.environ['TUSHARE_TOKEN'] = TUSHARE_TOKEN
        print(f"✓ TuShare Token已加载")
except Exception as e:
    print(f"⚠️  无法加载TuShare Token: {e}")
    # 直接硬编码Token
    os.environ['TUSHARE_TOKEN'] = "c581961ccacd6c2f01c196364402ef122a6a51335354bb01ab24c7a1"
    print(f"使用默认Token")

from config import config
from utils.database import init_db
from api.data_api import data_bp
from api.strategy_api import strategy_bp
from api.backtest_api import backtest_bp
from api.subscription_api import subscription_bp
from api.observer_api import observer_bp
from api.trade_api import trade_bp
from api.factor_api import factor_bp  # v2.0 新增
from api.scoring_api import scoring_bp  # v2.3 新增
from api.signal_strategy_api import signal_strategy_bp  # v2.3 新增
from api.daily_observer_api import daily_observer_bp  # v2.6 每日模拟观测
from api.auth_api import auth_bp  # SaaS认证


def create_app(config_name: str = "default") -> Flask:
    """创建 Flask 应用"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # 配置Flask-Login
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.session_protection = 'basic'

    # 用户加载函数
    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))

    CORS(app, origins=["*"])  # 允许所有来源访问（局域网访问需要）

    init_db(app)

    app.register_blueprint(data_bp)
    app.register_blueprint(strategy_bp)
    app.register_blueprint(backtest_bp)
    app.register_blueprint(subscription_bp)
    app.register_blueprint(observer_bp)
    app.register_blueprint(trade_bp)
    app.register_blueprint(factor_bp)  # v2.0 因子模块
    app.register_blueprint(scoring_bp)  # v2.3 打分配置
    app.register_blueprint(signal_strategy_bp)  # v2.3 信号策略
    app.register_blueprint(daily_observer_bp)  # v2.6 每日模拟观测
    app.register_blueprint(auth_bp)  # SaaS认证

    @app.route("/health")
    def health():
        return {"status": "ok"}
    
    # 启动指数数据定时任务（在应用上下文中）
    with app.app_context():
        try:
            from services.index_scheduler import index_scheduler
            index_scheduler.start()
        except Exception as e:
            print(f"⚠️  指数定时任务启动失败：{e}")

    return app


if __name__ == "__main__":
    app = create_app()
    # 生产环境配置：禁用debug和auto-reload，避免异步任务丢失
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)

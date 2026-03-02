"""
配置文件 - StockQuant Pro
项目根目录为 vnpy/，数据库与 data 目录在项目根下。
"""
import os
from pathlib import Path

# 项目根目录（vnpy/），backend/config/settings.py -> parent.parent = backend, parent.parent.parent = vnpy
_BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = _BACKEND_DIR.parent


class Config:
    """基础配置"""

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = True

    # 数据库（SQLite，文件在项目根 database/ 下）
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{PROJECT_ROOT}/database/stock_quant.db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # TuShare
    TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "c581961ccacd6c2f01c196364402ef122a6a51335354bb01ab24c7a1")

    # DeepSeek LLM（用于回测智能总结）
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-303da06b61784127bc15c102629f6ef4")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # 数据与日志路径（项目根下）
    DATA_DIR = PROJECT_ROOT / "data"
    STOCKS_DATA_DIR = DATA_DIR / "stocks"
    LOG_DIR = PROJECT_ROOT / "logs"

    LOG_LEVEL = "INFO"

    # CORS
    CORS_ORIGINS = ["http://localhost:8080", "http://127.0.0.1:8080"]

    # 分页
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 200


class DevelopmentConfig(Config):
    """开发环境"""
    DEBUG = True
    SQLALCHEMY_ECHO = False  # 设为 True 可打印 SQL


class ProductionConfig(Config):
    """生产环境"""
    DEBUG = False
    # SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:pass@localhost/dbname"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

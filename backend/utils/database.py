"""
数据库工具 - StockQuant Pro
Flask-SQLAlchemy 初始化、建表、目录创建。
"""
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from pathlib import Path
from sqlalchemy import text

db = SQLAlchemy()


def init_db(app: Flask) -> None:
    """
    初始化数据库：绑定 app、创建 database/data 目录、建表。

    Args:
        app: Flask 应用实例
    """
    db.init_app(app)
    with app.app_context():
        uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
        if uri.startswith("sqlite:///"):
            db_path = Path(uri.replace("sqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        data_dir = app.config.get("DATA_DIR")
        if data_dir is not None:
            Path(data_dir).mkdir(parents=True, exist_ok=True)
        stocks_dir = app.config.get("STOCKS_DATA_DIR")
        if stocks_dir is not None:
            Path(stocks_dir).mkdir(parents=True, exist_ok=True)
        from models import stock, bar_data, strategy, backtest, simulation  # noqa: F401
        from models import factor_combo, selection_result  # noqa: F401  v2.1 双驱动
        db.create_all()
        # v2.1 双驱动：为已有表添加新列（SQLite 不自动 alter）
        if uri.startswith("sqlite:///"):
            try:
                with db.engine.connect() as conn:
                    for stmt in [
                        # v2.1 双驱动字段
                        "ALTER TABLE backtest_tasks ADD COLUMN factor_combo_id INTEGER",
                        "ALTER TABLE backtest_trades ADD COLUMN factor_combo_id INTEGER",
                        "ALTER TABLE backtest_trades ADD COLUMN factor_combo_name VARCHAR(100)",
                        "ALTER TABLE backtest_trades ADD COLUMN strategy_id INTEGER",
                        "ALTER TABLE backtest_trades ADD COLUMN strategy_name VARCHAR(100)",
                        "ALTER TABLE backtest_trades ADD COLUMN signal_reason VARCHAR(50)",
                        "ALTER TABLE backtest_trades ADD COLUMN composite_score REAL",
                        "ALTER TABLE backtest_trades ADD COLUMN rank INTEGER",
                        # v2.3 多因子打分回测系统字段
                        "ALTER TABLE backtest_tasks ADD COLUMN scoring_config_id INTEGER",
                        "ALTER TABLE backtest_tasks ADD COLUMN signal_strategy_id INTEGER",
                    ]:
                        try:
                            conn.execute(text(stmt))
                            conn.commit()
                        except Exception:
                            conn.rollback()
            except Exception:
                pass
"""
策略服务 - StockQuant Pro
策略 CRUD、列表筛选、模板管理。
"""
from typing import List, Dict, Optional
from datetime import datetime
from models.strategy import Strategy
from utils.database import db
import json


class StrategyService:
    """策略服务类"""

    def get_strategy_list(
        self,
        type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """
        获取策略列表（支持筛选）。

        Args:
            type: 策略类型（select/trade/combo）
            status: 状态（draft/testing/verified/running）

        Returns:
            策略字典列表
        """
        query = Strategy.query
        if type:
            query = query.filter(Strategy.type == type)
        if status:
            query = query.filter(Strategy.status == status)
        
        strategies = query.order_by(Strategy.updated_at.desc()).all()
        return [s.to_dict() for s in strategies]

    def get_strategy(self, strategy_id: int) -> Optional[Dict]:
        """
        获取策略详情。

        Args:
            strategy_id: 策略ID

        Returns:
            策略字典，不存在返回 None
        """
        strategy = Strategy.query.get(strategy_id)
        if strategy is None:
            return None
        result = strategy.to_dict()
        # 可以在这里添加 backtest_history 等扩展信息
        return result

    def create_strategy(
        self,
        name: str,
        type: str,
        description: Optional[str] = None,
        params: Optional[Dict] = None,
        code: Optional[str] = None,
    ) -> Dict:
        """
        创建策略。

        Args:
            name: 策略名称
            type: 策略类型
            description: 描述
            params: 参数字典
            code: 策略代码

        Returns:
            创建的策略字典
        """
        strategy = Strategy(\
            tenant_id=tenant_id,
            name=name,
            type=type,
            description=description,
            params=json.dumps(params, ensure_ascii=False) if params else None,
            code=code,
            status="draft",
        )
        db.session.add(strategy)
        db.session.commit()
        return strategy.to_dict()

    def update_strategy(
        self,
        strategy_id: int,
        name: Optional[str] = None,
        type: Optional[str] = None,
        status: Optional[str] = None,
        description: Optional[str] = None,
        params: Optional[Dict] = None,
        code: Optional[str] = None,
        backtest_result: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        更新策略。

        Args:
            strategy_id: 策略ID
            其他参数：要更新的字段

        Returns:
            更新后的策略字典，不存在返回 None
        """
        strategy = Strategy.query.get(strategy_id)
        if strategy is None:
            return None

        if name is not None:
            strategy.name = name
        if type is not None:
            strategy.type = type
        if status is not None:
            strategy.status = status
        if description is not None:
            strategy.description = description
        if params is not None:
            strategy.params = json.dumps(params, ensure_ascii=False)
        if code is not None:
            strategy.code = code
        if backtest_result is not None:
            strategy.backtest_result = json.dumps(backtest_result, ensure_ascii=False)

        strategy.updated_at = datetime.utcnow()
        db.session.commit()
        return strategy.to_dict()

    def delete_strategy(self, strategy_id: int) -> bool:
        """
        删除策略。

        Args:
            strategy_id: 策略ID

        Returns:
            成功返回 True，不存在返回 False
        """
        strategy = Strategy.query.get(strategy_id)
        if strategy is None:
            return False
        db.session.delete(strategy)
        db.session.commit()
        return True

    def get_strategy_templates(self) -> List[Dict]:
        """
        获取内置策略模板。

        Returns:
            模板列表
        """
        templates = [
            {
                "id": "double_ma",
                "name": "双均线策略",
                "type": "trade",
                "description": "快速MA上穿慢速MA买入，下穿卖出",
                "params": {
                    "fast_ma": 5,
                    "slow_ma": 20,
                    "stop_loss": 0.05,
                    "take_profit": 0.10,
                },
                "code": """# 双均线策略示例
class DoubleMaStrategy(CtaTemplate):
    fast_ma = 5
    slow_ma = 20
    
    def on_bar(self, bar):
        if self.fast_ma_value > self.slow_ma_value:
            self.buy(bar.close, 100)
        elif self.fast_ma_value < self.slow_ma_value:
            self.sell(bar.close, 100)
""",
            },
            {
                "id": "macd",
                "name": "MACD金叉策略",
                "type": "trade",
                "description": "MACD金叉买入，死叉卖出",
                "params": {
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                },
                "code": """# MACD策略示例
class MacdStrategy(CtaTemplate):
    def on_bar(self, bar):
        if self.macd > self.signal and self.macd_prev < self.signal_prev:
            self.buy(bar.close, 100)
        elif self.macd < self.signal and self.macd_prev > self.signal_prev:
            self.sell(bar.close, 100)
""",
            },
            {
                "id": "bollinger",
                "name": "布林带突破",
                "type": "trade",
                "description": "价格突破上轨买入，跌破下轨卖出",
                "params": {
                    "period": 20,
                    "std_dev": 2,
                },
                "code": """# 布林带策略示例
class BollingerStrategy(CtaTemplate):
    def on_bar(self, bar):
        if bar.close > self.upper_band:
            self.buy(bar.close, 100)
        elif bar.close < self.lower_band:
            self.sell(bar.close, 100)
""",
            },
            {
                "id": "grid",
                "name": "网格交易",
                "type": "trade",
                "description": "在固定价格区间内进行高抛低吸",
                "params": {
                    "grid_min": 10.0,
                    "grid_max": 15.0,
                    "grid_step": 0.5,
                },
                "code": """# 网格交易策略示例
class GridStrategy(CtaTemplate):
    def on_bar(self, bar):
        # 价格下跌到网格线时买入
        # 价格上涨到网格线时卖出
        pass
""",
            },
            {
                "id": "momentum",
                "name": "动量策略",
                "type": "select",
                "description": "选择近期涨幅最大的股票",
                "params": {
                    "lookback_period": 20,
                    "top_n": 10,
                },
                "code": """# 动量选股策略示例
def select_stocks(stocks, lookback=20, top_n=10):
    # 计算每只股票的涨幅
    # 选择涨幅最大的 top_n 只
    return selected_stocks
""",
            },
        ]
        return templates

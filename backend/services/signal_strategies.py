"""
买卖信号策略 - StockQuant Pro
支持多种买入卖出策略和仓位管理方法
"""
from typing import Dict, List, Tuple
from abc import ABC, abstractmethod


# ============================================================================
# 买入策略
# ============================================================================

class BuySignalStrategy(ABC):
    """买入策略基类"""

    @abstractmethod
    def generate_signals(
        self,
        stocks_with_scores: List[Dict],
        current_positions: set,
        params: Dict
    ) -> List[Dict]:
        """
        生成买入信号

        Args:
            stocks_with_scores: [{"ts_code": "...", "score": 0.85, "rank": 1, ...}, ...]
            current_positions: 当前持仓股票代码集合
            params: 策略参数

        Returns:
            买入候选列表（已过滤已持仓）
        """
        pass


class BuySignalTopN(BuySignalStrategy):
    """买入策略1: 综合分Top N"""

    def generate_signals(
        self,
        stocks_with_scores: List[Dict],
        current_positions: set,
        params: Dict
    ) -> List[Dict]:
        """
        买入信号：综合分前N名且未持仓

        Args:
            params: {"top_n": 20}

        Returns:
            买入候选列表
        """
        top_n = params.get('top_n', 20)

        buy_list = []
        for stock in stocks_with_scores[:top_n]:
            if stock['ts_code'] not in current_positions:
                buy_list.append(stock)

        return buy_list


class BuySignalThreshold(BuySignalStrategy):
    """买入策略2: 综合分阈值 + 排名过滤"""

    def generate_signals(
        self,
        stocks_with_scores: List[Dict],
        current_positions: set,
        params: Dict
    ) -> List[Dict]:
        """
        买入信号：综合分≥阈值 且 排名≤max_rank

        Args:
            params: {"min_score": 80, "max_rank": 30}

        Returns:
            买入候选列表
        """
        min_score = params.get('min_score', 80.0)
        max_rank = params.get('max_rank', 30)

        buy_list = []
        for stock in stocks_with_scores:
            if (stock['ts_code'] not in current_positions and
                stock['composite_score'] >= min_score and
                stock['rank'] <= max_rank):
                buy_list.append(stock)

        return buy_list


class BuySignalMultiFactorResonance(BuySignalStrategy):
    """买入策略3: 多因子共振"""

    def generate_signals(
        self,
        stocks_with_scores: List[Dict],
        current_positions: set,
        params: Dict
    ) -> List[Dict]:
        """
        买入信号：多个因子同时满足条件

        Args:
            params: {
                "factor_rules": {
                    "return_20d": {"min": 0.1, "direction": "long"},
                    "pe_ratio": {"min": 30, "direction": "short"}
                }
            }

        Returns:
            买入候选列表
        """
        factor_rules = params.get('factor_rules', {})

        if not factor_rules:
            return []

        buy_list = []
        for stock in stocks_with_scores:
            if stock['ts_code'] in current_positions:
                continue

            pass_all = True
            factor_scores = stock.get('factor_scores', {})

            for factor_code, rule in factor_rules.items():
                score = factor_scores.get(factor_code, 0)
                direction = rule.get('direction', 'long')
                min_val = rule.get('min', 0)

                if direction == 'long':
                    # 正向因子：得分必须 >= min_val
                    if score < min_val:
                        pass_all = False
                        break
                else:  # short
                    # 负向因子：得分必须 <= min_val
                    if score > min_val:
                        pass_all = False
                        break

            if pass_all:
                buy_list.append(stock)

        return buy_list


class BuySignalTechnicalBreakout(BuySignalStrategy):
    """买入策略4: 技术指标突破（预留，需要K线数据）"""

    def generate_signals(
        self,
        stocks_with_scores: List[Dict],
        current_positions: set,
        params: Dict
    ) -> List[Dict]:
        """
        买入信号：技术指标突破

        Args:
            params: {"breakout_type": "golden_cross", "ma_short": 5, "ma_long": 20}

        Returns:
            买入候选列表

        Note:
            此策略需要K线数据，暂时返回空列表
            实际实现需要传入bars_dict参数
        """
        # TODO: 实现技术指标突破策略
        # 需要K线数据支持，这里先返回空列表
        return []


# ============================================================================
# 卖出策略
# ============================================================================

class SellSignalStrategy(ABC):
    """卖出策略基类"""

    @abstractmethod
    def should_sell(
        self,
        ts_code: str,
        holding_info: Dict,
        current_info: Dict,
        params: Dict
    ) -> Tuple[bool, str]:
        """
        判断是否应该卖出

        Args:
            ts_code: 股票代码
            holding_info: 持仓信息
                {
                    'volume': 持仓数量,
                    'cost_price': 成本价,
                    'entry_factor_scores': 买入时的因子得分,
                    'entry_date': 买入日期
                }
            current_info: 当前信息
                {
                    'current_price': 当前价格,
                    'composite_score': 当前综合分,
                    'rank': 当前排名,
                    'factor_scores': 当前因子得分
                }
            params: 策略参数

        Returns:
            (should_sell, reason): (True, "止盈") or (False, "")
        """
        pass


class SellSignalProfitLoss(SellSignalStrategy):
    """卖出策略1: 止盈止损"""

    def should_sell(
        self,
        ts_code: str,
        holding_info: Dict,
        current_info: Dict,
        params: Dict
    ) -> Tuple[bool, str]:
        """
        卖出信号：止盈或止损

        Args:
            params: {"take_profit_ratio": 0.15, "stop_loss_ratio": -0.08}

        Returns:
            (True, "止盈15%") or (True, "止损-8%") or (False, "")
        """
        current_price = current_info.get('current_price', 0)
        cost_price = holding_info.get('cost_price', 0)

        if current_price == 0 or cost_price == 0:
            return False, ""

        profit_ratio = (current_price - cost_price) / cost_price

        take_profit_ratio = params.get('take_profit_ratio', 0.15)
        stop_loss_ratio = params.get('stop_loss_ratio', -0.08)

        if profit_ratio >= take_profit_ratio:
            return True, f"止盈{profit_ratio*100:.1f}%"

        if profit_ratio <= stop_loss_ratio:
            return True, f"止损{profit_ratio*100:.1f}%"

        return False, ""


class SellSignalScoreDeterioration(SellSignalStrategy):
    """卖出策略2: 打分掉出"""

    def should_sell(
        self,
        ts_code: str,
        holding_info: Dict,
        current_info: Dict,
        params: Dict
    ) -> Tuple[bool, str]:
        """
        卖出信号：排名掉出或综合分下降

        Args:
            params: {"sell_rank_out": 30, "sell_score_below": 60}

        Returns:
            (True, "打分掉出前30") or (True, "综合分低于60") or (False, "")
        """
        current_rank = current_info.get('rank', 99999)
        current_score = current_info.get('composite_score', 0)

        sell_rank_out = params.get('sell_rank_out', 30)
        sell_score_below = params.get('sell_score_below', 60.0)

        if current_rank > sell_rank_out:
            return True, f"打分掉出前{sell_rank_out}"

        if current_score < sell_score_below:
            return True, f"综合分低于{sell_score_below}"

        return False, ""


class SellSignalTechnicalDeathCross(SellSignalStrategy):
    """卖出策略3: 技术指标死叉（预留）"""

    def should_sell(
        self,
        ts_code: str,
        holding_info: Dict,
        current_info: Dict,
        params: Dict
    ) -> Tuple[bool, str]:
        """
        卖出信号：技术指标死叉

        Args:
            params: {"signal_type": "death_cross"}

        Returns:
            (True, "死叉") or (False, "")

        Note:
            此策略需要K线数据，暂时返回False
        """
        # TODO: 实现技术指标死叉策略
        return False, ""


class SellSignalFactorDeterioration(SellSignalStrategy):
    """卖出策略4: 因子恶化"""

    def should_sell(
        self,
        ts_code: str,
        holding_info: Dict,
        current_info: Dict,
        params: Dict
    ) -> Tuple[bool, str]:
        """
        卖出信号：关键因子恶化

        Args:
            params: {
                "deterioration_rules": {
                    "return_20d": -0.05,
                    "pe_ratio": 0.1
                }
            }

        Returns:
            (True, "return_20d恶化") or (False, "")
        """
        deterioration_rules = params.get('deterioration_rules', {})

        if not deterioration_rules:
            return False, ""

        current_factor_scores = current_info.get('factor_scores', {})
        entry_factor_scores = holding_info.get('entry_factor_scores', {})

        for factor_code, threshold in deterioration_rules.items():
            current_score = current_factor_scores.get(factor_code, 0)
            entry_score = entry_factor_scores.get(factor_code, 0)
            change = current_score - entry_score

            # 注意：threshold通常是负数，表示恶化阈值
            if change < threshold:
                return True, f"{factor_code}恶化"

        return False, ""


# ============================================================================
# 仓位管理
# ============================================================================

class PositionManager:
    """仓位管理器"""

    @staticmethod
    def equal_weight(
        cash: float,
        buy_list: List[Dict],
        max_positions: int
    ) -> List[Dict]:
        """
        等权分配：每只股票平均分配资金

        Args:
            cash: 可用资金
            buy_list: 买入列表（含price字段）
            max_positions: 最大持仓数

        Returns:
            交易订单列表 [{"ts_code": "...", "volume": 100, "price": 10.5}, ...]
        """
        if not buy_list or cash <= 0:
            return []

        actual_buy_count = min(len(buy_list), max_positions)
        cash_per_stock = cash / actual_buy_count

        orders = []
        for stock in buy_list[:actual_buy_count]:
            price = stock.get('price', 0)
            if price <= 0:
                continue

            volume = int(cash_per_stock / price / 100) * 100  # 整手
            if volume > 0:
                orders.append({
                    'ts_code': stock['ts_code'],
                    'volume': volume,
                    'price': price
                })

        return orders

    @staticmethod
    def score_weighted(
        cash: float,
        buy_list: List[Dict],
        max_positions: int
    ) -> List[Dict]:
        """
        按综合分加权分配：得分高的分配更多资金

        公式：weight_i = score_i / Σscore_j

        Args:
            cash: 可用资金
            buy_list: 买入列表（含score和price字段）
            max_positions: 最大持仓数

        Returns:
            交易订单列表
        """
        if not buy_list or cash <= 0:
            return []

        buy_list = sorted(buy_list, key=lambda x: x.get('composite_score', 0), reverse=True)
        actual_buy_count = min(len(buy_list), max_positions)
        buy_list = buy_list[:actual_buy_count]

        total_score = sum(s.get('composite_score', 0) for s in buy_list)

        if total_score == 0:
            return PositionManager.equal_weight(cash, buy_list, max_positions)

        orders = []
        for stock in buy_list:
            score = stock.get('composite_score', 0)
            weight = score / total_score
            cash_for_stock = cash * weight
            price = stock.get('price', 0)

            if price <= 0:
                continue

            volume = int(cash_for_stock / price / 100) * 100
            if volume > 0:
                orders.append({
                    'ts_code': stock['ts_code'],
                    'volume': volume,
                    'price': price
                })

        return orders


# ============================================================================
# 工厂函数
# ============================================================================

def create_buy_signal_strategy(strategy_type: str) -> BuySignalStrategy:
    """
    创建买入策略实例

    Args:
        strategy_type: 策略类型

    Returns:
        策略实例
    """
    strategies = {
        'top_n': BuySignalTopN,
        'threshold': BuySignalThreshold,
        'multi_factor_resonance': BuySignalMultiFactorResonance,
        'technical_breakout': BuySignalTechnicalBreakout,
    }

    strategy_class = strategies.get(strategy_type, BuySignalTopN)
    return strategy_class()


def create_sell_signal_strategy() -> List[SellSignalStrategy]:
    """
    创建卖出策略实例列表（按优先级）

    Returns:
        策略实例列表 [止盈止损, 打分掉出, 技术死叉, 因子恶化]
    """
    return [
        SellSignalProfitLoss(),  # 优先级1
        SellSignalScoreDeterioration(),  # 优先级2
        SellSignalTechnicalDeathCross(),  # 优先级3
        SellSignalFactorDeterioration(),  # 优先级4
    ]

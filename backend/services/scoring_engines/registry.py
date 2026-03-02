"""
打分驱动回测引擎 - 注册表
===========================
集中管理所有引擎版本。新增版本只需在 ENGINES 字典中添加一行。
"""
from typing import Dict, List, Optional
from services.scoring_engines.base_engine import BaseEngine


def _lazy_load_v1():
    from services.scoring_engines.v1_momentum import V1MomentumEngine
    return V1MomentumEngine


def _lazy_load_v2_adaptive():
    from services.scoring_engines.v2_adaptive import AdaptiveEngine
    return AdaptiveEngine


def _lazy_load_v3_enhanced():
    from services.scoring_engines.v3_enhanced import EnhancedAdaptiveEngine
    return EnhancedAdaptiveEngine


def _lazy_load_v4_optimized():
    from services.scoring_engines.v4_optimized import OptimizedAdaptiveEngine
    return OptimizedAdaptiveEngine


def _lazy_load_simple_conservative():
    from services.scoring_engines.simple_conservative import SimpleConservativeEngine
    return SimpleConservativeEngine


def _lazy_load_daily_observer():
    from services.scoring_engines.daily_observer_engine import DailyObserverEngine
    return DailyObserverEngine


# ======================================================================1
#  引擎注册表
#  格式: "engine_id" -> (lazy_loader, 元信息)
#  新增版本只需在这里加一行，前端自动出现选项
#
#  use_observer_params: 是否在观测系统中显示参数控制
#    - True: 引擎使用 decide_daily_trades，需要参数控制
#    - False: 引擎有自己的买卖逻辑，不需要这些参数
# ======================================================================
ENGINES: Dict[str, dict] = {
    "v1_momentum": {
        "loader": _lazy_load_v1,
        "id": "v1_momentum",
        "name": "v1 动量均值回归",
        "desc": "移动止损 + 大盘趋势过滤 + 黑名单 + 信号确认（基线版本）",
        "version": "1.0",
        "use_observer_params": False,  # 有自己的买卖逻辑
    },
    "v2_adaptive": {
        "loader": _lazy_load_v2_adaptive,
        "id": "v2_adaptive",
        "name": "v2 自适应策略",
        "desc": "根据市场状态自动切换因子组合：牛市追涨、震荡反转、熊市防御",
        "version": "2.0",
        "use_observer_params": True,  # 在观测系统使用参数控制
    },
    "v3_enhanced": {
        "loader": _lazy_load_v3_enhanced,
        "id": "v3_enhanced",
        "name": "v3 增强自适应",
        "desc": "趋势确认+成交量验证（过敏感版）",
        "version": "3.0",
        "use_observer_params": False,  # 有自己的买卖逻辑
    },
    "v4_optimized": {
        "loader": _lazy_load_v4_optimized,
        "id": "v4_optimized",
        "name": "v4 优化自适应",
        "desc": "v2基础+成交量确认+智能仓位（⭐推荐）",
        "version": "4.0",
        "use_observer_params": False,  # 有自己的买卖逻辑
    },
    "simple_conservative": {
        "loader": _lazy_load_simple_conservative,
        "id": "simple_conservative",
        "name": "简单保守策略",
        "desc": "固定因子+严格风控+低频交易（稳健型）",
        "version": "1.0",
        "use_observer_params": False,  # 有自己的买卖逻辑
    },
    "daily_observer": {
        "loader": _lazy_load_daily_observer,
        "id": "daily_observer",
        "name": "每日观测引擎",
        "desc": "参数化买卖决策，专用于每日观测系统（可自定义所有参数）",
        "version": "1.0",
        "use_observer_params": True,  # 使用观测参数
    },
}

# 默认引擎ID
DEFAULT_ENGINE_ID = "v2_adaptive"


def get_engine(engine_id: Optional[str] = None) -> BaseEngine:
    """
    获取引擎实例。
    engine_id 为 None 或不存在时返回默认引擎。
    """
    if not engine_id or engine_id not in ENGINES:
        engine_id = DEFAULT_ENGINE_ID
    loader = ENGINES[engine_id]["loader"]
    engine_class = loader()
    return engine_class()


def list_engines() -> List[dict]:
    """
    列出所有可用引擎（供前端下拉框使用）。
    返回格式: [{"id": "v1_momentum", "name": "...", "desc": "...", "version": "1.0", "use_observer_params": bool}, ...]
    """
    result = []
    for eid, info in ENGINES.items():
        result.append({
            "id": info["id"],
            "name": info["name"],
            "desc": info["desc"],
            "version": info["version"],
            "is_default": eid == DEFAULT_ENGINE_ID,
            "use_observer_params": info.get("use_observer_params", False),
        })
    return result

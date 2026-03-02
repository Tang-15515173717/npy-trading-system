"""
套餐配置 - StockQuant Pro
定义各个套餐的权限和价格
"""
from typing import Dict, Any

# 套餐价格配置（元/月）
PLAN_PRICES = {
    'basic': 19,      # 基础版：19元/月
    'pro': 99,        # 专业版：99元/月
    'enterprise': 299 # 企业版：299元/月
}

# 套餐权限配置
PLAN_LIMITS: Dict[str, Dict[str, Any]] = {
    'basic': {
        'name': '基础版',
        'price': 19,
        'max_strategies': 9999,  # 不限制策略数量
        'max_backtests_per_day': 10,
        'max_observers': 2,
        'data_retention_days': 90,  # 数据保留90天
        'features': [
            '无限策略',
            '每日10次回测',
            '2个观测策略',
            '90天数据',
            '基础技术支持'
        ]
    },
    'pro': {
        'name': '专业版',
        'price': 99,
        'max_strategies': 20,
        'max_backtests_per_day': 50,
        'max_observers': 10,
        'data_retention_days': 365,  # 数据保留1年
        'features': [
            '20个策略',
            '每日50次回测',
            '10个观测策略',
            '1年数据',
            '高级技术支持',
            '策略优化建议'
        ]
    },
    'enterprise': {
        'name': '企业版',
        'price': 299,
        'max_strategies': 100,
        'max_backtests_per_day': 200,
        'max_observers': 50,
        'data_retention_days': 730,  # 数据保留2年
        'features': [
            '100个策略',
            '每日200次回测',
            '50个观测策略',
            '2年数据',
            '专属客服',
            '定制化服务',
            'API访问',
            '数据导出'
        ]
    }
}

# 试用期配置
TRIAL_DAYS = 7  # 新用户赠送7天试用期
TRIAL_PLAN = 'basic'  # 试用期套餐为基础版


def get_plan_info(plan: str) -> Dict[str, Any]:
    """
    获取套餐信息
    
    Args:
        plan: 套餐类型 (basic/pro/enterprise)
    
    Returns:
        套餐信息字典
    """
    return PLAN_LIMITS.get(plan, PLAN_LIMITS['basic'])


def get_all_plans() -> Dict[str, Dict[str, Any]]:
    """获取所有套餐信息"""
    return PLAN_LIMITS


def get_plan_price(plan: str) -> int:
    """
    获取套餐价格
    
    Args:
        plan: 套餐类型
    
    Returns:
        价格（元/月）
    """
    return PLAN_PRICES.get(plan, 19)

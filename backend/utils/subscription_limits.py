"""
订阅限制检查模块 - StockQuant Pro SaaS
用于检查租户的套餐限制
"""
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from models.user import Tenant
from models.strategy import Strategy
from models.backtest import BacktestTask
from utils.database import db
from utils.plan_config import PLAN_LIMITS, get_plan_info
from sqlalchemy import func


def get_tenant(tenant_id: int) -> Optional[Tenant]:
    """获取租户信息"""
    return Tenant.query.get(tenant_id)


def get_plan_limits(plan: str) -> Dict:
    """获取套餐限制配置"""
    return get_plan_info(plan)


def can_create_strategy(tenant_id: int) -> Tuple[bool, str]:
    """
    检查是否可以创建新策略
    
    Returns:
        (bool, str): (是否可以创建, 错误消息)
    """
    tenant = get_tenant(tenant_id)
    if not tenant:
        return False, "租户不存在"
    
    if not tenant.is_active:
        return False, "账号已禁用"
    
    # 🆕 检查是否过期
    status = tenant.get_status()
    if status in ['trial_expired', 'expired']:
        if status == 'trial_expired':
            return False, "试用期已结束，请升级套餐"
        return False, "套餐已过期，请续费"
    
    # 获取当前策略数量
    current_count = Strategy.query.filter_by(tenant_id=tenant_id).count()
    
    # 获取套餐限制
    limits = get_plan_limits(tenant.plan)
    max_strategies = limits['max_strategies']
    
    if current_count >= max_strategies:
        return False, f"已达到{limits['name']}策略数量上限（{max_strategies}个），请升级套餐"
    
    return True, ""


def can_run_backtest(tenant_id: int) -> Tuple[bool, str]:
    """
    检查是否可以运行回测（每日限制）
    
    Returns:
        (bool, str): (是否可以运行, 错误消息)
    """
    tenant = get_tenant(tenant_id)
    if not tenant:
        return False, "租户不存在"
    
    if not tenant.is_active:
        return False, "账号已禁用"
    
    # 🆕 检查是否过期
    status = tenant.get_status()
    if status in ['trial_expired', 'expired']:
        if status == 'trial_expired':
            return False, "试用期已结束，请升级套餐"
        return False, "套餐已过期，请续费"
    
    # 获取今日回测次数
    today = date.today()
    today_count = BacktestTask.query.filter(
        BacktestTask.tenant_id == tenant_id,
        func.date(BacktestTask.created_at) == today
    ).count()
    
    # 获取套餐限制
    limits = get_plan_limits(tenant.plan)
    max_backtests = limits['max_backtests_per_day']
    
    if today_count >= max_backtests:
        return False, f"今日回测次数已达上限（{max_backtests}次），请明天再试或升级套餐"
    
    return True, ""


def can_create_observer(tenant_id: int) -> Tuple[bool, str]:
    """
    检查是否可以创建新观测

    Returns:
        (bool, str): (是否可以创建, 错误消息)
    """
    from models.daily_observer import DailyObserverStrategy

    tenant = get_tenant(tenant_id)
    if not tenant:
        return False, "租户不存在"

    if not tenant.is_active:
        return False, "租户已禁用"

    # 获取当前活跃观测数量
    current_count = DailyObserverStrategy.query.filter_by(
        tenant_id=tenant_id,
        status='active'
    ).count()
    
    # 获取套餐限制
    limits = get_plan_limits(tenant.plan)
    max_observers = limits['max_observers']
    
    if current_count >= max_observers:
        return False, f"已达到观测数量上限（{max_observers}个），请升级套餐"
    
    return True, ""


def get_usage_stats(tenant_id: int) -> Dict:
    """
    获取租户的使用统计
    
    Returns:
        Dict: 包含各项使用情况的统计
    """
    tenant = get_tenant(tenant_id)
    if not tenant:
        return {}
    
    # 获取当前使用情况
    strategy_count = Strategy.query.filter_by(tenant_id=tenant_id).count()
    
    today = date.today()
    today_backtest_count = BacktestTask.query.filter(
        BacktestTask.tenant_id == tenant_id,
        func.date(BacktestTask.created_at) == today
    ).count()
    
    # 获取观测数量（如果模型存在）
    try:
        from models.daily_observer import DailyObserverStrategy
        observer_count = DailyObserverStrategy.query.filter_by(
            tenant_id=tenant_id,
            status='active'
        ).count()
    except:
        observer_count = 0
    
    # 获取套餐限制
    limits = get_plan_limits(tenant.plan)
    
    return {
        'plan': tenant.plan,
        'plan_name': limits['name'],
        'plan_price': limits['price'],
        'strategy': {
            'current': strategy_count,
            'limit': limits['max_strategies'],
            'percentage': round(strategy_count / limits['max_strategies'] * 100, 1) if limits['max_strategies'] > 0 else 0
        },
        'backtest': {
            'today': today_backtest_count,
            'daily_limit': limits['max_backtests_per_day'],
            'percentage': round(today_backtest_count / limits['max_backtests_per_day'] * 100, 1) if limits['max_backtests_per_day'] > 0 else 0
        },
        'observer': {
            'current': observer_count,
            'limit': limits['max_observers'],
            'percentage': round(observer_count / limits['max_observers'] * 100, 1) if limits['max_observers'] > 0 else 0
        },
        'tenant': {
            'is_active': tenant.is_active,
            'created_at': tenant.created_at.isoformat() if tenant.created_at else None
        }
    }


def get_all_plans() -> List[Dict]:
    """
    获取所有套餐信息
    
    Returns:
        list: 套餐列表
    """
    return [
        {
            'id': plan_id,
            'name': config['name'],
            'price': config['price'],
            'limits': {
                'max_strategies': config['max_strategies'],
                'max_backtests_per_day': config['max_backtests_per_day'],
                'max_observers': config['max_observers']
            }
        }
        for plan_id, config in PLAN_LIMITS.items()
    ]

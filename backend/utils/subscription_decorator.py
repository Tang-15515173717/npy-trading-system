"""
订阅权限检查装饰器
检查用户套餐是否过期，以及是否有权限访问功能
"""
from functools import wraps
from flask import jsonify, g
from datetime import datetime
from models.user import Tenant


def check_subscription(f):
    """
    检查订阅状态装饰器
    需要在@token_required之后使用
    
    使用方法:
        @token_required
        @check_subscription
        def my_api():
            # 确保用户订阅有效
            pass
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 获取当前用户的租户
        if not hasattr(g, 'user'):
            return jsonify({
                'code': 401,
                'message': '未登录',
                'data': None
            }), 401
        
        tenant = Tenant.query.get(g.user.tenant_id)
        if not tenant:
            return jsonify({
                'code': 404,
                'message': '租户不存在',
                'data': None
            }), 404
        
        # 检查账号状态
        status = tenant.get_status()
        
        if status == 'disabled':
            return jsonify({
                'code': 403,
                'message': '账号已被禁用，请联系客服',
                'data': {
                    'status': 'disabled',
                    'action_required': 'contact_support'
                }
            }), 403
        
        if status == 'trial_expired':
            return jsonify({
                'code': 403,
                'message': '试用期已结束，请升级套餐继续使用',
                'data': {
                    'status': 'trial_expired',
                    'trial_end_date': tenant.trial_end_date.isoformat() if tenant.trial_end_date else None,
                    'action_required': 'upgrade',
                    'redirect': '/subscription'
                }
            }), 403
        
        if status == 'expired':
            return jsonify({
                'code': 403,
                'message': '套餐已过期，请续费继续使用',
                'data': {
                    'status': 'expired',
                    'expire_date': tenant.expire_date.isoformat() if tenant.expire_date else None,
                    'action_required': 'renew',
                    'redirect': '/subscription'
                }
            }), 403
        
        # 订阅有效，继续执行
        return f(*args, **kwargs)
    
    return decorated


def check_feature_limit(feature: str):
    """
    检查功能使用限制装饰器
    
    Args:
        feature: 功能名称 (strategy/backtest/observer)
    
    使用方法:
        @token_required
        @check_subscription
        @check_feature_limit('strategy')
        def create_strategy():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from utils.subscription_limits import (
                can_create_strategy,
                can_run_backtest,
                can_create_observer
            )
            
            tenant_id = g.user.tenant_id
            
            # 根据功能类型检查限制
            if feature == 'strategy':
                allowed, message = can_create_strategy(tenant_id)
            elif feature == 'backtest':
                allowed, message = can_run_backtest(tenant_id)
            elif feature == 'observer':
                allowed, message = can_create_observer(tenant_id)
            else:
                allowed, message = True, ""
            
            if not allowed:
                return jsonify({
                    'code': 403,
                    'message': message,
                    'data': {
                        'feature': feature,
                        'action_required': 'upgrade',
                        'redirect': '/subscription'
                    }
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated
    return decorator

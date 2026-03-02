"""
订阅管理API - StockQuant Pro SaaS
提供套餐信息、使用统计、订阅管理功能
"""
from flask import Blueprint, request, jsonify, g
from utils.auth_decorator import optional_token, token_required, get_current_tenant_id
from utils.subscription_limits import get_usage_stats, get_all_plans, get_plan_limits
from models.user import Tenant
from utils.database import db
from datetime import datetime

subscription_bp = Blueprint('subscription', __name__, url_prefix='/api/subscription')


@subscription_bp.route('/plans', methods=['GET'])
def get_plans():
    """
    获取所有套餐信息
    公开接口，无需登录
    """
    try:
        plans = get_all_plans()
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': plans
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': str(e)
        }), 500


@subscription_bp.route('/current', methods=['GET'])
@subscription_bp.route('/current', methods=['GET'])
@token_required
def get_current_subscription():
    """
    获取当前用户的订阅信息
    """
    try:
        tenant_id = get_current_tenant_id()
        stats = get_usage_stats(tenant_id)
        
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@subscription_bp.route('/usage', methods=['GET'])
@optional_token
def get_usage():
    """
    获取当前用户的使用统计
    可选登录，优先使用Token中的租户ID
    """
    try:
        from utils.auth_decorator import get_current_tenant_id, get_current_user_id
        from flask import g

        # 🆕 优先从Token中获取tenant_id
        tenant_id = get_current_tenant_id()
        user_id = get_current_user_id()

        # 调试日志
        from flask import request
        auth_header = request.headers.get('Authorization', '')
        print(f"DEBUG get_usage - auth_header: {auth_header[:30]}..., user_id: {user_id}, tenant_id: {tenant_id}, g.current_user: {getattr(g, 'current_user', 'NOT_SET')}")

        # 如果没有租户ID，返回默认（免费版）
        if not tenant_id:
            print("DEBUG: No tenant_id, returning default")
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'plan': 'free',
                    'strategy': { 'current': 0, 'limit': 3, 'percentage': 0 },
                    'backtest': { 'today': 0, 'daily_limit': 5, 'percentage': 0 },
                    'observer': { 'current': 0, 'limit': 1, 'percentage': 0 }
                }
            })

        stats = get_usage_stats(tenant_id)

        return jsonify({
            'code': 200,
            'message': 'success',
            'data': stats
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        # 出错时返回默认值
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'plan': 'free',
                'strategy': { 'current': 0, 'limit': 3, 'percentage': 0 },
                'backtest': { 'today': 0, 'daily_limit': 5, 'percentage': 0 },
                'observer': { 'current': 0, 'limit': 1, 'percentage': 0 }
            }
        })


@subscription_bp.route('/upgrade', methods=['POST'])
@token_required
def upgrade_plan():
    """
    升级套餐
    
    Request Body:
        {
            "plan": "basic" | "pro" | "enterprise"
        }
    """
    try:
        # 只有管理员可以升级套餐
        if g.user.role != 'admin':
            return jsonify({
                'success': False,
                'error': '只有管理员可以升级套餐'
            }), 403
        
        data = request.get_json()
        new_plan = data.get('plan')
        
        if not new_plan or new_plan not in ['free', 'basic', 'pro', 'enterprise']:
            return jsonify({
                'success': False,
                'error': '无效的套餐类型'
            }), 400
        
        # 获取租户
        tenant = Tenant.query.get(get_current_tenant_id())
        if not tenant:
            return jsonify({
                'success': False,
                'error': '租户不存在'
            }), 404
        
        # 检查是否降级
        plan_order = ['free', 'basic', 'pro', 'enterprise']
        current_index = plan_order.index(tenant.plan)
        new_index = plan_order.index(new_plan)
        
        if new_index < current_index:
            return jsonify({
                'success': False,
                'error': '升级接口不支持降级，请联系客服'
            }), 400
        
        # 更新套餐
        tenant.plan = new_plan
        limits = get_plan_limits(new_plan)
        tenant.max_strategies = limits['max_strategies']
        tenant.max_backtests_per_day = limits['max_backtests_per_day']
        tenant.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'套餐已升级为 {limits["name"]}',
            'data': {
                'plan': new_plan,
                'plan_name': limits['name'],
                'limits': limits
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@subscription_bp.route('/check-limits', methods=['GET'])
@optional_token
def check_limits():
    """
    检查各项限制
    可选登录，优先使用Token中的租户ID
    """
    try:
        from utils.subscription_limits import can_create_strategy, can_run_backtest, can_create_observer, get_usage_stats

        tenant_id = get_current_tenant_id()

        # 如果没有租户ID，返回默认（免费版）
        if not tenant_id:
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'can_create_strategy': True,
                    'can_run_backtest': True,
                    'can_create_observer': True,
                    'usage': {
                        'strategy_count': 0,
                        'backtest_count': 0,
                        'observer_count': 0,
                        'strategy_limit': 3,
                        'backtest_limit': 5,
                        'observer_limit': 1
                    }
                }
            })

        can_strategy, msg_strategy = can_create_strategy(tenant_id)
        can_backtest, msg_backtest = can_run_backtest(tenant_id)
        can_observer, msg_observer = can_create_observer(tenant_id)

        # 获取使用统计
        usage_stats = get_usage_stats(tenant_id)

        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'can_create_strategy': can_strategy,
                'can_run_backtest': can_backtest,
                'can_create_observer': can_observer,
                'usage': {
                    'strategy_count': usage_stats['strategy']['current'],
                    'backtest_count': usage_stats['backtest']['today'],
                    'observer_count': usage_stats['observer']['current'],
                    'strategy_limit': usage_stats['strategy']['limit'],
                    'backtest_limit': usage_stats['backtest']['daily_limit'],
                    'observer_limit': usage_stats['observer']['limit']
                }
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        # 出错时返回默认值
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'can_create_strategy': True,
                'can_run_backtest': True,
                'can_create_observer': True,
                'usage': {
                    'strategy_count': 0,
                    'backtest_count': 0,
                    'observer_count': 0,
                    'strategy_limit': 3,
                    'backtest_limit': 5,
                    'observer_limit': 1
                }
            }
        })

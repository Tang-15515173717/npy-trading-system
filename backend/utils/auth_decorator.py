"""
认证装饰器 - 替代Flask-Login
提供基于JWT的认证装饰器
"""
from functools import wraps
from flask import request, jsonify, g
from utils.auth_manager import auth_manager, get_current_user_from_token
from models.user import User


def token_required(f):
    """
    JWT Token认证装饰器
    
    使用方法:
        @token_required
        def my_api():
            user_id = g.current_user['user_id']
            tenant_id = g.current_user['tenant_id']
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # 从Header获取Token
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # 如果Header没有，尝试从Query参数获取（兼容某些场景）
        if not token:
            token = request.args.get('token')
        
        if not token:
            return jsonify({
                'code': 401,
                'message': '未提供认证Token',
                'data': None
            }), 401
        
        # 验证Token
        user_info = get_current_user_from_token(token)
        if not user_info:
            return jsonify({
                'code': 401,
                'message': 'Token无效或已过期',
                'data': None
            }), 401
        
        # 验证用户是否存在且激活
        user = User.query.get(user_info['user_id'])
        if not user or not user.is_active:
            return jsonify({
                'code': 401,
                'message': '用户不存在或已被禁用',
                'data': None
            }), 401
        
        # 将用户信息存储到g对象中
        g.current_user = user_info
        g.user = user
        
        return f(*args, **kwargs)
    
    return decorated


def optional_token(f):
    """
    可选Token认证装饰器
    如果有Token则验证，没有Token也允许访问
    
    使用方法:
        @optional_token
        def my_api():
            if hasattr(g, 'current_user'):
                # 已登录用户
                user_id = g.current_user['user_id']
            else:
                # 未登录用户
                pass
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # 从Header获取Token
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # 如果有Token，尝试验证
        if token:
            user_info = get_current_user_from_token(token)
            if user_info:
                user = User.query.get(user_info['user_id'])
                if user and user.is_active:
                    g.current_user = user_info
                    g.user = user
        
        return f(*args, **kwargs)
    
    return decorated


def admin_required(f):
    """
    管理员权限装饰器
    需要先使用token_required装饰器
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'user') or g.user.role != 'admin':
            return jsonify({
                'code': 403,
                'message': '需要管理员权限',
                'data': None
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated


def get_current_user_id() -> int:
    """获取当前用户ID"""
    if hasattr(g, 'current_user'):
        return g.current_user['user_id']
    return None


def get_current_tenant_id() -> int:
    """获取当前租户ID"""
    if hasattr(g, 'current_user'):
        return g.current_user['tenant_id']
    return None

"""
认证API - 用户注册/登录/注销（JWT版本）
实现完整的JWT Token认证流程
"""
from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
from utils.database import db
from models.user import User, Tenant
from utils.auth_manager import auth_manager
from utils.auth_decorator import token_required, get_current_user_id

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    用户注册
    
    Request Body:
        {
            "email": "user@example.com",
            "password": "password123",
            "username": "用户名" (可选)
        }
    """
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        username = data.get('username', email.split('@')[0])

        # 参数校验
        if not email or not password:
            return jsonify({
                'code': 400,
                'message': '邮箱和密码必填',
                'data': None
            }), 400

        if len(password) < 6:
            return jsonify({
                'code': 400,
                'message': '密码至少6位',
                'data': None
            }), 400

        # 检查邮箱是否已注册
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({
                'code': 400,
                'message': '邮箱已被注册',
                'data': None
            }), 400

        # 🆕 创建租户（赠送7天基础版试用）
        trial_end = datetime.utcnow() + timedelta(days=7)
        tenant = Tenant(
            name=username,
            plan='basic',  # 基础版
            max_strategies=5,
            max_backtests_per_day=10,
            is_active=True,
            is_trial=True,  # 试用期
            trial_end_date=trial_end
        )
        db.session.add(tenant)
        db.session.flush()  # 获取租户ID

        # 创建用户
        user = User(
            email=email,
            username=username,
            tenant_id=tenant.id,
            role='member',
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # 生成Token
        tokens = auth_manager.generate_token(user.id, tenant.id, email)
        
        # 创建Session
        session_id = auth_manager.create_session(user.id, tenant.id, tokens['access_token'])

        return jsonify({
            'code': 200,
            'message': '注册成功',
            'data': {
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'tenant_id': tenant.id,
                    'role': user.role
                },
                'tokens': tokens,
                'session_id': session_id
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'message': f'注册失败: {str(e)}',
            'data': None
        }), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    用户登录
    
    Request Body:
        {
            "email": "user@example.com",
            "password": "password123"
        }
    """
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({
                'code': 400,
                'message': '邮箱和密码必填',
                'data': None
            }), 400

        # 查询用户
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return jsonify({
                'code': 401,
                'message': '邮箱或密码错误',
                'data': None
            }), 401

        if not user.is_active:
            return jsonify({
                'code': 403,
                'message': '账号已被禁用',
                'data': None
            }), 403

        # 获取租户信息
        tenant = Tenant.query.get(user.tenant_id)
        if not tenant:
            return jsonify({
                'code': 404,
                'message': '租户不存在',
                'data': None
            }), 404

        # 生成Token
        tokens = auth_manager.generate_token(user.id, user.tenant_id, email)
        
        # 创建Session（会自动踢掉旧Session）
        session_id = auth_manager.create_session(user.id, user.tenant_id, tokens['access_token'])
        
        # 更新最后登录时间
        user.last_login_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'code': 200,
            'message': '登录成功',
            'data': {
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'tenant_id': user.tenant_id,
                    'role': user.role
                },
                'tenant': {
                    'id': tenant.id,
                    'plan': tenant.plan,
                    'max_strategies': tenant.max_strategies,
                    'max_backtests_per_day': tenant.max_backtests_per_day
                },
                'tokens': tokens,
                'session_id': session_id
            }
        })

    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'登录失败: {str(e)}',
            'data': None
        }), 500


@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout():
    """
    用户注销
    需要Token认证
    """
    try:
        # 从请求中获取session_id（如果有）
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        if session_id:
            auth_manager.delete_session(session_id)
        
        # 也可以通过user_id删除所有Session
        user_id = get_current_user_id()
        if user_id:
            user_session_key = f"user_session:{user_id}"
            session_id = auth_manager._get(user_session_key)
            if session_id:
                auth_manager.delete_session(session_id)

        return jsonify({
            'code': 200,
            'message': '注销成功',
            'data': None
        })

    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'注销失败: {str(e)}',
            'data': None
        }), 500


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    刷新Token
    
    Request Body:
        {
            "refresh_token": "xxx"
        }
    """
    try:
        data = request.get_json()
        refresh_token_str = data.get('refresh_token')

        if not refresh_token_str:
            return jsonify({
                'code': 400,
                'message': '缺少refresh_token',
                'data': None
            }), 400

        # 刷新Token
        new_tokens = auth_manager.refresh_token(refresh_token_str)
        if not new_tokens:
            return jsonify({
                'code': 401,
                'message': 'Refresh Token无效或已过期',
                'data': None
            }), 401

        return jsonify({
            'code': 200,
            'message': 'Token刷新成功',
            'data': {
                'tokens': new_tokens
            }
        })

    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'Token刷新失败: {str(e)}',
            'data': None
        }), 500


@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
    """
    获取当前登录用户信息
    需要Token认证
    """
    try:
        user = g.user
        tenant = Tenant.query.get(user.tenant_id)

        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'tenant_id': user.tenant_id,
                    'role': user.role,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'last_login_at': user.last_login_at.isoformat() if user.last_login_at else None
                },
                'tenant': tenant.to_dict() if tenant else None
            }
        })

    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取用户信息失败: {str(e)}',
            'data': None
        }), 500

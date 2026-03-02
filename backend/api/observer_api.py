"""
观测API - StockQuant Pro SaaS
提供观测管理功能，带租户隔离
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.daily_observer import DailyObserverStrategy
from utils.database import db
from utils.subscription_limits import can_create_observer
from datetime import datetime
import json

observer_bp = Blueprint('observer', __name__, url_prefix='/api/observers')


@observer_bp.route('/', methods=['GET'])
@login_required
def list_observers():
    """
    获取观测列表（带租户隔离）
    """
    try:
        tenant_id = current_user.tenant_id

        # 查询参数
        status = request.args.get('status', 'active')
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))

        # 构建查询（租户隔离）
        query = DailyObserverStrategy.query.filter_by(tenant_id=tenant_id)

        if status:
            query = query.filter_by(status=status)

        # 分页
        pagination = query.order_by(DailyObserverStrategy.created_at.desc()).paginate(
            page=page,
            per_page=page_size,
            error_out=False
        )

        observers = [obs.to_dict() for obs in pagination.items]

        return jsonify({
            'success': True,
            'data': {
                'items': observers,
                'total': pagination.total,
                'page': page,
                'page_size': page_size,
                'has_more': pagination.has_next
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@observer_bp.route('/', methods=['POST'])
@login_required
def create_observer():
    """
    创建观测（带数量限制检查）
    """
    try:
        tenant_id = current_user.tenant_id

        # 检查是否可以创建
        can_create, error_msg = can_create_observer(tenant_id)
        if not can_create:
            return jsonify({
                'success': False,
                'error': error_msg,
                'need_upgrade': True
            }), 403

        data = request.get_json()

        # 验证必填字段
        if not data.get('name'):
            return jsonify({
                'success': False,
                'error': '观测名称不能为空'
            }), 400

        # 创建观测
        observer = DailyObserverStrategy(
            tenant_id=tenant_id,
            user_id=current_user.id,
            name=data['name'],
            status='active'
        )

        db.session.add(observer)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '观测创建成功',
            'data': observer.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

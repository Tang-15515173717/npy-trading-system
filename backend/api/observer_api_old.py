"""
观测API - StockQuant Pro SaaS
提供观测管理功能，带租户隔离
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.daily_observer import DailyObserver
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
        query = DailyObserver.query.filter_by(tenant_id=tenant_id)
        
        if status:
            query = query.filter_by(status=status)
        
        # 分页
        pagination = query.order_by(DailyObserver.created_at.desc()).paginate(
            page=page,
            per_page=page_size,
            error_out=False
        )
        
        observers = [observer.to_dict() for observer in pagination.items]
        
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


@observer_bp.route('/<int:observer_id>', methods=['GET'])
@login_required
def get_observer(observer_id):
    """
    获取观测详情（带租户隔离检查）
    """
    try:
        tenant_id = current_user.tenant_id
        
        observer = DailyObserver.query.filter_by(
            id=observer_id,
            tenant_id=tenant_id
        ).first()
        
        if not observer:
            return jsonify({
                'success': False,
                'error': '观测不存在或无权访问'
            }), 404
        
        return jsonify({
            'success': True,
            'data': observer.to_dict()
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
    
    Request Body:
        {
            "name": "观测名称",
            "symbols": ["000001.SZ", "600000.SH"],
            "config": {}
        }
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
        
        if not data.get('symbols'):
            return jsonify({
                'success': False,
                'error': '股票列表不能为空'
            }), 400
        
        # 创建观测
        observer = DailyObserver(
            tenant_id=tenant_id,
            user_id=current_user.id,
            name=data['name'],
            symbols=data['symbols'],
            config=data.get('config', {}),
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


@observer_bp.route('/<int:observer_id>', methods=['PUT'])
@login_required
def update_observer(observer_id):
    """
    更新观测（带租户隔离检查）
    """
    try:
        tenant_id = current_user.tenant_id
        
        observer = DailyObserver.query.filter_by(
            id=observer_id,
            tenant_id=tenant_id
        ).first()
        
        if not observer:
            return jsonify({
                'success': False,
                'error': '观测不存在或无权访问'
            }), 404
        
        data = request.get_json()
        
        # 更新字段
        if 'name' in data:
            observer.name = data['name']
        if 'symbols' in data:
            observer.symbols = data['symbols']
        if 'config' in data:
            observer.config = data['config']
        if 'status' in data:
            observer.status = data['status']
        
        observer.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '观测更新成功',
            'data': observer.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@observer_bp.route('/<int:observer_id>', methods=['DELETE'])
@login_required
def delete_observer(observer_id):
    """
    删除观测（带租户隔离检查）
    """
    try:
        tenant_id = current_user.tenant_id
        
        observer = DailyObserver.query.filter_by(
            id=observer_id,
            tenant_id=tenant_id
        ).first()
        
        if not observer:
            return jsonify({
                'success': False,
                'error': '观测不存在或无权访问'
            }), 404
        
        # 软删除（标记为已删除）
        observer.status = 'deleted'
        observer.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '观测删除成功'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

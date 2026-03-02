"""
信号策略配置管理 API - StockQuant Pro
创建、查询、更新、删除信号策略配置
"""
from flask import Blueprint, request, jsonify
from models.signal_strategy_config import SignalStrategyConfig
from utils.database import db
import json

signal_strategy_bp = Blueprint('signal_strategy', __name__, url_prefix='/api/signal/strategy')


@signal_strategy_bp.route('/config', methods=['POST'])
def create_signal_strategy():
    """创建信号策略配置"""
    try:
        data = request.get_json()

        strategy = SignalStrategyConfig(
            name=data.get('name'),
            description=data.get('description'),
            buy_strategy_type=data.get('buy_strategy_type', 'top_n'),
            buy_params=json.dumps(data.get('buy_params', {})),
            sell_take_profit_ratio=data.get('sell_take_profit_ratio', 0.15),
            sell_stop_loss_ratio=data.get('sell_stop_loss_ratio', -0.08),
            sell_rank_out=data.get('sell_rank_out', 30),
            sell_score_below=data.get('sell_score_below'),
            sell_enable_technical=data.get('sell_enable_technical', False),
            sell_technical_params=json.dumps(data.get('sell_technical_params', {})),
            position_method=data.get('position_method', 'equal'),
            max_positions=data.get('max_positions', 10),
            single_position_max_ratio=data.get('single_position_max_ratio', 0.2)
        )

        db.session.add(strategy)
        db.session.commit()

        return jsonify({
            "code": 200,
            "data": strategy.to_dict(),
            "message": "创建成功"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "code": 400,
            "data": None,
            "message": f"创建失败: {str(e)}"
        })


@signal_strategy_bp.route('/config', methods=['GET'])
def get_signal_strategies():
    """获取信号策略配置列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        keyword = request.args.get('keyword', '')

        query = SignalStrategyConfig.query

        if keyword:
            query = query.filter(SignalStrategyConfig.name.like(f'%{keyword}%'))

        pagination = query.order_by(SignalStrategyConfig.created_at.desc()).paginate(
            page=page, per_page=page_size, error_out=False
        )

        items = [strategy.to_dict() for strategy in pagination.items]

        return jsonify({
            "code": 200,
            "data": {
                "total": pagination.total,
                "page": page,
                "page_size": page_size,
                "items": items
            },
            "message": "success"
        })

    except Exception as e:
        return jsonify({
            "code": 400,
            "data": None,
            "message": f"查询失败: {str(e)}"
        })


@signal_strategy_bp.route('/config/<int:strategy_id>', methods=['GET'])
def get_signal_strategy(strategy_id):
    """获取单个信号策略配置"""
    try:
        strategy = SignalStrategyConfig.query.get(strategy_id)

        if not strategy:
            return jsonify({
                "code": 404,
                "data": None,
                "message": "策略不存在"
            })

        return jsonify({
            "code": 200,
            "data": strategy.to_dict(),
            "message": "success"
        })

    except Exception as e:
        return jsonify({
            "code": 400,
            "data": None,
            "message": f"查询失败: {str(e)}"
        })


@signal_strategy_bp.route('/config/<int:strategy_id>', methods=['PUT'])
def update_signal_strategy(strategy_id):
    """更新信号策略配置"""
    try:
        strategy = SignalStrategyConfig.query.get(strategy_id)

        if not strategy:
            return jsonify({
                "code": 404,
                "data": None,
                "message": "策略不存在"
            })

        data = request.get_json()

        strategy.name = data.get('name', strategy.name)
        strategy.description = data.get('description', strategy.description)
        strategy.buy_strategy_type = data.get('buy_strategy_type', strategy.buy_strategy_type)

        if 'buy_params' in data:
            strategy.buy_params = json.dumps(data['buy_params'])

        strategy.sell_take_profit_ratio = data.get('sell_take_profit_ratio', strategy.sell_take_profit_ratio)
        strategy.sell_stop_loss_ratio = data.get('sell_stop_loss_ratio', strategy.sell_stop_loss_ratio)
        strategy.sell_rank_out = data.get('sell_rank_out', strategy.sell_rank_out)
        strategy.sell_score_below = data.get('sell_score_below', strategy.sell_score_below)
        strategy.sell_enable_technical = data.get('sell_enable_technical', strategy.sell_enable_technical)

        if 'sell_technical_params' in data:
            strategy.sell_technical_params = json.dumps(data['sell_technical_params'])

        strategy.position_method = data.get('position_method', strategy.position_method)
        strategy.max_positions = data.get('max_positions', strategy.max_positions)
        strategy.single_position_max_ratio = data.get('single_position_max_ratio', strategy.single_position_max_ratio)

        db.session.commit()

        return jsonify({
            "code": 200,
            "data": strategy.to_dict(),
            "message": "更新成功"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "code": 400,
            "data": None,
            "message": f"更新失败: {str(e)}"
        })


@signal_strategy_bp.route('/config/<int:strategy_id>', methods=['DELETE'])
def delete_signal_strategy(strategy_id):
    """删除信号策略配置"""
    try:
        strategy = SignalStrategyConfig.query.get(strategy_id)

        if not strategy:
            return jsonify({
                "code": 404,
                "data": None,
                "message": "策略不存在"
            })

        db.session.delete(strategy)
        db.session.commit()

        return jsonify({
            "code": 200,
            "data": None,
            "message": "删除成功"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "code": 400,
            "data": None,
            "message": f"删除失败: {str(e)}"
        })

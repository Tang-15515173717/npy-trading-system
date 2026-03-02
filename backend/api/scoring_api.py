"""
打分配置管理 API - StockQuant Pro
创建、查询、更新、删除打分配置
"""
from flask import Blueprint, request, jsonify
from models.scoring_config import ScoringConfig
from utils.database import db

scoring_bp = Blueprint('scoring', __name__, url_prefix='/api/scoring')


@scoring_bp.route('/config', methods=['POST'])
def create_scoring_config():
    """创建打分配置"""
    try:
        data = request.get_json()

        config = ScoringConfig(
            name=data.get('name'),
            description=data.get('description'),
            normalization_method=data.get('normalization_method', 'percentile'),
            outlier_method=data.get('outlier_method', 'winsorize'),
            outlier_lower_bound=data.get('outlier_lower_bound', 0.01),
            outlier_upper_bound=data.get('outlier_upper_bound', 0.99),
            min_stocks=data.get('min_stocks', 50),
            industry_neutral=data.get('industry_neutral', False)
        )

        db.session.add(config)
        db.session.commit()

        return jsonify({
            "code": 200,
            "data": config.to_dict(),
            "message": "创建成功"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "code": 400,
            "data": None,
            "message": f"创建失败: {str(e)}"
        })


@scoring_bp.route('/config', methods=['GET'])
def get_scoring_configs():
    """获取打分配置列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        keyword = request.args.get('keyword', '')

        query = ScoringConfig.query

        if keyword:
            query = query.filter(ScoringConfig.name.like(f'%{keyword}%'))

        pagination = query.order_by(ScoringConfig.created_at.desc()).paginate(
            page=page, per_page=page_size, error_out=False
        )

        items = [config.to_dict() for config in pagination.items]

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


@scoring_bp.route('/config/<int:config_id>', methods=['GET'])
def get_scoring_config(config_id):
    """获取单个打分配置"""
    try:
        config = ScoringConfig.query.get(config_id)

        if not config:
            return jsonify({
                "code": 404,
                "data": None,
                "message": "配置不存在"
            })

        return jsonify({
            "code": 200,
            "data": config.to_dict(),
            "message": "success"
        })

    except Exception as e:
        return jsonify({
            "code": 400,
            "data": None,
            "message": f"查询失败: {str(e)}"
        })


@scoring_bp.route('/config/<int:config_id>', methods=['PUT'])
def update_scoring_config(config_id):
    """更新打分配置"""
    try:
        config = ScoringConfig.query.get(config_id)

        if not config:
            return jsonify({
                "code": 404,
                "data": None,
                "message": "配置不存在"
            })

        data = request.get_json()

        config.name = data.get('name', config.name)
        config.description = data.get('description', config.description)
        config.normalization_method = data.get('normalization_method', config.normalization_method)
        config.outlier_method = data.get('outlier_method', config.outlier_method)
        config.outlier_lower_bound = data.get('outlier_lower_bound', config.outlier_lower_bound)
        config.outlier_upper_bound = data.get('outlier_upper_bound', config.outlier_upper_bound)
        config.min_stocks = data.get('min_stocks', config.min_stocks)
        config.industry_neutral = data.get('industry_neutral', config.industry_neutral)

        db.session.commit()

        return jsonify({
            "code": 200,
            "data": config.to_dict(),
            "message": "更新成功"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "code": 400,
            "data": None,
            "message": f"更新失败: {str(e)}"
        })


@scoring_bp.route('/config/<int:config_id>', methods=['DELETE'])
def delete_scoring_config(config_id):
    """删除打分配置"""
    try:
        config = ScoringConfig.query.get(config_id)

        if not config:
            return jsonify({
                "code": 404,
                "data": None,
                "message": "配置不存在"
            })

        db.session.delete(config)
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

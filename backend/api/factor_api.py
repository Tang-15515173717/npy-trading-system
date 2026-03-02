"""
因子API接口 - Factor API
提供因子相关接口（含 v2.1 因子组合与按日选股）
"""
from flask import Blueprint, request, jsonify
from services.factor_service import FactorService
from services.factor_combo_service import FactorComboService


factor_bp = Blueprint('factor', __name__, url_prefix='/api/factor')


@factor_bp.route('/library', methods=['GET'])
def get_factor_library():
    """
    5.1 获取因子库
    
    Query Params:
        category: 因子分类（可选）
        is_active: 是否只返回启用的因子（可选）
    
    Returns:
        {code: 200, data: {total: int, factors: list}, message: 'success'}
    """
    try:
        category = request.args.get('category')
        is_active = request.args.get('is_active')
        
        # 转换is_active为布尔值
        if is_active is not None:
            is_active = is_active.lower() == 'true'
        
        result = FactorService.get_factor_library(category, is_active)
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': 'success'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取因子库失败: {str(e)}'
        }), 500


@factor_bp.route('/calculate', methods=['POST'])
def calculate_factors():
    """
    5.2 批量计算因子（真实版本）
    
    Body:
        {
            "ts_codes": ["000001.SZ", "000002.SZ"],
            "trade_date": "20260130",
            "factor_codes": ["return_20d", "rsi_14"],
            "overwrite": false
        }
    
    Returns:
        {code: 200, data: {success_count, fail_count, ...}, message: '计算完成'}
    """
    try:
        data = request.get_json()
        
        ts_codes = data.get('ts_codes', [])
        trade_date = data.get('trade_date')
        factor_codes = data.get('factor_codes')
        overwrite = data.get('overwrite', False)
        
        if not ts_codes:
            return jsonify({
                'code': 400,
                'message': '股票代码列表不能为空'
            }), 400
        
        # ✅ 使用真实计算方法
        result = FactorService.calculate_factors_real(
            ts_codes, trade_date, factor_codes, overwrite
        )
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': f'因子计算完成！成功{result["success_count"]}只，失败{result["fail_count"]}只'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'code': 500,
            'message': f'计算失败: {str(e)}'
        }), 500


@factor_bp.route('/data/<ts_code>', methods=['GET'])
def get_factor_data(ts_code):
    """
    5.3 获取因子数据
    
    Path Params:
        ts_code: 股票代码
    
    Query Params:
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
        factor_codes: 因子代码（逗号分隔，可选）
    
    Returns:
        {code: 200, data: [...], message: 'success'}
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        factor_codes_str = request.args.get('factor_codes')
        
        factor_codes = factor_codes_str.split(',') if factor_codes_str else None
        
        result = FactorService.get_factor_data(
            ts_code, start_date, end_date, factor_codes
        )
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': 'success'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        }), 500


@factor_bp.route('/ic/<factor_code>', methods=['GET'])
def get_factor_ic(factor_code):
    """
    5.4 因子IC分析 (真实对接)
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        forward_days = request.args.get('forward_days', '5')
        
        # 修正：调用 Service 层定义的真名 get_factor_ic_real
        result = FactorService.get_factor_ic_real(factor_code, start_date, end_date, int(forward_days))
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': 'success'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'分析失败: {str(e)}'
        }), 500


@factor_bp.route('/correlation', methods=['POST'])
def analyze_correlation():
    """
    5.5 因子相关性分析 (真实对接)
    """
    try:
        data = request.get_json()
        factor_codes = data.get('factor_codes', [])
        trade_date = data.get('trade_date')
        
        if len(factor_codes) < 2:
            return jsonify({
                'code': 400,
                'message': '至少需要2个因子'
            }), 400
        
        result = FactorService.analyze_correlation_real(factor_codes, trade_date)
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': 'success'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'分析失败: {str(e)}'
        }), 500


@factor_bp.route('/group_analysis', methods=['POST'])
def group_analysis():
    """
    5.6 因子分组收益分析 (真实对接)
    """
    try:
        data = request.get_json()
        factor_code = data.get('factor_code')
        trade_date = data.get('trade_date')
        group_count = data.get('group_count', 5)
        holding_period = data.get('holding_period', 20)
        
        if not factor_code:
            return jsonify({
                'code': 400,
                'message': '因子代码不能为空'
            }), 400
        
        result = FactorService.group_analysis_real(
            factor_code, trade_date, group_count, holding_period
        )
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': 'success'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'分析失败: {str(e)}'
        }), 500


@factor_bp.route('/select/single', methods=['POST'])
def select_single():
    """
    5.7 单因子选股（Mock版本）
    
    Body:
        {
            "factor_code": "return_20d",
            "trade_date": "20260130",
            "direction": "long",
            "stock_count": 30,
            "industry_neutral": false,
            "exclude_st": true
        }
    
    Returns:
        {code: 200, data: {selection_id, selected_stocks, ...}, message: '选股完成'}
    """
    try:
        data = request.get_json()
        
        factor_code = data.get('factor_code')
        trade_date = data.get('trade_date')
        direction = data.get('direction', 'long')
        stock_count = data.get('stock_count', 30)
        industry_neutral = data.get('industry_neutral', False)
        exclude_st = data.get('exclude_st', True)
        
        if not factor_code:
            return jsonify({
                'code': 400,
                'message': '因子代码不能为空'
            }), 400
        
        result = FactorService.select_single_mock(
            factor_code, trade_date, direction, 
            stock_count, industry_neutral, exclude_st
        )
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': '选股完成'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'选股失败: {str(e)}'
        }), 500


@factor_bp.route('/select/multiple', methods=['POST'])
def select_multiple():
    """
    5.8 多因子选股（Mock版本）
    
    Body:
        {
            "selection_name": "动量+价值组合",
            "trade_date": "20260130",
            "factors": [
                {"factor_code": "return_20d", "weight": 0.5, "direction": "long"},
                {"factor_code": "pe_ratio", "weight": 0.5, "direction": "short"}
            ],
            "stock_count": 30,
            "industry_neutral": false,
            "exclude_st": true
        }
    
    Returns:
        {code: 200, data: {selection_id, selected_stocks, ...}, message: '选股完成'}
    """
    try:
        data = request.get_json()
        
        selection_name = data.get('selection_name')
        factors = data.get('factors', [])
        trade_date = data.get('trade_date')
        stock_count = data.get('stock_count', 30)
        industry_neutral = data.get('industry_neutral', False)
        exclude_st = data.get('exclude_st', True)
        
        if not selection_name:
            return jsonify({
                'code': 400,
                'message': '选股方案名称不能为空'
            }), 400
        
        if not factors or len(factors) == 0:
            return jsonify({
                'code': 400,
                'message': '至少需要一个因子'
            }), 400
        
        # 检查权重总和
        total_weight = sum(f.get('weight', 0) for f in factors)
        if abs(total_weight - 1.0) > 0.01:
            return jsonify({
                'code': 400,
                'message': f'因子权重总和必须为1.0（当前：{total_weight}）'
            }), 400
        
        result = FactorService.select_multiple_mock(
            selection_name, factors, trade_date,
            stock_count, industry_neutral, exclude_st
        )
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': '选股完成'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'选股失败: {str(e)}'
        }), 500


@factor_bp.route('/select/history', methods=['GET'])
def get_selection_history():
    """
    5.9 获取选股记录
    
    Query Params:
        page: 页码（默认1）
        page_size: 每页数量（默认20）
    
    Returns:
        {code: 200, data: {total, page, page_size, items}, message: 'success'}
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        
        result = FactorService.get_selection_history(page, page_size)
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': 'success'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        }), 500


@factor_bp.route('/supply_chain/<chain_name>', methods=['GET'])
def get_supply_chain(chain_name):
    """
    5.10 产业链分析
    
    Path Params:
        chain_name: 产业链名称
    
    Returns:
        {code: 200, data: {chain_name, positions, linkage_analysis}, message: 'success'}
    """
    try:
        result = FactorService.get_supply_chain(chain_name)
        
        if not result:
            return jsonify({
                'code': 404,
                'message': f'未找到产业链: {chain_name}'
            }), 404
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': 'success'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        }), 500


@factor_bp.route('/select/supply_chain', methods=['POST'])
def select_by_supply_chain():
    """
    5.11 产业链选股（Mock版本）
    
    Body:
        {
            "chain_name": "新能源汽车",
            "position": "上游",
            "stock_count": 10,
            "include_leaders": true
        }
    
    Returns:
        {code: 200, data: {chain_name, selected_stocks, ...}, message: '选股完成'}
    """
    try:
        data = request.get_json()
        
        chain_name = data.get('chain_name')
        position = data.get('position')
        stock_count = data.get('stock_count', 10)
        include_leaders = data.get('include_leaders', True)
        
        if not chain_name:
            return jsonify({
                'code': 400,
                'message': '产业链名称不能为空'
            }), 400
        
        result = FactorService.select_by_supply_chain_mock(
            chain_name, position, stock_count, include_leaders
        )
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': '选股完成'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'选股失败: {str(e)}'
        }), 500


@factor_bp.route('/industry_analysis', methods=['GET'])
def get_industry_analysis():
    """
    5.12 行业分析统计数据
    
    Query Params:
        trade_date: 交易日期（可选）
    
    Returns:
        {code: 200, data: {trade_date, industries: [...]}, message: 'success'}
    """
    try:
        trade_date = request.args.get('trade_date')
        result = FactorService.get_industry_analysis(trade_date)
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': 'success'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'分析失败: {str(e)}'
        }), 500
@factor_bp.route('/backtest/integrated', methods=['POST'])
def run_integrated_backtest():
    """
    5.13 因子+策略联动回测 (Phase 8 核心接口)
    
    Body:
        {
            "selection_name": "我的组合",
            "factors": [...],
            "strategy_type": "MACD",
            "start_date": "20250101",
            "end_date": "20251231",
            "initial_cash": 1000000
        }
    """
    try:
        data = request.get_json()
        
        selection_name = data.get('selection_name', 'Default_Backtest')
        factors = data.get('factors', [])
        strategy_type = data.get('strategy_type', 'MACD')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        initial_cash = data.get('initial_cash', 1000000.0)
        
        if not factors or not start_date or not end_date:
            return jsonify({
                'code': 400,
                'message': '缺少必要参数 (factors/start_date/end_date)'
            }), 400
            
        result = FactorService.run_integrated_backtest(
            selection_name, factors, strategy_type, 
            start_date, end_date, initial_cash
        )
        
        return jsonify({
            'code': 200,
            'data': result,
            'message': '回测任务执行成功'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'code': 500,
            'message': f'回测执行失败: {str(e)}'
        }), 500


@factor_bp.route('/backtest/transactions/<backtest_id>', methods=['GET'])
def get_backtest_transactions(backtest_id):
    """
    5.14 获取回测交易流水
    """
    try:
        from models.backtest_transaction import BacktestTransaction
        transactions = BacktestTransaction.query.filter_by(
            backtest_id=backtest_id
        ).order_by(BacktestTransaction.trade_date.asc()).all()
        
        return jsonify({
            'code': 200,
            'data': [t.to_dict() for t in transactions],
            'message': 'success'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取流水失败: {str(e)}'
        }), 500


# ---------- v2.1 因子组合与按日选股 ----------

@factor_bp.route('/combo', methods=['GET'])
def get_factor_combo_list():
    """5.12 因子组合列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        keyword = request.args.get('keyword')
        result = FactorComboService.list(page=page, page_size=page_size, keyword=keyword)
        return jsonify({'code': 200, 'data': result, 'message': 'success'})
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@factor_bp.route('/combo/<int:combo_id>', methods=['GET'])
def get_factor_combo_detail(combo_id):
    """5.13 因子组合详情"""
    try:
        result = FactorComboService.get_by_id(combo_id)
        if result is None:
            return jsonify({'code': 404, 'message': '因子组合不存在'}), 404
        return jsonify({'code': 200, 'data': result, 'message': 'success'})
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@factor_bp.route('/combo', methods=['POST'])
def create_factor_combo():
    """5.14 创建因子组合"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'message': '请求体为空'}), 400
        name = data.get('name')
        factor_config = data.get('factor_config')
        selection_rule = data.get('selection_rule')
        if not name or factor_config is None or selection_rule is None:
            return jsonify({'code': 400, 'message': '缺少 name / factor_config / selection_rule'}), 400
        result = FactorComboService.create(name=name, factor_config=factor_config, selection_rule=selection_rule)
        return jsonify({'code': 200, 'data': result, 'message': '创建成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@factor_bp.route('/combo/<int:combo_id>', methods=['PUT'])
def update_factor_combo(combo_id):
    """5.15 更新因子组合"""
    try:
        data = request.get_json() or {}
        name = data.get('name')
        factor_config = data.get('factor_config')
        selection_rule = data.get('selection_rule')
        result = FactorComboService.update(combo_id, name=name, factor_config=factor_config, selection_rule=selection_rule)
        return jsonify({'code': 200, 'data': result, 'message': '更新成功'})
    except ValueError as e:
        return jsonify({'code': 404, 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@factor_bp.route('/combo/<int:combo_id>', methods=['DELETE'])
def delete_factor_combo(combo_id):
    """5.16 删除因子组合"""
    try:
        ok = FactorComboService.delete(combo_id)
        if not ok:
            return jsonify({'code': 404, 'message': '因子组合不存在'}), 404
        return jsonify({'code': 200, 'data': None, 'message': '删除成功'})
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@factor_bp.route('/run_selection', methods=['POST'])
def run_selection():
    """5.17 按日选股"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'message': '请求体为空'}), 400
        trade_date = data.get('trade_date')
        factor_combo_id = data.get('factor_combo_id')
        if not trade_date or factor_combo_id is None:
            return jsonify({'code': 400, 'message': '缺少 trade_date 或 factor_combo_id'}), 400
        result = FactorService.run_selection(trade_date=str(trade_date), factor_combo_id=int(factor_combo_id), save=True)
        return jsonify({'code': 200, 'data': result, 'message': '选股完成'})
    except ValueError as e:
        return jsonify({'code': 400, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500

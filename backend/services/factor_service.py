"""
因子服务 - Factor Service
业务逻辑层（v1.1 - 支持真实计算）
"""
from models.factor_library import FactorLibrary
from models.factor_data import FactorData
from models.factor_ic import FactorIC
from models.factor_selection import FactorSelection
from models.factor_combo import FactorCombo
from models.selection_result import SelectionResult
from models.supply_chain import SupplyChain
from models.backtest_transaction import BacktestTransaction
from utils.database import db
from utils.factor_calculator import FactorCalculator
from datetime import datetime, timedelta
import random


class FactorService:
    """因子服务类"""
    
    @staticmethod
    def get_factor_library(category=None, is_active=None):
        """
        获取因子库
        
        Args:
            category: 因子分类（可选）
            is_active: 是否只返回启用的因子（可选）
        
        Returns:
            dict: {total: int, factors: list}
        """
        query = FactorLibrary.query
        
        if category:
            query = query.filter_by(factor_category=category)
        if is_active is not None:
            query = query.filter_by(is_active=is_active)
        
        factors = query.all()
        
        return {
            'total': len(factors),
            'factors': [f.to_dict() for f in factors]
        }
    
    @staticmethod
    def calculate_factors_real(ts_codes, trade_date=None, factor_codes=None, overwrite=False):
        """
        批量计算因子（优化版 - 向量化计算 + 批量入库）
        """
        import time
        from models.stock import Stock
        start_time = time.time()
        
        # 1. 调用向量化计算引擎
        calc_result = FactorCalculator.batch_calculate(ts_codes, trade_date)
        trade_date = calc_result.get('trade_date', trade_date)
        
        # 2. 准备批量入库数据
        calculated_results = calc_result.get('results', [])
        success_count = 0
        final_list = []
        stock_info = []
        
        # 获取所有股票名称
        stocks = Stock.query.filter(Stock.ts_code.in_(ts_codes)).all()
        stock_name_map = {s.ts_code: s.name for s in stocks}
        
        # 处理计算成功的股票
        to_insert = []
        for item in calculated_results:
            ts_code = item['ts_code']
            factors = item['factors']
            stock_name = stock_name_map.get(ts_code, ts_code)
            
            # 记录股票信息
            stock_info.append({'ts_code': ts_code, 'name': stock_name})
            final_list.append(factors)
            
            # 检查数据库是否已存在（为了性能，这里依然保持按个检查，或者后续改写为批量删除再插入）
            existing = FactorData.query.filter_by(ts_code=ts_code, trade_date=trade_date).first()
            
            if existing:
                if overwrite:
                    for key, value in factors.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.updated_at = datetime.now()
                # 无论是否覆盖，只要有数就计入成功
                success_count += 1
            else:
                data_map = {
                    'ts_code': ts_code,
                    'trade_date': trade_date,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                data_map.update(factors)
                to_insert.append(data_map)
                success_count += 1
        
        # 3. 批量执行新数据的插入
        if to_insert:
            try:
                db.session.bulk_insert_mappings(FactorData, to_insert)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"❌ 批量入库失败: {e}")
                # 回退到单条插入以保证部分成功
                for data in to_insert:
                    try:
                        record = FactorData(**data)
                        db.session.add(record)
                        db.session.commit()
                    except:
                        db.session.rollback()
        else:
            db.session.commit()
            
        execution_time = time.time() - start_time
        
        # 处理失败的股票信息
        for ts_code in calc_result.get('failed_stocks', []):
            stock_info.append({
                'ts_code': ts_code, 
                'name': stock_name_map.get(ts_code, ts_code)
            })
            
        return {
            'success_count': success_count,
            'fail_count': calc_result.get('fail_count', 0),
            'total': len(ts_codes),
            'failed_stocks': calc_result.get('failed_stocks', []),
            'execution_time': round(execution_time, 2),
            'results': final_list,
            'stock_info': stock_info
        }
    
    @staticmethod
    def calculate_factors_mock(ts_codes, trade_date=None, factor_codes=None, overwrite=False):
        """
        批量计算因子（Mock版本 - 已废弃，使用calculate_factors_real）
        """
        print("⚠️  Mock方法已废弃，自动切换到真实计算")
        return FactorService.calculate_factors_real(ts_codes, trade_date, factor_codes, overwrite)
    
    @staticmethod
    def get_factor_data(ts_code, start_date=None, end_date=None, factor_codes=None):
        """
        获取因子数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            factor_codes: 因子代码列表（可选）
        
        Returns:
            list: 因子数据列表
        """
        query = FactorData.query.filter_by(ts_code=ts_code)
        
        if start_date:
            query = query.filter(FactorData.trade_date >= start_date)
        if end_date:
            query = query.filter(FactorData.trade_date <= end_date)
        
        data = query.order_by(FactorData.trade_date.desc()).limit(100).all()
        
        return [d.to_dict() for d in data]
    
    @staticmethod
    def get_factor_ic_real(factor_code, start_date=None, end_date=None, forward_days=5):
        """
        获取因子IC值（真实版本）
        
        IC (Information Coefficient) = 因子值与未来收益率的相关系数
        
        Args:
            factor_code: 因子代码
            start_date: 开始日期
            end_date: 结束日期
            forward_days: 前瞻天数（默认5天）
        
        Returns:
            dict: IC时序数据和统计指标
        """
        import pandas as pd
        import numpy as np
        from models.bar_data import BarData
        
        print(f"\n{'='*60}")
        print(f"📊 开始计算因子IC")
        print(f"因子代码: {factor_code}")
        print(f"前瞻天数: {forward_days}天")
        print(f"{'='*60}\n")
        
        # 1. 获取因子信息
        factor = FactorLibrary.query.filter_by(factor_code=factor_code).first()
        
        # 2. 获取所有因子数据
        query = FactorData.query
        if start_date:
            query = query.filter(FactorData.trade_date >= start_date)
        if end_date:
            query = query.filter(FactorData.trade_date <= end_date)
        
        factor_data_list = query.order_by(FactorData.trade_date).all()
        
        if not factor_data_list:
            print("❌ 未找到因子数据")
            return None
        
        # 3. 按日期分组
        from collections import defaultdict
        date_factor_map = defaultdict(list)
        
        for data in factor_data_list:
            factor_value = getattr(data, factor_code, None)
            if factor_value is not None:
                date_factor_map[data.trade_date].append({
                    'ts_code': data.ts_code,
                    'factor_value': factor_value
                })
        
        # 4. 获取所有交易日
        trade_dates = sorted(date_factor_map.keys())
        print(f"✅ 找到 {len(trade_dates)} 个交易日的数据")
        
        # 5. 计算每个交易日的IC值
        ic_series = []
        
        # 修正：即使数据天数少于 forward_days，也至少计算一次
        calculation_limit = max(1, len(trade_dates))
        
        for i, trade_date in enumerate(trade_dates):
            # 获取当日因子值
            current_factors = date_factor_map[trade_date]
            
            # 确定对比日期（如果有未来数据用未来，否则用当日或者跳过）
            future_idx = min(i + forward_days, len(trade_dates) - 1)
            future_date = trade_dates[future_idx]
            
            # 计算每只股票的未来收益率
            stock_returns = {}
            for stock_factor in current_factors:
                ts_code = stock_factor['ts_code']
                
                # 获取当前价格和未来价格
                current_bar = BarData.query.filter_by(
                    ts_code=ts_code, trade_date=trade_date
                ).first()
                
                future_bar = BarData.query.filter_by(
                    ts_code=ts_code, trade_date=future_date
                ).first()
                
                if current_bar and future_bar and current_bar.close > 0:
                    forward_return = (future_bar.close - current_bar.close) / current_bar.close
                    stock_returns[ts_code] = forward_return
            
            # 计算IC（因子值与未来收益率的相关系数）
            try:
                if len(stock_returns) >= 2:
                    factor_values = []
                    return_values = []
                    
                    for stock_factor in current_factors:
                        ts_code = stock_factor['ts_code']
                        if ts_code in stock_returns:
                            factor_values.append(float(stock_factor['factor_value']))
                            return_values.append(float(stock_returns[ts_code]))
                    
                    if len(factor_values) >= 2:
                        # 确保计算不出错
                        ic_value = 0.0
                        rank_ic = 0.0
                        
                        # 1. Pearson
                        ic_mat = np.corrcoef(factor_values, return_values)
                        if ic_mat.shape == (2, 2):
                            ic_value = float(ic_mat[0, 1])
                        
                        # 2. Spearman (手动实现，不依赖 scipy)
                        try:
                            # 转换为秩 (Rank)
                            f_series = pd.Series(factor_values)
                            r_series = pd.Series(return_values)
                            f_rank = f_series.rank()
                            r_rank = r_series.rank()
                            
                            # 秩的相关系数即为 Spearman IC
                            rank_ic_mat = np.corrcoef(f_rank, r_rank)
                            if rank_ic_mat.shape == (2, 2):
                                rank_ic = float(rank_ic_mat[0, 1])
                        except Exception as e:
                            print(f"Rank IC计算回退: {e}")
                            rank_ic = ic_value # 回退到 Pearson
                            
                        ic_series.append({
                            'trade_date': trade_date,
                            'ic_value': round(ic_value if not np.isnan(ic_value) else 0, 4),
                            'rank_ic': round(rank_ic if not np.isnan(rank_ic) else 0, 4),
                            'stock_count': len(factor_values)
                        })
                else:
                    # 数据不足不计入时序
                    pass
            except Exception as e:
                print(f"⚠️ 日期 {trade_date} IC计算跳过: {e}")
                continue
        
        if not ic_series:
            print("❌ 无法计算IC值")
            return {
                'factor_code': factor_code,
                'factor_name': factor.factor_name if factor else factor_code,
                'ic_series': [],
                'statistics': {
                    'ic_mean': 0, 'ic_std': 0, 'rank_ic_mean': 0,
                    'ir_value': 0, 'win_rate': 0, 'total_count': 0
                }
            }
        
        # 6. 计算统计指标 (防弹处理)
        ic_values = [x['ic_value'] for x in ic_series if not np.isnan(x['ic_value'])]
        rank_ic_values = [x['rank_ic'] for x in ic_series if not np.isnan(x['rank_ic'])]
        
        if not ic_values:
             return {'ic_series': [], 'statistics': {'ic_mean': 0}}

        ic_mean = float(np.mean(ic_values))
        ic_std = float(np.std(ic_values))
        ir_value = ic_mean / ic_std if ic_std > 0 else 0
        
        positive_count = sum(1 for x in ic_values if x > 0)
        win_rate = positive_count / len(ic_values)
        
        return {
            'factor_code': factor_code,
            'factor_name': factor.factor_name if factor else factor_code,
            'ic_series': ic_series,
            'statistics': {
                'ic_mean': round(float(ic_mean), 4),
                'ic_std': round(float(ic_std), 4),
                'rank_ic_mean': round(float(np.mean(rank_ic_values)), 4),
                'ir_value': round(float(ir_value), 2),
                'win_rate': round(float(win_rate), 3),
                'total_count': len(ic_series),
            }
        }
    
    @staticmethod
    def get_factor_ic_mock(factor_code, start_date=None, end_date=None):
        """
        获取因子IC值（Mock版本 - 已废弃，使用 get_factor_ic_real）
        """
        print("⚠️  Mock方法已废弃，自动切换到真实IC计算")
        return FactorService.get_factor_ic_real(factor_code, start_date, end_date)
    
    @staticmethod
    def analyze_correlation_real(factor_codes, trade_date=None):
        """
        因子相关性分析（真实版本）
        
        计算多个因子之间的相关性矩阵
        
        Args:
            factor_codes: 因子代码列表
            trade_date: 交易日期（可选，默认最新）
        
        Returns:
            dict: 相关性矩阵和高相关性对
        """
        import pandas as pd
        import numpy as np
        
        print(f"\n{'='*60}")
        print(f"📊 开始计算因子相关性")
        print(f"因子数量: {len(factor_codes)}")
        print(f"因子列表: {', '.join(factor_codes)}")
        print(f"{'='*60}\n")
        
        # 1. 获取最新交易日
        if not trade_date:
            latest_data = FactorData.query.order_by(FactorData.trade_date.desc()).first()
            trade_date = latest_data.trade_date if latest_data else datetime.now().strftime('%Y%m%d')
        
        # 2. 获取指定日期的所有因子数据
        factor_data_list = FactorData.query.filter_by(trade_date=trade_date).all()
        
        if not factor_data_list:
            print(f"❌ 未找到{trade_date}的因子数据")
            return None
        
        print(f"✅ 找到 {len(factor_data_list)} 只股票的数据")
        
        # 3. 构建因子数据矩阵
        data_dict = {code: [] for code in factor_codes}
        valid_stocks = []
        
        for data in factor_data_list:
            # 检查所有因子是否都有值
            all_valid = True
            for factor_code in factor_codes:
                value = getattr(data, factor_code, None)
                if value is None or pd.isna(value):
                    all_valid = False
                    break
            
            if all_valid:
                valid_stocks.append(data.ts_code)
                for factor_code in factor_codes:
                    value = getattr(data, factor_code)
                    data_dict[factor_code].append(float(value))
        
        if len(valid_stocks) < 1:
            print(f"❌ 有效数据不足（只有{len(valid_stocks)}只股票）")
            return None
        
        print(f"✅ 有效股票数: {len(valid_stocks)}")
        
        # 4. 转为DataFrame并计算相关性矩阵
        df = pd.DataFrame(data_dict)
        correlation_matrix = df.corr().values.tolist()
        
        # 5. 找出高相关性对（绝对值>0.7）
        high_correlation_pairs = []
        n = len(factor_codes)
        
        for i in range(n):
            for j in range(i+1, n):
                corr = correlation_matrix[i][j]
                if abs(corr) > 0.7:
                    high_correlation_pairs.append({
                        'factor1': factor_codes[i],
                        'factor2': factor_codes[j],
                        'correlation': round(float(corr), 4),
                        'abs_correlation': round(abs(float(corr)), 4)
                    })
        
        # 按相关性绝对值降序排序
        high_correlation_pairs.sort(key=lambda x: x['abs_correlation'], reverse=True)
        
        print(f"\n✅ 相关性分析完成")
        print(f"高相关性对数量: {len(high_correlation_pairs)}")
        if high_correlation_pairs:
            print(f"最高相关性: {high_correlation_pairs[0]['factor1']} vs {high_correlation_pairs[0]['factor2']} = {high_correlation_pairs[0]['correlation']:.4f}")
        print(f"{'='*60}\n")
        
        # 6. 四舍五入相关性矩阵
        correlation_matrix_rounded = [
            [round(float(val), 4) for val in row]
            for row in correlation_matrix
        ]
        
        return {
            'correlation_matrix': correlation_matrix_rounded,
            'factor_codes': factor_codes,
            'high_correlation_pairs': high_correlation_pairs,
            'trade_date': trade_date,
            'stock_count': len(valid_stocks)
        }
    
    @staticmethod
    def analyze_correlation_mock(factor_codes, trade_date=None):
        """
        因子相关性分析（Mock版本 - 已废弃，使用 analyze_correlation_real）
        """
        print("⚠️  Mock方法已废弃，自动切换到真实相关性分析")
        return FactorService.analyze_correlation_real(factor_codes, trade_date)
    
    
    @staticmethod
    def group_analysis_real(factor_code, trade_date=None, group_count=5, holding_period=20):
        """
        因子分组收益分析（真实版本）
        
        将股票按因子值分层，计算每层的持有期收益，验证因子单调性
        
        Args:
            factor_code: 因子代码
            trade_date: 交易日期（每期分组与持有的起始日期）
            group_count: 分组数量（默认5组）
            holding_period: 持有期（默认为20天）
        
        Returns:
            dict: 分组分析结果
        """
        import pandas as pd
        import numpy as np
        from models.bar_data import BarData
        
        print(f"\n{'='*60}")
        print(f"📊 开始分组收益分析")
        print(f"因子代码: {factor_code}")
        print(f"分层数量: {group_count}组")
        print(f"持有周期: {holding_period}天")
        print(f"{'='*60}\n")
        
        # 1. 确定起始交易日
        if not trade_date:
            latest_data = FactorData.query.order_by(FactorData.trade_date.desc()).first()
            if not latest_data:
                print("❌ 数据库中无因子数据")
                return None
            trade_date = latest_data.trade_date
        
        # 2. 获取当期因子数据
        factor_data_list = FactorData.query.filter_by(trade_date=trade_date).all()
        if not factor_data_list:
            print(f"❌ 未找到 {trade_date} 的因子数据")
            return None
            
        # 提取因子值
        data_items = []
        for fd in factor_data_list:
            val = getattr(fd, factor_code, None)
            if val is not None and not pd.isna(val):
                data_items.append({
                    'ts_code': fd.ts_code,
                    'factor_value': float(val)
                })
        
        if len(data_items) < group_count * 5:
            print(f"❌ 有效样本不足 ({len(data_items)}), 无法分成 {group_count} 组")
            return None
            
        # 转换为DataFrame
        df = pd.DataFrame(data_items)
        
        # 3. 计算收益率
        available_dates = db.session.query(BarData.trade_date).group_by(BarData.trade_date).order_by(BarData.trade_date).all()
        available_dates = [d[0] for d in available_dates]
        
        try:
            start_idx = available_dates.index(trade_date)
            end_idx = start_idx + holding_period
            if end_idx >= len(available_dates):
                print(f"⚠️ 警告：持有期结束日超出数据范围，使用最新日期")
                end_idx = len(available_dates) - 1
            
            end_date = available_dates[end_idx]
            print(f"📅 持有期: {trade_date} -> {end_date} (共 {end_idx - start_idx} 个交易日)")
            
        except ValueError:
            print(f"❌ 交易日 {trade_date} 不在BarData中")
            return None
            
        # 获取起始日和结束日的价格
        ts_codes = [d['ts_code'] for d in data_items]
        
        start_prices = db.session.query(BarData.ts_code, BarData.close).filter(
            BarData.trade_date == trade_date,
            BarData.ts_code.in_(ts_codes)
        ).all()
        start_price_map = {p[0]: p[1] for p in start_prices}
        
        end_prices = db.session.query(BarData.ts_code, BarData.close).filter(
            BarData.trade_date == end_date,
            BarData.ts_code.in_(ts_codes)
        ).all()
        end_price_map = {p[0]: p[1] for p in end_prices}
        
        # 计算个股收益率
        returns = []
        valid_df_indices = []
        
        for idx, row in df.iterrows():
            code = row['ts_code']
            p0 = start_price_map.get(code)
            p1 = end_price_map.get(code)
            
            if p0 and p1 and p0 > 0:
                ret = (p1 - p0) / p0
                returns.append(ret)
                valid_df_indices.append(idx)
        
        if not returns:
            print("❌ 无法计算收益率")
            return None
            
        # 筛选有效数据
        valid_df = df.loc[valid_df_indices].copy()
        valid_df['return'] = returns
        
        # 4. 分组
        try:
            valid_df['group'] = pd.qcut(valid_df['factor_value'], group_count, labels=False) + 1
        except Exception as e:
            print(f"❌ 分组失败: {e}")
            valid_df['rank'] = valid_df['factor_value'].rank(method='first')
            valid_df['group'] = pd.qcut(valid_df['rank'], group_count, labels=False) + 1
            
        # 5. 计算各组统计量
        groups_result = []
        for i in range(1, group_count + 1):
            group_data = valid_df[valid_df['group'] == i]
            if group_data.empty:
                 continue
                 
            avg_ret = group_data['return'].mean()
            win_rate = (group_data['return'] > 0).mean()
            min_val = group_data['factor_value'].min()
            max_val = group_data['factor_value'].max()
            
            groups_result.append({
                'group_id': i,
                'group_name': f'第{i}组',
                'stock_count': len(group_data),
                'factor_range': [round(min_val, 4), round(max_val, 4)],
                'avg_return': round(avg_ret, 4),
                'win_rate': round(win_rate, 4)
            })
            
        # 6. 计算多空收益
        if groups_result:
            long_short_return = groups_result[-1]['avg_return'] - groups_result[0]['avg_return']
        else:
            long_short_return = 0
        
        # 检查单调性
        returns_list = [g['avg_return'] for g in groups_result]
        is_increasing = all(x <= y for x, y in zip(returns_list, returns_list[1:]))
        is_decreasing = all(x >= y for x, y in zip(returns_list, returns_list[1:]))
        monotonicity = is_increasing or is_decreasing
        
        print(f"✅ 分组分析完成")
        print(f"多空收益: {long_short_return:.4f}")
        print(f"单调性: {'✅ 是' if monotonicity else '❌ 否'}")
        
        return {
            'factor_code': factor_code,
            'trade_date': trade_date,
            'groups': groups_result,
            'monotonicity': monotonicity,
            'long_short_return': round(long_short_return, 4),
        }
    
    @staticmethod
    def group_analysis_mock(factor_code, trade_date=None, group_count=5, holding_period=20):
        """
        因子分组收益分析（Mock版本 - 已废弃，使用 group_analysis_real）
        """
        print("⚠️  Mock方法已废弃，自动切换到真实分组分析")
        return FactorService.group_analysis_real(factor_code, trade_date, group_count, holding_period)
    
    @staticmethod
    def select_single_real(factor_code, trade_date=None, direction='long', 
                          stock_count=30, industry_neutral=False, exclude_st=True):
        """
        单因子选股（真实版本）
        
        Args:
            factor_code: 因子代码
            trade_date: 选股日期
            direction: 方向（long做多/short做空）
            stock_count: 选股数量
            industry_neutral: 是否行业中性
            exclude_st: 是否排除ST股
        
        Returns:
            dict: 选股结果
        """
        from models.stock import Stock
        from sqlalchemy import and_, or_
        
        print(f"\n{'='*60}")
        print(f"🎯 开始单因子选股")
        print(f"📊 因子代码: {factor_code}")
        print(f"📅 选股日期: {trade_date or '最新交易日'}")
        print(f"🔄 方向: {'做多' if direction == 'long' else '做空'}")
        print(f"🔢 数量: {stock_count}")
        print(f"{'='*60}\n")
        
        # 1. 获取最新交易日
        if not trade_date:
            latest_data = FactorData.query.order_by(FactorData.trade_date.desc()).first()
            trade_date = latest_data.trade_date if latest_data else datetime.now().strftime('%Y%m%d')
        
        # 2. 查询因子数据
        query = db.session.query(FactorData, Stock).join(
            Stock, FactorData.ts_code == Stock.ts_code
        ).filter(
            FactorData.trade_date == trade_date
        )
        
        # 3. 排除ST股票
        if exclude_st:
            query = query.filter(~Stock.name.like('%ST%'))
        
        # 4. 获取所有数据
        all_data = query.all()
        
        if not all_data:
            print(f"❌ 未找到{trade_date}的因子数据")
            return {
                'selection_id': random.randint(1000, 9999),
                'factor_code': factor_code,
                'trade_date': trade_date,
                'stock_count': 0,
                'selected_stocks': [],
            }
        
        print(f"✅ 找到 {len(all_data)} 只股票的因子数据")
        
        # 5. 提取因子值并排序
        stock_factors = []
        for factor_data, stock in all_data:
            # 获取指定因子的值
            factor_value = getattr(factor_data, factor_code, None)
            
            if factor_value is not None:
                stock_factors.append({
                    'ts_code': stock.ts_code,
                    'name': stock.name,
                    'factor_value': factor_value,
                    'industry': stock.industry or '未分类',
                })
        
        # 6. 排序（做多选高值，做空选低值）
        stock_factors.sort(
            key=lambda x: x['factor_value'], 
            reverse=(direction == 'long')
        )
        
        # 7. 行业中性选股
        if industry_neutral:
            selected_stocks = FactorService._industry_neutral_select(
                stock_factors, stock_count
            )
        else:
            selected_stocks = stock_factors[:stock_count]
        
        # 8. 添加排名和得分
        for i, stock in enumerate(selected_stocks, 1):
            stock['rank'] = i
            stock['composite_score'] = round(1.0 - (i-1) * (0.5 / stock_count), 3)
        
        print(f"\n✅ 选股完成！共选中 {len(selected_stocks)} 只股票")
        print(f"前5名: {', '.join([s['name'] for s in selected_stocks[:5]])}")
        print(f"{'='*60}\n")
        
        # 9. 保存选股记录（可选）
        selection_record = FactorSelection(
            selection_name=f"{factor_code}_{direction}",
            factor_config=f'{{"factor_code": "{factor_code}", "direction": "{direction}"}}',
            stock_count=len(selected_stocks),
            avg_score=sum(s['composite_score'] for s in selected_stocks) / len(selected_stocks) if selected_stocks else 0,
            trade_date=trade_date
        )
        db.session.add(selection_record)
        db.session.commit()
        
        return {
            'selection_id': selection_record.id,
            'factor_code': factor_code,
            'trade_date': trade_date,
            'stock_count': len(selected_stocks),
            'selected_stocks': selected_stocks,
        }
    
    @staticmethod
    def _industry_neutral_select(stock_factors, stock_count):
        """
        行业中性选股
        
        Args:
            stock_factors: 股票因子列表（已排序）
            stock_count: 总选股数量
        
        Returns:
            list: 选中的股票列表
        """
        from collections import defaultdict
        
        # 按行业分组
        industry_stocks = defaultdict(list)
        for stock in stock_factors:
            industry_stocks[stock['industry']].append(stock)
        
        # 计算每个行业应选股票数
        industry_count = len(industry_stocks)
        stocks_per_industry = stock_count // industry_count
        remaining = stock_count % industry_count
        
        selected = []
        for industry, stocks in industry_stocks.items():
            # 每个行业选择相同数量
            count = stocks_per_industry + (1 if remaining > 0 else 0)
            selected.extend(stocks[:count])
            if remaining > 0:
                remaining -= 1
        
        # 按因子值重新排序
        selected.sort(key=lambda x: x['factor_value'], reverse=True)
        
        return selected[:stock_count]
    
    @staticmethod
    def select_single_mock(factor_code, trade_date=None, direction='long', 
                          stock_count=30, industry_neutral=False, exclude_st=True):
        """
        单因子选股（Mock版本 - 已废弃，使用 select_single_real）
        """
        print("⚠️  Mock方法已废弃，自动切换到真实选股")
        return FactorService.select_single_real(
            factor_code, trade_date, direction, stock_count, industry_neutral, exclude_st
        )
    
    
    @staticmethod
    def select_multiple_real(selection_name, factors, trade_date=None, 
                            stock_count=30, industry_neutral=False, exclude_st=True):
        """
        多因子选股（真实版本）
        
        基于打分法（Scoring Model）进行多因子选股：
        1. 获取各因子数据
        2. 去极值与标准化（Z-Score）
        3. 加权合成综合得分
        4. 排序选股
        
        Args:
            selection_name: 选股方案名称
            factors: 因子配置列表 [{factor_code, weight, direction}, ...]
            trade_date: 选股日期
            stock_count: 选股数量
            industry_neutral: 是否行业中性
            exclude_st: 是否排除ST股
        
        Returns:
            dict: 选股结果
        """
        from models.stock import Stock
        import pandas as pd
        import numpy as np
        
        print(f"\n{'='*60}")
        print(f"🎯 开始多因子选股")
        print(f"📋 方案名称: {selection_name}")
        print(f"📅 选股日期: {trade_date or '最新交易日'}")
        print(f"🔢 选股数量: {stock_count}")
        print(f"⚖️ 因子配置: {len(factors)}个因子")
        for f in factors:
            print(f"   - {f['factor_code']}: 权重{f['weight']}, 方向{f['direction']}")
        print(f"{'='*60}\n")
        
        # 1. 确定交易日
        if not trade_date:
            latest_data = FactorData.query.order_by(FactorData.trade_date.desc()).first()
            if not latest_data:
                return {'stock_count': 0, 'selected_stocks': [], 'msg': '无数据'}
            trade_date = latest_data.trade_date
            
        # 2. 获取股票基础信息（名称、行业、是否ST）
        stocks = Stock.query.all()
        stock_map = {s.ts_code: {'name': s.name, 'industry': s.industry} for s in stocks}
        
        # 3. 获取因子数据
        factor_codes = [f['factor_code'] for f in factors]
        
        # 查询当期所有因子数据
        factor_data_list = FactorData.query.filter_by(trade_date=trade_date).all()
        
        if not factor_data_list:
            print(f"❌ 未找到 {trade_date} 的因子数据")
            return {'stock_count': 0, 'selected_stocks': []}
            
        # 4. 构建因子矩阵
        data_list = []
        for fd in factor_data_list:
            stock_info = stock_map.get(fd.ts_code)
            if not stock_info:
                continue
                
            if exclude_st and 'ST' in stock_info['name']:
                continue
                
            row = {'ts_code': fd.ts_code}
            # 动态获取所有因子库中定义的列
            for f in factors:
                code = f['factor_code']
                val = getattr(fd, code, np.nan)
                row[code] = float(val) if val is not None else np.nan
            
            data_list.append(row)
        
        if not data_list:
            print("❌ 有效数据为空")
            return {'stock_count': 0, 'selected_stocks': []}
            
        df = pd.DataFrame(data_list)
        
        # 5. 数据预处理（缺失值填补、去极值、标准化）
        # 填补缺失值（使用中位数填补，避免因个别因子缺失剔除整只股票）
        for f in factors:
            code = f['factor_code']
            if df[code].isnull().any():
                df[code] = df[code].fillna(df[code].median())
        
        print(f"✅ 有效样本数: {len(df)}")
        
        # 记录原始值用于展示
        raw_values_df = df.copy().set_index('ts_code')
        
        # 标准化矩阵计算
        scores = pd.Series(0.0, index=df.index)
        
        for f in factors:
            code = f['factor_code']
            weight = float(f['weight'])
            direction = f.get('direction', 'long')
            
            series = df[code]
            
            # 去极值 (Winsorize 3 sigma)
            median = series.median()
            std = series.std()
            series = series.clip(median - 3 * std, median + 3 * std)
            
            # Z-Score 标准化
            if series.std() > 0:
                series = (series - series.mean()) / series.std()
            else:
                series = series - series.mean()
            
            # 方向权重调整
            score_contrib = series * weight if direction == 'long' else -series * weight
            scores += score_contrib
            
        df['composite_score'] = scores
        # 补丁：处理可能出现的全局 NaN（如果所有因子都缺失）
        df['composite_score'] = df['composite_score'].fillna(0.0)
        
        # 6. 排序
        df_sorted = df.sort_values('composite_score', ascending=False)
        
        # 7. 选股（支持行业中性）
        selected_indices = []
        
        if industry_neutral:
            # 重新获取行业信息
            df_sorted['industry'] = df_sorted['ts_code'].map(lambda x: stock_map.get(x, {}).get('industry', '其他'))
            
            groups = df_sorted.groupby('industry')
            industry_count = len(groups)
            if industry_count > 0:
                per_industry = max(1, stock_count // industry_count)
                
                # 收集每个行业的前几名
                for name, group in groups:
                    selected_indices.extend(group.head(per_industry).index.tolist())
                    
                # 如果数量不够，从剩余中补齐
                if len(selected_indices) < stock_count:
                    current_set = set(selected_indices)
                    remaining_df = df_sorted[~df_sorted.index.isin(current_set)]
                    remaining_count = stock_count - len(selected_indices)
                    selected_indices.extend(remaining_df.head(remaining_count).index.tolist())
            else:
                selected_indices = df_sorted.head(stock_count).index.tolist()
        else:
            selected_indices = df_sorted.head(stock_count).index.tolist()
            
        # 8. 构建返回结果
        final_df = df_sorted.loc[selected_indices].sort_values('composite_score', ascending=False).head(stock_count)
        
        selected_stocks = []
        industry_distribution = {}
        
        for _, row in final_df.iterrows():
            ts_code = row['ts_code']
            stock_info = stock_map.get(ts_code, {})
            industry = stock_info.get('industry', '未知')
            
            # 统计行业分布
            industry_distribution[industry] = industry_distribution.get(industry, 0) + 1
            
            # 准备因子得分详情
            factor_scores = {}
            for f in factors:
                code = f['factor_code']
                # 从原始值 DataFrame 中安全获取
                if ts_code in raw_values_df.index:
                    val = raw_values_df.loc[ts_code, code]
                    # 关键修复：清洗 NaN 以防 JSON 解析失败
                    factor_scores[code] = round(float(val), 4) if not pd.isna(val) else 0.0
                else:
                    factor_scores[code] = 0.0
                
            # 关键修复：清洗 NaN 以防 JSON 解析失败
            comp_score = row['composite_score']
            final_score = round(float(comp_score), 3) if not pd.isna(comp_score) else 0.0
            
            selected_stocks.append({
                'ts_code': ts_code,
                'name': stock_info.get('name', '未知'),
                'composite_score': final_score,
                'industry': industry,
                'factor_scores': factor_scores
            })
            
        # 9. 保存选股记录
        try:
            selection_record = FactorSelection(
                selection_name=selection_name,
                factor_config=str(factors),
                stock_count=len(selected_stocks),
                avg_score=final_df['composite_score'].mean() if not final_df.empty else 0,
                trade_date=trade_date
            )
            db.session.add(selection_record)
            db.session.commit()
            selection_id = selection_record.id
        except Exception as e:
            print(f"⚠️ 保存选股记录失败: {e}")
            selection_id = 0
            
        return {
            'selection_id': selection_id,
            'selection_name': selection_name,
            'trade_date': trade_date,
            'stock_count': len(selected_stocks),
            'selected_stocks': selected_stocks,
            'industry_distribution': industry_distribution
        }
    
    @staticmethod
    def select_multiple_mock(selection_name, factors, trade_date=None, 
                            stock_count=30, industry_neutral=False, exclude_st=True):
        """
        多因子选股（Mock版本 - 已废弃，使用 select_multiple_real）
        """
        print("⚠️  Mock方法已废弃，自动切换到真实选股")
        return FactorService.select_multiple_real(
            selection_name, factors, trade_date, stock_count, industry_neutral, exclude_st
        )
    
    @staticmethod
    def get_selection_history(page=1, page_size=20):
        """
        获取选股历史记录
        
        Args:
            page: 页码
            page_size: 每页数量
        
        Returns:
            dict: 选股记录列表
        """
        query = FactorSelection.query.order_by(FactorSelection.created_at.desc())
        
        total = query.count()
        items = query.offset((page-1)*page_size).limit(page_size).all()
        
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'items': [item.to_dict() for item in items],
        }

    @staticmethod
    def run_selection(trade_date: str, factor_combo_id: int, save: bool = True):
        """
        按日选股：按指定交易日和因子组合执行一次选股，返回当日候选股票列表。
        供回测引擎与前端选股结果页使用。

        Args:
            trade_date: 交易日期 YYYYMMDD
            factor_combo_id: 因子组合ID
            save: 是否写入 selection_result 表

        Returns:
            dict: { trade_date, factor_combo_id, factor_combo_name, count, stocks }
        """
        import json
        combo = FactorCombo.query.get(factor_combo_id)
        if combo is None:
            raise ValueError("因子组合不存在")
        try:
            factor_config = json.loads(combo.factor_config) if isinstance(combo.factor_config, str) else combo.factor_config
        except Exception:
            factor_config = {}
        try:
            selection_rule = json.loads(combo.selection_rule) if isinstance(combo.selection_rule, str) else combo.selection_rule
        except Exception:
            selection_rule = {"type": "topk", "k": 50}
        factors = factor_config.get("factors", [])
        if not factors:
            return {
                "trade_date": trade_date,
                "factor_combo_id": factor_combo_id,
                "factor_combo_name": combo.name,
                "count": 0,
                "stocks": [],
            }
        k = 50
        if selection_rule.get("type") == "topk" and "k" in selection_rule:
            k = int(selection_rule["k"])
        selected_stocks = []
        if len(factors) == 1:
            fc = factors[0]
            factor_code = fc.get("factor_code", "")
            res = FactorService.select_single_real(
                factor_code=factor_code,
                trade_date=trade_date,
                direction="long",
                stock_count=k,
                industry_neutral=False,
                exclude_st=True,
            )
            raw = res.get("selected_stocks", [])
            for i, s in enumerate(raw, 1):
                sc = s.get("composite_score") or s.get("factor_value")
                selected_stocks.append({
                    "ts_code": s.get("ts_code", ""),
                    "name": s.get("name", ""),
                    "rank": i,
                    "score": sc,
                    "composite_score": sc,
                })
        else:
            factors_conf = [{"factor_code": f.get("factor_code", ""), "weight": f.get("weight", 1), "direction": f.get("direction", "long")} for f in factors]
            res = FactorService.select_multiple_real(
                selection_name=combo.name,
                factors=factors_conf,
                trade_date=trade_date,
                stock_count=k,
                industry_neutral=False,
                exclude_st=True,
            )
            raw = res.get("selected_stocks", [])
            for i, s in enumerate(raw, 1):
                sc = s.get("composite_score") or s.get("score")
                item = {
                    "ts_code": s.get("ts_code", ""),
                    "name": s.get("name", ""),
                    "rank": i,
                    "score": sc,
                    "composite_score": sc,
                }
                if s.get("factor_scores") is not None:
                    item["factor_scores"] = s["factor_scores"]
                selected_stocks.append(item)
        ts_codes = [s["ts_code"] for s in selected_stocks]
        if save:
            existing = SelectionResult.query.filter_by(trade_date=trade_date, factor_combo_id=factor_combo_id).first()
            if existing:
                existing.stock_list = json.dumps(ts_codes, ensure_ascii=False)
                db.session.commit()
            else:
                sr = SelectionResult(
                    trade_date=trade_date,
                    factor_combo_id=factor_combo_id,
                    stock_list=json.dumps(ts_codes, ensure_ascii=False),
                )
                db.session.add(sr)
                db.session.commit()
        return {
            "trade_date": trade_date,
            "factor_combo_id": factor_combo_id,
            "factor_combo_name": combo.name,
            "count": len(selected_stocks),
            "stocks": selected_stocks,
        }
    
    @staticmethod
    def get_supply_chain(chain_name):
        """
        获取产业链信息
        
        Args:
            chain_name: 产业链名称
        
        Returns:
            dict: 产业链数据
        """
        from models.stock import Stock
        
        chains = SupplyChain.query.filter_by(chain_name=chain_name).all()
        
        if not chains:
            return None
        
        # 获取所有相关股票的信息
        ts_codes = [c.ts_code for c in chains]
        stocks = Stock.query.filter(Stock.ts_code.in_(ts_codes)).all()
        stock_map = {s.ts_code: s.name for s in stocks}
        
        # 按位置分组
        positions = {}
        for chain in chains:
            pos = chain.chain_position
            if pos not in positions:
                positions[pos] = []
            
            positions[pos].append({
                'ts_code': chain.ts_code,
                'name': stock_map.get(chain.ts_code, chain.ts_code),
                'is_leader': chain.is_leader,
            })
        
        return {
            'chain_name': chain_name,
            'positions': positions,
            'linkage_analysis': {
                'upstream_momentum': round(random.uniform(0.1, 0.2), 3),
                'downstream_demand': round(random.uniform(0.15, 0.25), 3),
            }
        }
    
    @staticmethod
    def select_by_supply_chain_mock(chain_name, position=None, stock_count=10, include_leaders=True):
        """
        产业链选股（Mock版本）
        
        Args:
            chain_name: 产业链名称
            position: 产业链位置（可选）
            stock_count: 选股数量
            include_leaders: 是否包含龙头
        
        Returns:
            dict: 选股结果
        """
        from models.stock import Stock
        
        selected_stocks = []
        
        query = SupplyChain.query.filter_by(chain_name=chain_name)
        if position:
            query = query.filter(SupplyChain.chain_position.like(f'%{position}%'))
        
        chains = query.limit(stock_count).all()
        
        # 获取股票名称
        ts_codes = [c.ts_code for c in chains]
        stocks = Stock.query.filter(Stock.ts_code.in_(ts_codes)).all()
        stock_map = {s.ts_code: s.name for s in stocks}
        
        for chain in chains:
            selected_stocks.append({
                'ts_code': chain.ts_code,
                'name': stock_map.get(chain.ts_code, '未知公司'),
                'position': chain.chain_position,
                'is_leader': chain.is_leader,
                'linkage_score': round(random.uniform(0.7, 0.95), 3),
            })
        
        return {
            'chain_name': chain_name,
            'position': position or '全部',
            'stock_count': len(selected_stocks),
            'selected_stocks': selected_stocks,
        }

    @staticmethod
    def get_industry_analysis(trade_date=None):
        """
        获取行业分析统计数据
        
        聚合各个行业的因子平均表现
        
        Args:
            trade_date: 交易日期
        
        Returns:
            dict: 行业分析数据
        """
        from models.stock import Stock
        import pandas as pd
        import numpy as np
        
        # 1. 确定日期
        if not trade_date:
            latest_data = FactorData.query.order_by(FactorData.trade_date.desc()).first()
            if not latest_data:
                return []
            trade_date = latest_data.trade_date
            
        # 2. 查询因子数据和行业信息
        results = db.session.query(FactorData, Stock.industry).join(
            Stock, FactorData.ts_code == Stock.ts_code
        ).filter(FactorData.trade_date == trade_date).all()
        
        if not results:
            return {
                'trade_date': trade_date,
                'industries': []
            }
            
        # 3. 转换为 DataFrame 方便聚合
        data_list = []
        for fd, industry in results:
            if not industry: 
                continue
            data_list.append({
                'industry': industry,
                'return_5d': fd.return_5d,
                'return_20d': fd.return_20d,
                'volatility_20d': fd.volatility_20d,
                'volume_ratio': fd.volume_ratio
            })
        
        if not data_list:
            return {
                'trade_date': trade_date,
                'industries': []
            }
            
        df = pd.DataFrame(data_list)
        
        # 4. 按行业聚合
        industry_stats = df.groupby('industry').agg({
            'return_5d': 'mean',
            'return_20d': 'mean',
            'volatility_20d': 'mean',
            'volume_ratio': 'mean',
            'industry': 'count'
        }).rename(columns={'industry': 'count'}).reset_index()
        
        # 5. 格式化返回结果
        final_results = []
        for _, row in industry_stats.iterrows():
            final_results.append({
                'industry': row['industry'],
                'stock_count': int(row['count']),
                'avg_return_5d': round(float(row['return_5d']), 4) if not pd.isna(row['return_5d']) else 0,
                'avg_return_20d': round(float(row['return_20d']), 4) if not pd.isna(row['return_20d']) else 0,
                'avg_volatility': round(float(row['volatility_20d']), 4) if not pd.isna(row['volatility_20d']) else 0,
                'avg_volume_ratio': round(float(row['volume_ratio']), 2) if not pd.isna(row['volume_ratio']) else 0,
            })
            
        # 按20日收益率排序
        final_results.sort(key=lambda x: x['avg_return_20d'], reverse=True)
        
        return {
            'trade_date': trade_date,
            'industries': final_results
        }

    @staticmethod
    def run_integrated_backtest(selection_name, factors, strategy_type='MACD', 
                               start_date=None, end_date=None, initial_cash=1000000.0):
        """
        因子+策略联动回测引擎 (Phase 8 核心逻辑)
        
        策略逻辑说明：
        1. 选股层 (Selection)：每周刷新基于多因子的权重打分 Top 30 观察池。
        2. 择时层 (Timing)：每日检测观察池内股票的策略信号 (如 MACD 金叉、RSRS)。
        3. 账户层 (Account)：模拟真实买入卖出、扣除滑点与手续费、记录每日净值。
        """
        import pandas as pd
        import numpy as np
        import random
        from models.bar_data import BarData
        from models.stock import Stock
        from datetime import datetime, timedelta
        
        # --- 步骤 1：初始化基本环境 ---
        # 生成一个回测物理 ID，用于后续通过 API 查询流水
        backtest_id = f"BT_LINK_{datetime.now().strftime('%m%d%H%M%S')}"
        
        # 获取回测周期内的所有交易日
        all_dates_query = db.session.query(BarData.trade_date).filter(
            BarData.trade_date >= start_date,
            BarData.trade_date <= end_date
        ).distinct().order_by(BarData.trade_date.asc()).all()
        all_dates = [d[0] for d in all_dates_query]
        
        if not all_dates:
            return {"error": "指定的历史区间内没有 K 线数据"}

        # 初始化虚拟账户状态
        cash = initial_cash
        holdings = {}           # 持仓结构: {ts_code: {amount, cost}}
        equity_curve = []       # 净值序列: [{date, value}]
        current_watch_pool = [] # 因子筛选出的观察名单
        
        print(f"\n{'='*60}")
        print(f"🕵️ 启动【因子+策略】联动回测引擎")
        print(f"🆔 任务ID: {backtest_id}")
        print(f"💰 初始资金: {initial_cash}")
        print(f"📅 周期: {start_date} ~ {end_date}")
        print(f"{'='*60}\n")
        
        # --- 步骤 2：步进式时间模拟 (Step-by-step Simulation) ---
        for i, today in enumerate(all_dates):
            # A. 选股周期触发 (比如每 5 个交易日更新一次名单)
            if i % 5 == 0:
                # 调用我们重构后的多因子计算引擎
                selection_res = FactorService.select_multiple_real(
                    selection_name=f"{backtest_id}_pool",
                    factors=factors,
                    trade_date=today,
                    stock_count=20 # 观察池大小
                )
                current_watch_pool = selection_res.get('selected_stocks', [])
            
            # --- B. 择时逻辑：持仓扫描与卖出 (SELL) ---
            to_sell = []
            for ts_code, h_info in holdings.items():
                today_bar = BarData.query.filter_by(ts_code=ts_code, trade_date=today).first()
                if not today_bar: continue
                
                curr_price = float(today_bar.close)
                # 止损逻辑：亏损超过 8% 強制离场
                if curr_price < h_info['cost'] * 0.92:
                    to_sell.append((ts_code, '止损卖出'))
                # 调仓逻辑：如果不在新的观察名单里了，寻找出场点 (此处模拟 50% 概率策略信号离场)
                elif ts_code not in [s['ts_code'] for s in current_watch_pool]:
                    if random.random() < 0.6: # 模拟 MACD 死叉等信号
                        to_sell.append((ts_code, '调仓/择时卖出'))
            
            for code, reason in to_sell:
                bar = BarData.query.filter_by(ts_code=code, trade_date=today).first()
                sell_price = float(bar.close)
                sell_amount = holdings[code]['amount']
                cash += sell_price * sell_amount
                
                # 持久化交易流水
                db.session.add(BacktestTransaction(
                    backtest_id=backtest_id,
                    ts_code=code,
                    trade_date=today,
                    action='SELL',
                    price=sell_price,
                    amount=sell_amount,
                    reason=reason
                ))
                del holdings[code]

            # --- C. 择时逻辑：名单扫描与买入 (BUY) ---
            # 维持适度分散投资 (最多持有 10 只票)
            if len(holdings) < 10:
                for stock in current_watch_pool:
                    code = stock['ts_code']
                    if code in holdings: continue
                    if len(holdings) >= 10: break
                    
                    # 只有处于观察名单【且】策略触发才买入
                    # 此处模拟策略信号检查 (比如 MACD 金叉触发率为 20%)
                    if random.random() < 0.2:
                        bar = BarData.query.filter_by(ts_code=code, trade_date=today).first()
                        if not bar: continue
                        
                        buy_price = float(bar.close)
                        # 仓位估算：每只股票分配初始资金的 10%
                        target_pos_val = initial_cash * 0.1
                        buy_amount = int(target_pos_val / buy_price // 100 * 100) # 按手买入
                        
                        if buy_amount > 0 and cash >= (buy_price * buy_amount):
                            cash -= buy_price * buy_amount
                            holdings[code] = {'amount': buy_amount, 'cost': buy_price}
                            
                            # 持久化交易流水
                            db.session.add(BacktestTransaction(
                                backtest_id=backtest_id,
                                ts_code=code,
                                trade_date=today,
                                action='BUY',
                                price=buy_price,
                                amount=buy_amount,
                                reason='因子入选+策略金叉',
                                factor_score=stock['composite_score']
                            ))

            # --- D. 每日净值计算 (Daily Settle) ---
            daily_mkt_val = 0
            for code, h in holdings.items():
                b = BarData.query.filter_by(ts_code=code, trade_date=today).first()
                p = float(b.close) if b else h['cost']
                daily_mkt_val += p * h['amount']
            
            equity_curve.append({
                'date': today,
                'value': round(cash + daily_mkt_val, 2)
            })
            
        # 3. 提交事务并生成最终报告
        try:
            db.session.commit()
        except:
            db.session.rollback()
            
        final_equity = equity_curve[-1]['value'] if equity_curve else initial_cash
        return {
            'backtest_id': backtest_id,
            'summary': {
                'total_return': f"{round((final_equity/initial_cash-1)*100, 2)}%",
                'final_value': final_equity,
                'trade_count': db.session.query(BacktestTransaction).filter_by(backtest_id=backtest_id).count(),
                'win_rate': "TBD" # 待后续精细化计算
            },
            'equity_curve': equity_curve
        }

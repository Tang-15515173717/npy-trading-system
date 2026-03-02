"""
因子计算器 - Factor Calculator
v1.0 - 实现最简单的动量因子
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from models.bar_data import BarData
from models.stock import Stock
from utils.database import db


class FactorCalculator:
    """因子计算器 - 第一版：只实现最简单的因子"""
    
    @staticmethod
    def calculate_momentum_factors(ts_code: str, trade_date: str) -> dict:
        """
        计算动量因子（最简单的因子）
        
        包含：
        - return_5d: 5日收益率
        - return_20d: 20日收益率
        - return_60d: 60日收益率
        - volatility_20d: 20日波动率
        - volume_ratio: 量比
        
        Args:
            ts_code: 股票代码
            trade_date: 计算日期 YYYYMMDD
        
        Returns:
            dict: 因子值字典，如果数据不足返回None
        """
        try:
            # 1. 获取最近100天的K线数据（确保有足够的历史数据）
            print(f"🔍 查询K线: {ts_code}, date<={trade_date}")
            q = BarData.query.filter_by(ts_code=ts_code)\
                .filter(BarData.trade_date <= trade_date)\
                .order_by(BarData.trade_date.desc())\
                .limit(100)
            
            # print(q.statement) # 打印SQL
            bars = q.all()
            print(f"🔍 查询结果: {len(bars)}条")
            
            if len(bars) < 60:
                print(f"⚠️  {ts_code} 数据不足: 只有{len(bars)}条记录，需要至少60条")
                print(f"    最新日期: {bars[0].trade_date if bars else 'N/A'}")
                print(f"    请求日期: {trade_date}")
                # 尝试查询所有数据总数，确认是否是日期过滤问题
                total_count = BarData.query.filter_by(ts_code=ts_code).count()
                print(f"    数据库总记录数: {total_count}")
                print(f"    第一条记录日期: {bars[0].trade_date if bars else 'N/A'}")
                return None
            
            # 2. 转为DataFrame并按日期正序排列
            df = pd.DataFrame([{
                'trade_date': b.trade_date,
                'close': float(b.close) if b.close else 0,
                'vol': float(b.vol) if b.vol else 0,  # ✅ 修正：使用vol不是volume
                'amount': float(b.amount) if b.amount else 0
            } for b in bars])
            
            df = df.sort_values('trade_date').reset_index(drop=True)
            
            # 确保最新的数据在最后
            if df['trade_date'].iloc[-1] != trade_date:
                print(f"⚠️  {ts_code} 没有 {trade_date} 的数据")
                return None
            
            # 3. 计算收益率因子
            factors = {}
            
            close_t = df['close'].iloc[-1]  # 当天收盘价
            
            # 5日收益率
            if len(df) >= 6:
                close_t5 = df['close'].iloc[-6]
                if close_t5 > 0:
                    factors['return_5d'] = round((close_t - close_t5) / close_t5, 4)
            
            # 20日收益率
            if len(df) >= 21:
                close_t20 = df['close'].iloc[-21]
                if close_t20 > 0:
                    factors['return_20d'] = round((close_t - close_t20) / close_t20, 4)
            
            # 60日收益率
            if len(df) >= 61:
                close_t60 = df['close'].iloc[-61]
                if close_t60 > 0:
                    factors['return_60d'] = round((close_t - close_t60) / close_t60, 4)
            
            # 4. 计算波动率因子（20日年化波动率）
            if len(df) >= 21:
                returns = df['close'].pct_change().tail(20)
                std_20d = returns.std()
                # 年化波动率 = 日波动率 * sqrt(250)
                factors['volatility_20d'] = round(std_20d * np.sqrt(250), 4) if not pd.isna(std_20d) else None
            
            # 5. 计算量比（当日成交量 / 20日平均成交量）
            if len(df) >= 21:
                avg_vol_20d = df['vol'].iloc[-21:-1].mean()  # 前20天的平均成交量
                vol_today = df['vol'].iloc[-1]
                if avg_vol_20d > 0:
                    factors['volume_ratio'] = round(vol_today / avg_vol_20d, 4)
            
            # 6. 计算换手率（成交量/流通股本）
            # 注意：需要流通股本数据，暂时用简化计算
            if len(df) >= 1 and df['amount'].iloc[-1] > 0 and df['vol'].iloc[-1] > 0:
                # 换手率 = 成交量(手) / 流通股本(手) * 100%
                # 简化：用成交额/市值的近似
                factors['turnover_rate'] = round(df['vol'].iloc[-1] / 1000000, 4)  # 简化版
            
            print(f"✅ {ts_code} 因子计算成功: {len(factors)}个因子")
            return factors
            
        except Exception as e:
            print(f"❌ {ts_code} 因子计算失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def calculate_technical_indicators(ts_code: str, trade_date: str) -> dict:
        """
        计算技术指标因子
        
        包含：
        - rsi_14: 14日RSI相对强弱指标
        - macd: MACD指标（DIF值）
        - macd_signal: MACD信号线（DEA值）
        - macd_hist: MACD柱状图（MACD-Signal）
        - beta: Beta系数（相对于市场指数）
        
        Args:
            ts_code: 股票代码
            trade_date: 计算日期 YYYYMMDD
        
        Returns:
            dict: 技术指标值字典，如果数据不足返回None
        """
        try:
            # 1. 获取最近100天的K线数据
            bars = BarData.query.filter_by(ts_code=ts_code)\
                .filter(BarData.trade_date <= trade_date)\
                .order_by(BarData.trade_date.desc())\
                .limit(100)\
                .all()
            
            if len(bars) < 60:
                print(f"⚠️  {ts_code} 数据不足: 只有{len(bars)}条记录")
                return None
            
            # 2. 转为DataFrame
            df = pd.DataFrame([{
                'trade_date': b.trade_date,
                'close': float(b.close) if b.close else 0,
                'high': float(b.high) if b.high else 0,
                'low': float(b.low) if b.low else 0,
            } for b in bars])
            
            df = df.sort_values('trade_date').reset_index(drop=True)
            
            if df['trade_date'].iloc[-1] != trade_date:
                print(f"⚠️  {ts_code} 没有 {trade_date} 的数据")
                return None
            
            indicators = {}
            
            # 3. 计算RSI(14)
            if len(df) >= 15:
                rsi_value = FactorCalculator._calculate_rsi(df['close'], period=14)
                if rsi_value is not None:
                    indicators['rsi_14'] = round(rsi_value, 4)
            
            # 4. 计算MACD
            if len(df) >= 35:  # 需要至少35天数据（26+9）
                macd_values = FactorCalculator._calculate_macd(df['close'])
                if macd_values:
                    indicators['macd'] = round(macd_values['macd'], 4)
                    indicators['macd_signal'] = round(macd_values['signal'], 4)
                    indicators['macd_hist'] = round(macd_values['histogram'], 4)
            
            # 5. 计算Beta（相对于市场指数）
            if len(df) >= 60:
                beta_value = FactorCalculator._calculate_beta(ts_code, trade_date, df)
                if beta_value is not None:
                    indicators['beta'] = round(beta_value, 4)
            
            print(f"✅ {ts_code} 技术指标计算成功: {len(indicators)}个指标")
            return indicators
            
        except Exception as e:
            print(f"❌ {ts_code} 技术指标计算失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        """
        计算RSI相对强弱指标
        
        RSI = 100 - (100 / (1 + RS))
        RS = 平均涨幅 / 平均跌幅
        
        Args:
            prices: 价格序列
            period: 周期（默认14）
        
        Returns:
            float: RSI值（0-100）
        """
        try:
            # 计算价格变化
            delta = prices.diff()
            
            # 分离涨跌
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            # 计算平均涨跌幅（使用EMA）
            avg_gain = gain.ewm(span=period, adjust=False).mean()
            avg_loss = loss.ewm(span=period, adjust=False).mean()
            
            # 计算RS和RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.iloc[-1]
            
        except Exception as e:
            print(f"RSI计算失败: {e}")
            return None
    
    @staticmethod
    def _calculate_macd(prices: pd.Series, fast=12, slow=26, signal=9) -> dict:
        """
        计算MACD指标
        
        MACD = EMA(12) - EMA(26)
        Signal = EMA(MACD, 9)
        Histogram = MACD - Signal
        
        Args:
            prices: 价格序列
            fast: 快线周期（默认12）
            slow: 慢线周期（默认26）
            signal: 信号线周期（默认9）
        
        Returns:
            dict: {'macd': float, 'signal': float, 'histogram': float}
        """
        try:
            # 计算快慢EMA
            ema_fast = prices.ewm(span=fast, adjust=False).mean()
            ema_slow = prices.ewm(span=slow, adjust=False).mean()
            
            # 计算MACD线（DIF）
            macd_line = ema_fast - ema_slow
            
            # 计算信号线（DEA）
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()
            
            # 计算柱状图（MACD）
            histogram = macd_line - signal_line
            
            return {
                'macd': macd_line.iloc[-1],
                'signal': signal_line.iloc[-1],
                'histogram': histogram.iloc[-1]
            }
            
        except Exception as e:
            print(f"MACD计算失败: {e}")
            return None
    
    @staticmethod
    def _calculate_beta(ts_code: str, trade_date: str, stock_df: pd.DataFrame, period: int = 60) -> float:
        """
        计算Beta系数（相对于市场指数）
        
        Beta = Cov(股票收益率, 市场收益率) / Var(市场收益率)
        
        Args:
            ts_code: 股票代码
            trade_date: 计算日期
            stock_df: 股票价格DataFrame
            period: 计算周期（默认60天）
        
        Returns:
            float: Beta值
        """
        try:
            # 1. 确定市场指数代码（根据股票所属市场）
            if ts_code.endswith('.SH'):
                index_code = '000001.SH'  # 上证指数
            else:
                index_code = '399001.SZ'  # 深证成指
            
            # 2. 获取市场指数数据
            index_bars = BarData.query.filter_by(ts_code=index_code)\
                .filter(BarData.trade_date <= trade_date)\
                .order_by(BarData.trade_date.desc())\
                .limit(period + 1)\
                .all()
            
            if len(index_bars) < period:
                print(f"⚠️  市场指数数据不足")
                return None
            
            # 3. 转为DataFrame
            index_df = pd.DataFrame([{
                'trade_date': b.trade_date,
                'close': float(b.close) if b.close else 0,
            } for b in index_bars])
            
            index_df = index_df.sort_values('trade_date').reset_index(drop=True)
            
            # 4. 计算收益率
            stock_returns = stock_df['close'].pct_change().tail(period)
            index_returns = index_df['close'].pct_change().tail(period)
            
            # 5. 计算Beta
            covariance = stock_returns.cov(index_returns)
            variance = index_returns.var()
            
            if variance > 0:
                beta = covariance / variance
                return beta
            
            return None
            
        except Exception as e:
            print(f"Beta计算失败: {e}")
            return None
    
    @staticmethod
    def calculate_reversal_factor(ts_code: str, trade_date: str) -> float:
        """
        计算反转因子（5日反转）
        
        Args:
            ts_code: 股票代码
            trade_date: 计算日期
        
        Returns:
            float: 反转因子值（return_5d的负值）
        """
        try:
            bars = BarData.query.filter_by(ts_code=ts_code)\
                .filter(BarData.trade_date <= trade_date)\
                .order_by(BarData.trade_date.desc())\
                .limit(10)\
                .all()
            
            if len(bars) < 6:
                return None
            
            df = pd.DataFrame([{'close': float(b.close)} for b in bars])
            df = df.sort_index()
            
            close_t = df['close'].iloc[-1]
            close_t5 = df['close'].iloc[-6]
            
            if close_t5 > 0:
                return_5d = (close_t - close_t5) / close_t5
                return round(-return_5d, 4)  # 反转因子是负的收益率
            
            return None
            
        except Exception as e:
            print(f"反转因子计算失败 {ts_code}: {e}")
            return None
    
    @staticmethod
    def batch_calculate_vectorized(ts_codes: list, trade_date: str = None) -> dict:
        """
        批量计算多只股票的因子（向量化优化版）
        
        通过单次大查询和 Pandas 向量化运算提升性能。
        
        Args:
            ts_codes: 股票代码列表
            trade_date: 计算日期，默认为最新交易日
        
        Returns:
            dict: 计算结果统计
        """
        import time
        start_time = time.time()
        
        if not trade_date:
            latest_bar = BarData.query.order_by(BarData.trade_date.desc()).first()
            trade_date = latest_bar.trade_date if latest_bar else datetime.now().strftime('%Y%m%d')
        
        print(f"\n🚀 开始向量化批量计算因子")
        print(f"📅 目标日期: {trade_date}")
        
        # 1. 一次性获取所需的所有K线数据（例如最近90个交易日）
        # 先确定日期范围
        date_limit_query = db.session.query(BarData.trade_date).filter(
            BarData.trade_date <= trade_date
        ).distinct().order_by(BarData.trade_date.desc()).limit(90).all()
        
        if not date_limit_query:
            return {'success_count': 0, 'fail_count': len(ts_codes), 'results': [], 'failed_stocks': ts_codes}
            
        earliest_date = date_limit_query[-1][0]
        
        # 批量查询数据
        bars = BarData.query.filter(
            BarData.ts_code.in_(ts_codes),
            BarData.trade_date >= earliest_date,
            BarData.trade_date <= trade_date
        ).all()
        
        if not bars:
            return {'success_count': 0, 'fail_count': len(ts_codes), 'results': [], 'failed_stocks': ts_codes}
            
        # 2. 转换为 DataFrame 并整理
        full_df = pd.DataFrame([{
            'ts_code': b.ts_code,
            'trade_date': b.trade_date,
            'close': float(b.close),
            'vol': float(b.vol),
            'amount': float(b.amount)
        } for b in bars])
        
        full_df = full_df.sort_values(['ts_code', 'trade_date'])
        
        # 3. 向量化计算各项指标
        results = []
        failed_stocks = []
        
        for ts_code in ts_codes:
            df = full_df[full_df['ts_code'] == ts_code].reset_index(drop=True)
            
            # 基础验证：数据量与日期
            if len(df) < 5 or df['trade_date'].iloc[-1] != trade_date:
                failed_stocks.append(ts_code)
                continue
            
            try:
                factors = {}
                close_t = df['close'].iloc[-1]
                
                # 收益率因子
                for days in [5, 20, 60]:
                    if len(df) > days:
                        p_old = df['close'].iloc[-(days + 1)]
                        if p_old > 0:
                            factors[f'return_{days}d'] = round((close_t - p_old) / p_old, 4)
                
                # 波动率 (20d)
                if len(df) >= 21:
                    rets = df['close'].pct_change().tail(20)
                    factors['volatility_20d'] = round(rets.std() * np.sqrt(250), 4)
                
                # 量比 (20d)
                if len(df) >= 21:
                    avg_v = df['vol'].iloc[-21:-1].mean()
                    if avg_v > 0:
                        factors['volume_ratio'] = round(df['vol'].iloc[-1] / avg_v, 4)
                
                # 技术指标 (RSI, MACD) - 复用逻辑
                rsi = FactorCalculator._calculate_rsi(df['close'])
                if rsi is not None: factors['rsi_14'] = round(rsi, 4)
                
                macd = FactorCalculator._calculate_macd(df['close'])
                if macd:
                    factors['macd'] = round(macd['macd'], 4)
                    factors['macd_signal'] = round(macd['signal'], 4)
                    factors['macd_hist'] = round(macd['histogram'], 4)
                
                results.append({
                    'ts_code': ts_code,
                    'trade_date': trade_date,
                    'factors': factors
                })
            except Exception as e:
                print(f"⚠️ {ts_code} 向量化计算异常: {e}")
                failed_stocks.append(ts_code)
                
        execution_time = time.time() - start_time
        print(f"✨ 向量化计算完成，耗时: {execution_time:.2f}s")
        
        return {
            'success_count': len(results),
            'fail_count': len(failed_stocks),
            'total': len(ts_codes),
            'results': results,
            'failed_stocks': failed_stocks,
            'execution_time': round(execution_time, 2)
        }

    @staticmethod
    def batch_calculate(ts_codes: list, trade_date: str = None) -> dict:
        """
        批量计算多只股票的因子 (封装向量化版本)
        """
        return FactorCalculator.batch_calculate_vectorized(ts_codes, trade_date)


# 测试代码
if __name__ == '__main__':
    # 测试单只股票
    test_code = '000001.SZ'
    test_date = '20260130'
    
    print(f"测试计算 {test_code} 的因子...")
    factors = FactorCalculator.calculate_momentum_factors(test_code, test_date)
    
    if factors:
        print("\n计算结果:")
        for key, value in factors.items():
            print(f"  {key}: {value}")
    else:
        print("计算失败")

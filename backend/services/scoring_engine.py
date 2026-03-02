"""
因子打分引擎 - StockQuant Pro
支持多种标准化方法、极端值处理和综合得分计算
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional


def zscore_normalization(factor_values: pd.Series) -> pd.Series:
    """
    Z-Score 标准化
    公式：(x - μ) / σ
    适用：正态分布或近似正态分布的因子
    优点：保留原始分布，适合统计检验
    缺点：对极端值敏感

    Args:
        factor_values: 因子值序列

    Returns:
        标准化后的序列 (0-1范围)
    """
    mean = factor_values.mean()
    std = factor_values.std()
    if std == 0 or pd.isna(std):
        return pd.Series([0.5] * len(factor_values), index=factor_values.index)

    # 计算Z-Score
    z_scores = (factor_values - mean) / std

    # 将Z-Score映射到0-1范围（使用sigmoid函数）
    # 假设99.7%的数据在±3σ范围内
    normalized = 1 / (1 + np.exp(-z_scores))
    return normalized


def minmax_normalization(factor_values: pd.Series) -> pd.Series:
    """
    Min-Max 标准化
    公式：(x - min) / (max - min)
    适用：有明确上下界的因子
    优点：映射到[0,1]，直观
    缺点：对新数据敏感，极端值影响大

    Args:
        factor_values: 因子值序列

    Returns:
        标准化后的序列 (0-1范围)
    """
    min_val = factor_values.min()
    max_val = factor_values.max()

    if max_val == min_val or pd.isna(min_val) or pd.isna(max_val):
        return pd.Series([0.5] * len(factor_values), index=factor_values.index)

    normalized = (factor_values - min_val) / (max_val - min_val)
    return normalized


def percentile_rank_normalization(factor_values: pd.Series) -> pd.Series:
    """
    分位数排名标准化
    公式：rank(x) / N
    适用：偏态分布、有极端值的因子
    优点：对极端值鲁棒，稳定
    缺点：丢失绝对值信息

    Args:
        factor_values: 因子值序列

    Returns:
        标准化后的序列 (0-1范围)
    """
    # 计算排名百分比
    ranks = factor_values.rank(pct=True)
    return ranks


def handle_outliers(
    factor_values: pd.Series,
    method: str = 'winsorize',
    lower_bound: float = 0.01,
    upper_bound: float = 0.99
) -> pd.Series:
    """
    极端值处理

    Args:
        factor_values: 因子值序列
        method: 处理方法
            - 'winsorize': 缩尾处理（推荐）
            - 'trim': 截尾处理
            - 'clip': 限制范围
        lower_bound: 下分位数
        upper_bound: 上分位数

    Returns:
        处理后的序列
    """
    values = factor_values.copy()

    if method == 'winsorize':
        # 缩尾处理：将超出分位数的值限制在分位数边界
        lower = values.quantile(lower_bound)
        upper = values.quantile(upper_bound)
        return values.clip(lower=lower, upper=upper)

    elif method == 'trim':
        # 截尾处理：删除超出分位数的样本（返回值较少）
        lower = values.quantile(lower_bound)
        upper = values.quantile(upper_bound)
        return values[(values >= lower) & (values <= upper)]

    elif method == 'clip':
        # 限制范围：基于均值±3倍标准差
        mean = values.mean()
        std = values.std()
        if pd.notna(std) and std > 0:
            lower = mean - 3 * std
            upper = mean + 3 * std
            return values.clip(lower=lower, upper=upper)
        return values

    return values


def apply_direction(
    normalized_scores: pd.Series,
    direction: str
) -> pd.Series:
    """
    应用因子方向

    Args:
        normalized_scores: 标准化后的得分 (0-1)
        direction: 因子方向
            - 'long': 正向因子（值越大越好）
            - 'short': 负向因子（值越小越好）

    Returns:
        应用方向后的得分 (0-1)
    """
    if direction == 'short':
        # 负向因子：得分 = 1 - 标准化值
        return 1 - normalized_scores
    return normalized_scores


class ScoringEngine:
    """因子打分引擎"""

    def __init__(self, config: Dict):
        """
        初始化打分引擎

        Args:
            config: 打分配置字典
                {
                    'normalization_method': 'percentile',
                    'outlier_method': 'winsorize',
                    'outlier_lower_bound': 0.01,
                    'outlier_upper_bound': 0.99,
                    'min_stocks': 50
                }
        """
        self.config = config
        self.normalization_method = config.get('normalization_method', 'percentile')
        self.outlier_method = config.get('outlier_method', 'winsorize')
        self.outlier_lower_bound = config.get('outlier_lower_bound', 0.01)
        self.outlier_upper_bound = config.get('outlier_upper_bound', 0.99)
        self.min_stocks = config.get('min_stocks', 50)

    def normalize_factor(
        self,
        factor_values: pd.Series,
        direction: str = 'long'
    ) -> pd.Series:
        """
        标准化单个因子

        Args:
            factor_values: 因子值序列 (index=ts_code)
            direction: 因子方向 ('long' or 'short')

        Returns:
            标准化后的得分序列 (0-1)
        """
        # 1. 处理缺失值
        values = factor_values.dropna()

        if len(values) < self.min_stocks:
            # 数据不足，返回平均分
            return pd.Series([0.5] * len(factor_values), index=factor_values.index)

        # 2. 极端值处理
        processed = handle_outliers(
            values,
            method=self.outlier_method,
            lower_bound=self.outlier_lower_bound,
            upper_bound=self.outlier_upper_bound
        )

        # 3. 标准化
        if self.normalization_method == 'zscore':
            normalized = zscore_normalization(processed)
        elif self.normalization_method == 'minmax':
            normalized = minmax_normalization(processed)
        else:  # percentile
            normalized = percentile_rank_normalization(processed)

        # 4. 应用方向
        scored = apply_direction(normalized, direction)

        # 5. 重新对齐原始索引（填充被dropna的值为0.5）
        result = pd.Series([0.5] * len(factor_values), index=factor_values.index)
        result.update(scored)

        return result

    def calculate_composite_score(
        self,
        factor_data: Dict[str, pd.Series],
        factor_combo: Dict
    ) -> pd.DataFrame:
        """
        计算综合得分

        Args:
            factor_data: {factor_code: Series(index=ts_code, value=factor_value)}
            factor_combo: 因子组合配置
                {
                    'factors': [
                        {'factor_code': 'return_20d', 'score': 40, 'direction': 'long'},
                        {'factor_code': 'pe_ratio', 'score': 30, 'direction': 'short'},
                        ...
                    ]
                }

        Returns:
            DataFrame with columns:
                - ts_code: 股票代码
                - composite_score: 综合得分 (0-100)
                - rank: 排名
                - factor_scores: 各因子得分字典
        """
        # 1. 提取因子配置
        factors_config = factor_combo.get('factors', [])

        if not factors_config:
            raise ValueError("因子组合配置为空")

        # 2. 标准化所有因子
        normalized_scores = {}
        for factor_config in factors_config:
            factor_code = factor_config['factor_code']
            direction = factor_config.get('direction', 'long')

            if factor_code not in factor_data:
                continue

            factor_values = factor_data[factor_code]
            normalized = self.normalize_factor(factor_values, direction)
            normalized_scores[factor_code] = normalized

        if not normalized_scores:
            raise ValueError("没有可用的因子数据")

        # 3. 获取所有股票代码
        all_ts_codes = set()
        for series in normalized_scores.values():
            all_ts_codes.update(series.index)
        all_ts_codes = sorted(all_ts_codes)

        # 4. 计算综合得分
        composite_scores = pd.Series(index=all_ts_codes, dtype=float)

        for factor_config in factors_config:
            factor_code = factor_config['factor_code']
            weight = factor_config.get('score', 0) / 100.0  # 转换为权重（0-1）

            if factor_code not in normalized_scores:
                continue

            # 该因子对所有股票的得分
            factor_scores = normalized_scores[factor_code]

            # 累加：综合得分 = Σ(因子得分 × 权重 × 100)
            composite_scores += factor_scores.reindex(all_ts_codes, fill_value=0.5) * weight * 100

        # 5. 构建结果DataFrame
        result_data = []
        for ts_code in all_ts_codes:
            factor_scores_dict = {}
            for factor_code in normalized_scores:
                factor_scores_dict[factor_code] = float(normalized_scores[factor_code].get(ts_code, 0.5) * 100)

            result_data.append({
                'ts_code': ts_code,
                'composite_score': float(composite_scores.get(ts_code, 50)),
                'factor_scores': factor_scores_dict
            })

        result_df = pd.DataFrame(result_data)

        # 6. 排名
        result_df = result_df.sort_values(by='composite_score', ascending=False)
        result_df['rank'] = range(1, len(result_df) + 1)

        return result_df

    def calculate_daily_scores(
        self,
        factor_data: Dict[str, pd.Series],
        factor_combo: Dict
    ) -> Dict:
        """
        计算当日综合得分（对外接口）

        Args:
            factor_data: {factor_code: Series(index=ts_code, value=factor_value)}
            factor_combo: 因子组合配置

        Returns:
            {
                'stocks': [
                    {
                        'ts_code': '000001.SZ',
                        'composite_score': 85.6,
                        'rank': 1,
                        'factor_scores': {'return_20d': 90.2, 'pe_ratio': 78.5, ...}
                    },
                    ...
                ],
                'total': 总股票数,
                'scoring_method': 使用的标准化方法
            }
        """
        try:
            result_df = self.calculate_composite_score(factor_data, factor_combo)

            return {
                'stocks': result_df.to_dict('records'),
                'total': len(result_df),
                'scoring_method': self.normalization_method
            }
        except Exception as e:
            raise ValueError(f"计算综合得分失败: {str(e)}")

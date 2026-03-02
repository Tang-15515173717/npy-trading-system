"""
因子数据模型 - Factor Data
存储每只股票每个交易日的因子值
"""
from utils.database import db
from datetime import datetime


class FactorData(db.Model):
    """因子数据表 - 存储52个因子值"""
    
    __tablename__ = 'factor_data'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ts_code = db.Column(db.String(20), nullable=False, index=True)
    trade_date = db.Column(db.String(8), nullable=False, index=True)
    
    # 动量因子 (Momentum Factors)
    return_5d = db.Column(db.Float)      # 5日收益率
    return_20d = db.Column(db.Float, index=True)    # 20日收益率
    return_60d = db.Column(db.Float)     # 60日收益率
    rsi_14 = db.Column(db.Float)         # RSI(14)
    macd = db.Column(db.Float)           # MACD（DIF值）
    macd_signal = db.Column(db.Float)    # MACD信号线（DEA值）
    macd_hist = db.Column(db.Float)      # MACD柱状图
    
    # 反转因子 (Reversal Factors)
    reversal_5d = db.Column(db.Float)    # 5日反转
    
    # 波动率因子 (Volatility Factors)
    volatility_20d = db.Column(db.Float) # 20日波动率
    beta = db.Column(db.Float)           # Beta系数
    
    # 流动性因子 (Liquidity Factors)
    turnover_rate = db.Column(db.Float)  # 换手率
    volume_ratio = db.Column(db.Float)   # 量比
    
    # 价值因子 (Value Factors)
    pe_ratio = db.Column(db.Float, index=True)      # 市盈率
    pb_ratio = db.Column(db.Float)       # 市净率
    ps_ratio = db.Column(db.Float)       # 市销率
    dividend_yield = db.Column(db.Float) # 股息率
    
    # 成长因子 (Growth Factors)
    revenue_growth = db.Column(db.Float) # 营收增长率
    profit_growth = db.Column(db.Float)  # 利润增长率
    roe_growth = db.Column(db.Float)     # ROE增长率
    
    # 质量因子 (Quality Factors)
    roe = db.Column(db.Float)            # ROE净资产收益率
    gross_margin = db.Column(db.Float)   # 毛利率
    debt_ratio = db.Column(db.Float)     # 资产负债率
    
    # 盈利因子 (Profitability Factors)
    net_margin = db.Column(db.Float)     # 净利率
    total_asset_turnover = db.Column(db.Float)  # 总资产周转率
    
    # 行业因子 (Industry Factors)
    industry_momentum = db.Column(db.Float)     # 行业动量
    industry_pe = db.Column(db.Float)           # 行业PE
    
    # 产业链因子 (Supply Chain Factors)
    upstream_linkage = db.Column(db.Float)      # 上游联动
    downstream_demand = db.Column(db.Float)     # 下游需求
    
    # 情绪因子 (Sentiment Factors)
    news_sentiment = db.Column(db.Float)        # 新闻情绪
    news_heat = db.Column(db.Float)             # 新闻热度
    social_heat = db.Column(db.Float)           # 社交媒体热度
    
    # 分析师因子 (Analyst Factors)
    analyst_rating = db.Column(db.Float)        # 分析师评级
    rating_trend = db.Column(db.Float)          # 评级趋势
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (
        db.UniqueConstraint('ts_code', 'trade_date', name='unique_stock_date'),
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'ts_code': self.ts_code,
            'trade_date': self.trade_date,
            'return_5d': self.return_5d,
            'return_20d': self.return_20d,
            'return_60d': self.return_60d,
            'rsi_14': self.rsi_14,
            'macd': self.macd,
            'macd_signal': self.macd_signal,
            'macd_hist': self.macd_hist,
            'reversal_5d': self.reversal_5d,
            'volatility_20d': self.volatility_20d,
            'beta': self.beta,
            'turnover_rate': self.turnover_rate,
            'volume_ratio': self.volume_ratio,
            'pe_ratio': self.pe_ratio,
            'pb_ratio': self.pb_ratio,
            'ps_ratio': self.ps_ratio,
            'dividend_yield': self.dividend_yield,
            'revenue_growth': self.revenue_growth,
            'profit_growth': self.profit_growth,
            'roe_growth': self.roe_growth,
            'roe': self.roe,
            'gross_margin': self.gross_margin,
            'debt_ratio': self.debt_ratio,
            'net_margin': self.net_margin,
            'total_asset_turnover': self.total_asset_turnover,
            'industry_momentum': self.industry_momentum,
            'industry_pe': self.industry_pe,
            'upstream_linkage': self.upstream_linkage,
            'downstream_demand': self.downstream_demand,
            'news_sentiment': self.news_sentiment,
            'news_heat': self.news_heat,
            'social_heat': self.social_heat,
            'analyst_rating': self.analyst_rating,
            'rating_trend': self.rating_trend,
        }

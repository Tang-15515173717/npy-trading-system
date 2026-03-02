"""
在 data_api.py 中添加指数数据接口
"""

# 在文件开头导入
from services.index_scheduler import index_scheduler

# 添加以下路由

@data_bp.route("/index/realtime", methods=["GET"])
def get_realtime_index():
    """
    获取实时指数数据（15分钟缓存）
    
    Query Params:
        code: 指数代码（可选，如 000001），不传返回所有主要指数
    
    Returns:
        {
            "code": 200,
            "data": {
                "000001": {
                    "name": "上证指数",
                    "price": 3245.67,
                    "change": 12.34,
                    "change_pct": 0.38,
                    "update_time": "2026-01-30 14:45:00"
                },
                ...
            },
            "meta": {
                "last_update": "2026-01-30 14:45:00",
                "count": 8
            }
        }
    """
    try:
        code = request.args.get("code")
        
        if code:
            # 获取单个指数
            data = index_scheduler.get_index_data(code)
            if data is None:
                return error(message=f"未找到指数：{code}", code=404)
            return success(data=data)
        else:
            # 获取主要指数
            result = index_scheduler.get_main_indices()
            meta = {
                'last_update': index_scheduler.last_update.strftime('%Y-%m-%d %H:%M:%S') if index_scheduler.last_update else None,
                'count': len(result)
            }
            return success(data={'indices': result, 'meta': meta})
            
    except Exception as e:
        return error(message=f"获取失败：{str(e)}", code=500)


@data_bp.route("/index/history/<ts_code>", methods=["GET"])
def get_index_history(ts_code: str):
    """
    获取指数历史数据（用于图表展示）
    
    Path Params:
        ts_code: 指数代码（如 000001.SH）
    
    Query Params:
        start_date: 开始日期 YYYYMMDD（可选）
        end_date: 结束日期 YYYYMMDD（可选）
        period: 快捷时间段（可选）：1d, 5d, 1m, 3m, 6m, 1y, 3y, 5y
    
    Returns:
        {
            "code": 200,
            "data": [
                {
                    "date": "20260130",
                    "open": 3234.56,
                    "close": 3245.67,
                    "high": 3256.78,
                    "low": 3223.45,
                    "volume": 234567890
                },
                ...
            ]
        }
    """
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        period = request.args.get("period")
        
        # 根据 period 计算日期范围
        if period and not start_date:
            from datetime import datetime, timedelta
            end = datetime.now()
            
            period_map = {
                '1d': 1,
                '5d': 5,
                '1m': 30,
                '3m': 90,
                '6m': 180,
                '1y': 365,
                '3y': 365*3,
                '5y': 365*5
            }
            
            days = period_map.get(period, 365)
            start = end - timedelta(days=days)
            
            start_date = start.strftime('%Y%m%d')
            end_date = end.strftime('%Y%m%d')
        
        # 调用数据服务（需要实现）
        # 这里可以从数据库获取，或实时从AKShare获取
        import akshare as ak
        
        # 转换代码格式（000001.SH → sh000001）
        if ts_code.endswith('.SH'):
            ak_symbol = 'sh' + ts_code.replace('.SH', '')
        elif ts_code.endswith('.SZ'):
            ak_symbol = 'sz' + ts_code.replace('.SZ', '')
        else:
            ak_symbol = ts_code
        
        df = ak.stock_zh_index_daily(symbol=ak_symbol)
        
        if df is None or df.empty:
            return error(message="未获取到数据", code=404)
        
        # 筛选日期
        if start_date:
            start_date_dt = start_date.replace('-', '')
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y%m%d')
            df = df[df['date'] >= start_date_dt]
        
        if end_date:
            end_date_dt = end_date.replace('-', '')
            df = df[df['date'] <= end_date_dt]
        
        # 转换为前端需要的格式
        result = []
        for _, row in df.iterrows():
            result.append({
                'date': row['date'],
                'open': float(row['open']),
                'close': float(row['close']),
                'high': float(row['high']),
                'low': float(row['low']),
                'volume': float(row['volume'])
            })
        
        return success(data=result)
        
    except Exception as e:
        return error(message=f"获取失败：{str(e)}", code=500)

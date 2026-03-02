"""
数据管理 API - StockQuant Pro
提供股票列表、🔴数据下载（从TuShare）、K 线查询、大盘、搜索、统计等接口。

🔴 v1.1 核心更新：
- 明确"下载数据"功能：从 TuShare API 下载真实数据到数据库
- 新增：增量下载功能（自动检测已有数据）
- 新增：数据完整性检查接口

🔴 v1.2 核心更新：
- 新增：指数实时数据接口（15分钟更新，内存缓存）
- 新增：指数历史数据接口（日K线，数据库查询）
"""
from flask import Blueprint, request
from utils.response import success, error
from services.data_service import DataService
from services.index_scheduler import index_scheduler
from services.index_data_service import IndexDataService

data_bp = Blueprint("data", __name__, url_prefix="/api/data")
data_service = DataService()


@data_bp.route("/hello", methods=["GET"])
def hello():
    """
    联调用 Hello 接口。

    Returns:
        { "code": 200, "data": null, "message": "Hello from StockQuant Pro" }
    """
    return success(message="Hello from StockQuant Pro")


@data_bp.route("/stocks", methods=["GET"])
def get_stock_list():
    """
    获取股票列表（支持分页、筛选、搜索）。

    Query Params:
        keyword: 搜索关键词（代码/名称模糊匹配）🆕
        exchange: 交易所（SSE/SZSE）
        industry: 行业
        list_status: 上市状态（L/D/P）
        stock_type: 🆕 股票类型（key=重点股票，normal=普通股票）
        has_full_data: 🆕 是否有完整历史数据（true/false）
        has_factor_data: 🆕 是否有因子数据（true/false）
        page: 页码，默认1
        page_size: 每页数量，默认50，最大1000 🔴 v1.2优化

    Returns:
        {
            "code": 200,
            "data": {
                "total": 总数,
                "page": 当前页,
                "page_size": 每页数量,
                "items": [股票列表]
            },
            "message": "success"
        }
    """
    try:
        keyword = request.args.get("keyword")
        exchange = request.args.get("exchange")
        industry = request.args.get("industry")
        list_status = request.args.get("list_status")
        stock_type = request.args.get("stock_type")  # 新增
        has_full_data = request.args.get("has_full_data")  # 新增
        has_factor_data = request.args.get("has_factor_data")  # 🆕 新增
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 50))

        # 🔴 v1.2 优化：放宽分页限制，支持更大数据量
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50
        if page_size > 1000:  # 提升到1000
            page_size = 1000

        result = data_service.get_stock_list(
            keyword=keyword,
            exchange=exchange,
            industry=industry,
            list_status=list_status,
            stock_type=stock_type,  # 新增
            has_full_data=has_full_data,  # 新增
            has_factor_data=has_factor_data,  # 🆕 新增
            page=page,
            page_size=page_size,
        )
        return success(data=result)
    except ValueError as e:
        return error(message=f"参数错误：{str(e)}", code=400)
    except Exception as e:
        return error(message=f"服务器错误：{str(e)}", code=500)


@data_bp.route("/search", methods=["GET"])
def search_stocks():
    """
    搜索股票（按代码或名称模糊匹配）。

    Query Params:
        keyword: 搜索关键词（必填）
        limit: 返回数量，默认10

    Returns:
        {
            "code": 200,
            "data": [股票列表],
            "message": "success"
        }
    """
    try:
        keyword = request.args.get("keyword")
        if not keyword:
            return error(message="缺少参数：keyword", code=400)

        limit = int(request.args.get("limit", 10))
        if limit < 1:
            limit = 10
        if limit > 50:
            limit = 50

        result = data_service.search_stocks(keyword=keyword, limit=limit)
        return success(data=result)
    except Exception as e:
        return error(message=f"搜索失败：{str(e)}", code=500)


@data_bp.route("/sync_stocks", methods=["POST"])
def sync_stocks():
    """
    从 TuShare 同步股票列表到数据库（管理员功能）。

    Returns:
        { "code": 200, "data": { "success_count": ..., "total": ... }, "message": "..." }
    """
    try:
        result = data_service.sync_stock_list_from_tushare()
        return success(data=result, message=f"同步完成，成功 {result['success_count']} 只")
    except Exception as e:
        return error(message=f"同步失败：{str(e)}", code=500)


@data_bp.route("/download", methods=["POST"])
def download_stock_data():
    """
    🔴【v1.1 重要更新】批量下载股票 K 线数据（从 TuShare API 到数据库）
    
    核心功能：
    - 从 TuShare API 获取真实A股历史行情数据
    - 存储到本地数据库 bar_data 表
    - ⚠️ 不是导出数据库中已有的数据
    
    v1.1 新增特性：
    - ✅ 增量下载（自动检测已有数据，仅下载缺失部分）
    - ✅ 断点续传（失败后可重试，不会重复下载）
    - ✅ 数据完整性验证
    
    Request Body:
        {
            "ts_codes": ["000001.SZ", "000002.SZ"],  // 股票代码列表
            "start_date": "20230101",                 // 开始日期 YYYYMMDD
            "end_date": "20260129",                   // 结束日期 YYYYMMDD
            "freq": "D"                               // 频率：D(日线)
        }

    Returns:
        {
            "code": 200,
            "data": {
                "success_count": 48,
                "fail_count": 2,
                "total": 50,
                "failed_stocks": ["000003.SZ"],
                "stored_records": 12000,              // 🔴 v1.1新增：存储记录数
                "data_source": "TuShare API",          // 🔴 v1.1新增：数据源
                "incremental": true                    // 🔴 v1.1新增：是否增量
            },
            "message": "从TuShare下载完成，已存储到数据库"
        }
        
    数据流程：
        前端调用 → data_service.download_stock_data() →
        检查已有数据（增量）→ TushareHelper.get_daily_data() →
        TuShare API → 存储到 bar_data 表 → 返回统计
    """
    try:
        data = request.get_json()
        if not data:
            return error(message="请求体为空", code=400)

        ts_codes = data.get("ts_codes")
        if not ts_codes or not isinstance(ts_codes, list):
            return error(message="缺少参数：ts_codes（数组）", code=400)

        start_date = data.get("start_date")
        if not start_date:
            return error(message="缺少参数：start_date", code=400)

        end_date = data.get("end_date")
        freq = data.get("freq", "D")

        result = data_service.download_stock_data(
            ts_codes=ts_codes,
            start_date=start_date,
            end_date=end_date,
            freq=freq,
        )
        return success(data=result, message="下载完成")
    except Exception as e:
        return error(message=f"下载失败：{str(e)}", code=500)


@data_bp.route("/check_integrity", methods=["POST"])
def check_data_integrity():
    """
    🔴【v1.1 新增】检查指定股票在指定日期范围内的数据完整性。
    
    用途：
    - 回测前检查数据是否完整
    - 数据下载后验证数据质量
    - 确定需要补充下载的股票和日期范围
    
    Request Body:
        {
            "ts_codes": ["000001.SZ", "000002.SZ", "600519.SH"],
            "start_date": "20230101",
            "end_date": "20231231",
            "freq": "D"  // 可选，默认 D
        }
    
    Returns:
        {
            "code": 200,
            "data": {
                "complete": [
                    {
                        "ts_code": "000001.SZ",
                        "name": "平安银行",
                        "records": 243,
                        "expected_records": 243,
                        "data_range": ["20230101", "20231231"]
                    }
                ],
                "incomplete": [
                    {
                        "ts_code": "000002.SZ",
                        "name": "万科A",
                        "records": 180,
                        "expected_records": 243,
                        "missing_dates": 63,
                        "data_range": ["20230401", "20231231"]
                    }
                ],
                "missing": [
                    {
                        "ts_code": "600519.SH",
                        "name": "贵州茅台",
                        "records": 0,
                        "message": "无数据"
                    }
                ],
                "summary": {
                    "total": 3,
                    "complete": 1,
                    "incomplete": 1,
                    "missing": 1,
                    "completeness_rate": 33.3
                }
            },
            "message": "检查完成"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return error(message="请求体为空", code=400)

        ts_codes = data.get("ts_codes")
        if not ts_codes or not isinstance(ts_codes, list):
            return error(message="缺少参数：ts_codes（数组）", code=400)

        start_date = data.get("start_date")
        if not start_date:
            return error(message="缺少参数：start_date", code=400)

        end_date = data.get("end_date")
        if not end_date:
            return error(message="缺少参数：end_date", code=400)

        freq = data.get("freq", "D")

        result = data_service.check_data_integrity(
            ts_codes=ts_codes,
            start_date=start_date,
            end_date=end_date,
            freq=freq,
        )
        return success(data=result, message="检查完成")
    except Exception as e:
        return error(message=f"检查失败：{str(e)}", code=500)


@data_bp.route("/bars/<ts_code>", methods=["GET"])
def get_bar_data(ts_code: str):
    """
    获取单只股票的 K 线数据。

    Path Params:
        ts_code: 股票代码

    Query Params:
        start_date: 开始日期 YYYYMMDD（可选）
        end_date: 结束日期 YYYYMMDD（可选）
        freq: 数据频率 D/W/M，默认 D

    Returns:
        {
            "code": 200,
            "data": [K线列表],
            "message": "success"
        }
    """
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        freq = request.args.get("freq", "D")

        result = data_service.get_bar_data(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            freq=freq,
        )
        return success(data=result)
    except Exception as e:
        return error(message=f"查询失败：{str(e)}", code=500)




@data_bp.route("/stats", methods=["GET"])
def get_data_stats():
    """
    获取数据统计信息。

    Returns:
        {
            "code": 200,
            "data": {
                "total_stocks": 5138,
                "downloaded_stocks": 2568,
                "total_bars": 1234567,
                "date_range": { "start": "20200101", "end": "20260129" }
            },
            "message": "success"
        }
    """
    try:
        result = data_service.get_data_stats()
        return success(data=result)
    except Exception as e:
        return error(message=f"统计失败：{str(e)}", code=500)


@data_bp.route("/bars/<ts_code>", methods=["DELETE"])
def delete_bar_data(ts_code: str):
    """
    删除单只股票的 K 线数据。

    Path Params:
        ts_code: 股票代码

    Returns:
        {
            "code": 200,
            "data": { "deleted_records": 746 },
            "message": "删除成功"
        }
    """
    try:
        deleted = data_service.delete_bar_data(ts_code=ts_code)
        return success(data={"deleted_records": deleted}, message="删除成功")
    except Exception as e:
        return error(message=f"删除失败：{str(e)}", code=500)


# ========== 指数数据接口 ==========

@data_bp.route("/index/realtime", methods=["GET"])
def get_realtime_index():
    """
    获取实时指数数据（15分钟缓存，内存读取）
    
    Query Params:
        code: 指数代码（可选，如 000001），不传返回所有主要指数
    
    Returns:
        {
            "code": 200,
            "data": {
                "indices": {
                    "000001": {
                        "code": "000001",
                        "name": "上证指数",
                        "price": 3245.67,
                        "change": 12.34,
                        "change_pct": 0.38,
                        "open": 3234.56,
                        "high": 3267.89,
                        "low": 3223.45,
                        "volume": 234567890,
                        "update_time": "2026-01-30 14:45:00"
                    },
                    ...
                },
                "meta": {
                    "last_update": "2026-01-30 14:45:00",
                    "count": 6
                }
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
                'last_update': index_scheduler.last_update.strftime('%Y-%m-%d %H:%M:%S') 
                              if index_scheduler.last_update else None,
                'count': len(result)
            }
            return success(data={'indices': result, 'meta': meta})
            
    except Exception as e:
        return error(message=f"获取失败：{str(e)}", code=500)


@data_bp.route("/index/history/<ts_code>", methods=["GET"])
def get_index_history(ts_code: str):
    """
    获取指数历史数据（从数据库读取）
    
    Path Params:
        ts_code: 指数代码（如 000001.SH）
    
    Query Params:
        start_date: 开始日期 YYYYMMDD 或 YYYY-MM-DD（可选）
        end_date: 结束日期 YYYYMMDD 或 YYYY-MM-DD（可选）
        period: 快捷时间段（可选）：1d, 5d, 1m, 3m, 6m, 1y, 3y, 5y
        limit: 限制返回条数（可选）
    
    Returns:
        {
            "code": 200,
            "data": [
                {
                    "ts_code": "000001.SH",
                    "trade_date": "20260130",
                    "open": 3234.56,
                    "close": 3245.67,
                    "high": 3256.78,
                    "low": 3223.45,
                    "volume": 234567890
                },
                ...
            ],
            "meta": {
                "count": 250,
                "source": "database"
            }
        }
    """
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        period = request.args.get("period")
        limit = request.args.get("limit")
        
        if limit:
            limit = int(limit)
        
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
        
        # 查询数据库
        data = IndexDataService.get_daily_data(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        if not data:
            return error(message=f"未找到 {ts_code} 的历史数据", code=404)
        
        result = {
            'data': data,
            'meta': {
                'count': len(data),
                'source': 'database'
            }
        }
        return success(data=result)
        
    except Exception as e:
        return error(message=f"获取失败：{str(e)}", code=500)


@data_bp.route("/index/stats", methods=["GET"])
def get_index_stats():
    """
    获取指数数据统计信息
    
    Returns:
        {
            "code": 200,
            "data": {
                "000001.SH": {
                    "name": "上证指数",
                    "count": 731,
                    "latest_date": "20260130"
                },
                ...
            }
        }
    """
    try:
        stats = IndexDataService.get_stats()
        return success(data=stats)
    except Exception as e:
        return error(message=f"获取统计失败：{str(e)}", code=500)


@data_bp.route("/market/overview", methods=["GET"])
def get_market_overview():
    """
    🆕【v1.2 新增】获取市场概览（轻量级接口）
    
    一次请求获取：
    1. 主要指数数据（6个）
    2. 涨幅榜TOP20
    3. 跌幅榜TOP20
    4. 市场统计
    
    Returns:
        {
            "code": 200,
            "data": {
                "indexes": [指数数据],
                "top_gainers": [涨幅榜],
                "top_losers": [跌幅榜],
                "market_stats": {统计数据}
            }
        }
    """
    try:
        from models.stock import Stock
        from models.bar_data import BarData
        from sqlalchemy import func
        
        # 1. 获取主要指数数据（6个）
        indexes = []
        index_stats = IndexDataService.get_stats()
        
        for ts_code, info in index_stats.items():
            # 获取最新2条数据计算涨跌
            history = IndexDataService.get_daily_data(ts_code=ts_code, limit=2)
            
            if len(history) >= 2:
                latest = history[-1]
                previous = history[-2]
                
                change = latest['close'] - previous['close']
                pct_chg = (change / previous['close']) * 100
                
                indexes.append({
                    'ts_code': ts_code,
                    'name': info['name'],
                    'trade_date': latest['trade_date'],
                    'close': latest['close'],
                    'open': latest['open'],
                    'high': latest['high'],
                    'low': latest['low'],
                    'pre_close': previous['close'],
                    'change': change,
                    'pct_chg': pct_chg,
                    'vol': latest['volume'],
                    'amount': latest['volume'] * latest['close'] if latest['volume'] else 0
                })
        
        # 2. 获取重点股票的涨跌幅（只获取有K线数据的）
        stocks = Stock.query.filter_by(stock_type='key').limit(100).all()
        
        stock_ranks = []
        for stock in stocks:
            try:
                # 获取最新2条K线
                bars = BarData.query.filter_by(ts_code=stock.ts_code)\
                    .order_by(BarData.trade_date.desc())\
                    .limit(2)\
                    .all()
                
                if len(bars) >= 2:
                    latest = bars[0]
                    previous = bars[1]
                    
                    pct_chg = ((latest.close - previous.close) / previous.close) * 100
                    
                    stock_ranks.append({
                        'ts_code': stock.ts_code,
                        'name': stock.name,
                        'close': float(latest.close),
                        'pct_chg': float(pct_chg)
                    })
            except:
                continue
        
        # 排序获取涨跌幅榜
        top_gainers = sorted(stock_ranks, key=lambda x: x['pct_chg'], reverse=True)[:20]
        top_losers = sorted(stock_ranks, key=lambda x: x['pct_chg'])[:20]
        
        # 3. 计算市场统计
        market_stats = {
            'up_count': len([s for s in stock_ranks if s['pct_chg'] > 0]),
            'down_count': len([s for s in stock_ranks if s['pct_chg'] < 0]),
            'flat_count': len([s for s in stock_ranks if s['pct_chg'] == 0]),
            'limit_up_count': len([s for s in stock_ranks if s['pct_chg'] >= 9.9])
        }
        
        return success(data={
            'indexes': indexes,
            'top_gainers': top_gainers,
            'top_losers': top_losers,
            'market_stats': market_stats
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return error(message=f"获取市场概览失败：{str(e)}", code=500)


# ============== 交易日历接口 ==============

@data_bp.route("/trading-calendar/sync", methods=["POST"])
def sync_trading_calendar():
    """
    从TuShare同步交易日历数据

    Request Body:
        {
            "start_date": "20240101",  # 可选，默认20240101
            "end_date": "20271231"      # 可选，默认20271231
        }

    Returns:
        {
            "code": 200,
            "data": {
                "success": true,
                "total": 1000,
                "added": 1000,
                "updated": 0,
                "start_date": "20240101",
                "end_date": "20271231"
            },
            "message": "同步成功"
        }
    """
    try:
        from services.trading_calendar_service import trading_calendar_service

        # 获取参数
        req_data = request.get_json() or {}
        start_date = req_data.get("start_date", "20240101")
        end_date = req_data.get("end_date", "20271231")

        # 验证日期格式
        if not (len(start_date) == 8 and start_date.isdigit()):
            return error(message="start_date格式错误，应为YYYYMMDD", code=400)
        if not (len(end_date) == 8 and end_date.isdigit()):
            return error(message="end_date格式错误，应为YYYYMMDD", code=400)

        # 执行同步
        result = trading_calendar_service.sync_from_tushare(start_date, end_date)

        if result["success"]:
            return success(data=result, message=f"同步成功：新增{result['added']}条，更新{result['updated']}条")
        else:
            return error(message=result.get("error", "同步失败"), code=500)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return error(message=f"同步交易日历失败：{str(e)}", code=500)


@data_bp.route("/trading-calendar/check", methods=["GET"])
def check_trading_day():
    """
    检查指定日期是否为交易日

    Query Params:
        date: 日期 YYYYMMDD

    Returns:
        {
            "code": 200,
            "data": {
                "date": "20240101",
                "is_trading_day": false,
                "is_weekend": true,
                "is_holiday": false,
                "holiday_name": null
            },
            "message": "success"
        }
    """
    try:
        from services.trading_calendar_service import trading_calendar_service
        from models.trading_calendar import TradingCalendar

        date_str = request.args.get("date")
        if not date_str:
            return error(message="缺少date参数", code=400)

        # 查询数据库
        record = TradingCalendar.query.get(date_str)

        if not record:
            return error(message=f"未找到日期{date_str}的交易日历记录，请先同步数据", code=404)

        return success(data={
            "date": date_str,
            "is_trading_day": record.is_trading_day,
            "is_weekend": record.is_weekend,
            "is_holiday": record.is_holiday,
            "holiday_name": record.holiday_name
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return error(message=f"查询交易日失败：{str(e)}", code=500)


@data_bp.route("/trading-calendar/trading-days", methods=["GET"])
def get_trading_days():
    """
    获取指定日期范围内的所有交易日

    Query Params:
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD

    Returns:
        {
            "code": 200,
            "data": {
                "start_date": "20240101",
                "end_date": "20241231",
                "trading_days": ["20240101", "20240102", ...],
                "count": 244
            },
            "message": "success"
        }
    """
    try:
        from services.trading_calendar_service import trading_calendar_service

        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        if not start_date or not end_date:
            return error(message="缺少start_date或end_date参数", code=400)

        # 获取交易日列表
        trading_days = trading_calendar_service.get_trading_days(start_date, end_date)

        return success(data={
            "start_date": start_date,
            "end_date": end_date,
            "trading_days": trading_days,
            "count": len(trading_days)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return error(message=f"获取交易日列表失败：{str(e)}", code=500)


@data_bp.route("/trading-calendar/non-trading-days", methods=["GET"])
def get_non_trading_days():
    """
    获取指定日期范围内的所有非交易日

    Query Params:
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD

    Returns:
        {
            "code": 200,
            "data": {
                "start_date": "20240101",
                "end_date": "20241231",
                "non_trading_days": [
                    {"date": "20240101", "is_weekend": true, "is_holiday": false, "holiday_name": null},
                    {"date": "20240210", "is_weekend": false, "is_holiday": true, "holiday_name": "春节"}
                ],
                "count": 122
            },
            "message": "success"
        }
    """
    try:
        from services.trading_calendar_service import trading_calendar_service

        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        if not start_date or not end_date:
            return error(message="缺少start_date或end_date参数", code=400)

        # 获取非交易日列表
        non_trading_days = trading_calendar_service.get_non_trading_days(start_date, end_date)

        return success(data={
            "start_date": start_date,
            "end_date": end_date,
            "non_trading_days": non_trading_days,
            "count": len(non_trading_days)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return error(message=f"获取非交易日列表失败：{str(e)}", code=500)


@data_bp.route("/trading-calendar/stats", methods=["GET"])
def get_trading_calendar_stats():
    """
    获取交易日历统计信息

    Returns:
        {
            "code": 200,
            "data": {
                "total": 1000,
                "trading_days": 700,
                "non_trading_days": 300,
                "weekends": 260,
                "holidays": 40,
                "date_range": {
                    "earliest": "20240101",
                    "latest": "20271231"
                }
            },
            "message": "success"
        }
    """
    try:
        from services.trading_calendar_service import trading_calendar_service

        stats = trading_calendar_service.get_stats()

        return success(data=stats)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return error(message=f"获取统计信息失败：{str(e)}", code=500)


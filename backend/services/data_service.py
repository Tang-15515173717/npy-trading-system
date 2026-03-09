"""
数据服务 - StockQuant Pro
处理数据相关的业务逻辑：股票列表、下载、K线查询等。
"""
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
from sqlalchemy import or_, func
from models.stock import Stock
from models.bar_data import BarData
from utils.database import db
from utils.tushare_helper import TushareHelper
from utils.baostock_helper import BaostockHelper  # 🆕 Baostock - 完全免费，无限制
from config import config as app_config
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class DataService:
    """数据服务类"""

    def __init__(self):
        self.ts_helper = TushareHelper()
        # 🔴 Baostock连接有问题，暂时禁用
        # self.bs_helper = BaostockHelper()
        self.baostock_available = False  # 强制禁用Baostock
        
    def _check_baostock_available(self):
        """检查Baostock是否可用"""
        # 🔴 Baostock服务器当前不稳定（能建立TCP连接，但登录时服务响应卡死）
        # 优先使用TuShare，等Baostock服务恢复后再考虑启用
        if not self.baostock_available:
            return False
        
        # 可选：未来可添加动态检测逻辑
        try:
            from utils.baostock_helper import BaostockHelper
            helper = BaostockHelper()
            if helper._test_connection():
                helper.login()
                helper.logout()
                return True
        except Exception as e:
            logger.warning(f"Baostock连接检测失败: {e}")
            self.baostock_available = False
        return False

    def get_stock_list(
        self,
        keyword: Optional[str] = None,
        exchange: Optional[str] = None,
        industry: Optional[str] = None,
        list_status: Optional[str] = None,
        stock_type: Optional[str] = None,
        has_full_data: Optional[str] = None,
        has_factor_data: Optional[str] = None,  # 🆕 是否有因子数据
        page: int = 1,
        page_size: int = 50,
    ) -> Dict:
        """
        获取股票列表（支持搜索、筛选与分页）。

        Args:
            keyword: 搜索关键词（代码/名称模糊匹配）🆕
            exchange: 交易所代码（SSE/SZSE）
            industry: 行业分类
            list_status: 上市状态（L/D/P）
            stock_type: 股票类型（key=重点股票, normal=普通股票）🆕
            has_full_data: 是否有完整数据（true/false）🆕
            page: 页码（从1开始）
            page_size: 每页数量

        Returns:
            {
                "total": 总数,
                "page": 当前页,
                "page_size": 每页数量,
                "items": [股票字典列表]
            }
        """
        query = Stock.query

        # 🔍 搜索条件（优先级最高）
        if keyword:
            keyword = keyword.strip()
            query = query.filter(
                or_(
                    Stock.ts_code.like(f"%{keyword}%"),
                    Stock.name.like(f"%{keyword}%"),
                    Stock.symbol.like(f"%{keyword}%"),
                )
            )

        # 筛选条件
        if exchange:
            query = query.filter(Stock.exchange == exchange)
        if industry:
            query = query.filter(Stock.industry == industry)
        if list_status:
            query = query.filter(Stock.list_status == list_status)
        
        # 新增筛选条件
        if stock_type:
            query = query.filter(Stock.stock_type == stock_type)
        if has_full_data:
            # 转换字符串为布尔值
            has_data = has_full_data.lower() in ['true', '1', 'yes']
            query = query.filter(Stock.has_full_data == has_data)

        # 🆕 筛选有因子数据的股票
        if has_factor_data and has_factor_data.lower() in ['true', '1', 'yes']:
            # 子查询：有因子数据的股票代码
            from models.factor_data import FactorData
            stocks_with_factor = db.session.query(FactorData.ts_code).distinct().subquery()
            query = query.filter(Stock.ts_code.in_(stocks_with_factor))

        # 总数
        total = query.count()

        # 分页
        offset = (page - 1) * page_size
        stocks = query.offset(offset).limit(page_size).all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [stock.to_dict() for stock in stocks],
        }

    def search_stocks(self, keyword: str, limit: int = 10) -> List[Dict]:
        """
        搜索股票（按代码或名称模糊匹配）。

        Args:
            keyword: 搜索关键词
            limit: 返回数量

        Returns:
            股票字典列表
        """
        stocks = (
            Stock.query.filter(
                or_(
                    Stock.ts_code.like(f"%{keyword}%"),
                    Stock.name.like(f"%{keyword}%"),
                    Stock.symbol.like(f"%{keyword}%"),
                )
            )
            .limit(limit)
            .all()
        )
        return [stock.to_dict() for stock in stocks]

    def sync_stock_list_from_tushare(self) -> Dict:
        """
        从 TuShare 同步股票列表到数据库。

        Returns:
            { "success_count": 成功数, "fail_count": 失败数, "total": 总数 }
        """
        if not self.ts_helper.is_available():
            raise Exception("TuShare 不可用，请配置 TUSHARE_TOKEN")

        df = self.ts_helper.get_stock_basic()
        if df is None or len(df) == 0:
            return {"success_count": 0, "fail_count": 0, "total": 0}

        success_count = 0
        fail_count = 0
        for _, row in df.iterrows():
            try:
                stock = Stock.query.filter_by(ts_code=row["ts_code"]).first()
                if stock is None:
                    stock = Stock(ts_code=row["ts_code"])
                stock.symbol = row.get("symbol", "")
                stock.name = row.get("name", "")
                stock.area = row.get("area")
                stock.industry = row.get("industry")
                stock.market = row.get("market")
                stock.exchange = row.get("exchange", "")
                stock.list_date = row.get("list_date")
                stock.list_status = row.get("list_status", "L")
                stock.updated_at = datetime.utcnow()
                db.session.add(stock)
                success_count += 1
            except Exception as e:
                print(f"插入 {row.get('ts_code')} 失败：{e}")
                fail_count += 1

        db.session.commit()
        return {"success_count": success_count, "fail_count": fail_count, "total": len(df)}

    def download_stock_data(
        self,
        ts_codes: List[str],
        start_date: str,
        end_date: Optional[str] = None,
        freq: str = "D",
        data_source: str = "auto",  # 🔴 改为auto，自动选择可用数据源
    ) -> Dict:
        """
        批量下载股票 K 线数据（写入数据库），支持增量下载，自动切换数据源。
        
        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            freq: 频率 (D-日线, W-周线, M-月线)
            data_source: 数据源 ("auto"-自动选择, "baostock"-Baostock优先, "tushare"-TuShare)
        
        Returns:
            Dict with success_count, fail_count, total, failed_stocks, stored_records
        """
        # 自动选择数据源
        if data_source == "auto":
            if self._check_baostock_available():
                data_source = "baostock"
                logger.info("✅ 使用Baostock数据源（免费无限制）")
            else:
                data_source = "tushare"
                logger.info("⚠️ Baostock不可用，使用TuShare（有限制）")
        
        # 根据数据源选择调用不同的下载方法
        if data_source.lower() == "baostock":
            try:
                return self._download_with_baostock(ts_codes, start_date, end_date, freq)
            except (TimeoutError, Exception) as e:
                logger.error(f"❌ Baostock下载失败: {e}，切换到TuShare")
                self.baostock_available = False
                return self._download_with_tushare(ts_codes, start_date, end_date, freq)
        elif data_source.lower() == "tushare":
            return self._download_with_tushare(ts_codes, start_date, end_date, freq)
        else:
            raise ValueError(f"不支持的数据源: {data_source}")
    
    def _download_with_tushare(
        self,
        ts_codes: List[str],
        start_date: str,
        end_date: Optional[str] = None,
        freq: str = "D",
    ) -> Dict:
        """
        使用TuShare批量下载数据（高效版）
        
        根据TuShare文档: https://tushare.pro/document/2?doc_id=27
        - 支持多股票同时获取（逗号分隔）
        - 支持按日期获取全市场数据
        - 每分钟500次，每次6000条
        
        优化策略：使用批量获取，150只股票只需1-2秒
        """
        if not self.ts_helper.is_available():
            raise Exception("TuShare 不可用，请配置 TUSHARE_TOKEN")

        success_count = 0
        fail_count = 0
        failed_stocks = []
        total_stored_records = 0
        incremental_used = False

        logger.info(f"📡 TuShare批量下载: {len(ts_codes)}只股票, {start_date} - {end_date}")
        
        # 🚀 高效方式：使用批量获取（每批50只，一次请求）
        df = self.ts_helper.get_daily_batch(
            ts_codes=ts_codes,
            start_date=start_date,
            end_date=end_date,
            batch_size=50  # 每批50只
        )
        
        if df is None or len(df) == 0:
            # 批量获取无数据，可能是：
            # 1. 确实没数据（新股票）
            # 2. 数据已有（增量下载）
            # 先检查数据库是否已有数据，再决定是否回退
            logger.info(f"⚠️ 批量获取无数据，检查是否需要下载")
            has_existing = any([
                db.session.query(BarData).filter(
                    BarData.ts_code == code,
                    BarData.trade_date >= start_date,
                    BarData.trade_date <= (end_date or datetime.now().strftime("%Y%m%d"))
                ).first()
                for code in ts_codes
            ])
            if has_existing:
                logger.info(f"✅ 数据库已有数据，无需下载")
                return {
                    "success_count": len(ts_codes),
                    "fail_count": 0,
                    "total": len(ts_codes),
                    "failed_stocks": [],
                    "stored_records": 0,
                    "data_source": "TuShare API (existing)",
                    "incremental": True,
                }
            logger.warning(f"⚠️ 批量获取无数据丽数据库无记录，尝试逐只获取")
            return self._download_with_tushare_single(ts_codes, start_date, end_date, freq)
        
        logger.info(f"✅ 批量获取到 {len(df)} 条数据")
        
        # 按股票分组处理
        got_codes = set(df['ts_code'].unique())
        
        for ts_code in ts_codes:
            try:
                stock_df = df[df['ts_code'] == ts_code]
                
                # 检查增量：跳过已有数据
                existing_max_date = db.session.query(
                    func.max(BarData.trade_date)
                ).filter(
                    BarData.ts_code == ts_code,
                    BarData.freq == freq
                ).scalar()
                
                # 如果TuShare没有返回数据，检查数据库是否已有最新数据
                if stock_df.empty:
                    # 检查数据库是否已有该日期的数据
                    has_data = db.session.query(BarData).filter(
                        BarData.ts_code == ts_code,
                        BarData.trade_date == end_date,
                        BarData.freq == freq
                    ).first() is not None
                    
                    if has_data:
                        # 数据库已有数据，算成功
                        success_count += 1
                        incremental_used = True
                    else:
                        # 数据库没有数据，TuShare也没有数据，算失败
                        fail_count += 1
                        failed_stocks.append(ts_code)
                    continue
                
                records_inserted = 0
                for _, row in stock_df.iterrows():
                    trade_date = row['trade_date']
                    
                    # 增量检查
                    if existing_max_date and trade_date <= existing_max_date:
                        incremental_used = True
                        continue
                    
                    bar = BarData.query.filter_by(
                        ts_code=ts_code,
                        trade_date=trade_date,
                        freq=freq,
                    ).first()
                    if bar is None:
                        bar = BarData(ts_code=ts_code, trade_date=trade_date, freq=freq)
                    bar.open = row.get("open")
                    bar.high = row.get("high")
                    bar.low = row.get("low")
                    bar.close = row.get("close")
                    bar.pre_close = row.get("pre_close")
                    bar.change = row.get("change")
                    bar.pct_chg = row.get("pct_chg")
                    bar.vol = row.get("vol")
                    bar.amount = row.get("amount")
                    db.session.add(bar)
                    records_inserted += 1
                
                if records_inserted > 0:
                    total_stored_records += records_inserted
                success_count += 1
                
            except Exception as e:
                logger.error(f"处理 {ts_code} 失败: {e}")
                fail_count += 1
                failed_stocks.append(ts_code)
        
        db.session.commit()
        logger.info(f"✅ 下载完成: {success_count}成功, {fail_count}失败, 存储{total_stored_records}条")
        
        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "total": len(ts_codes),
            "failed_stocks": failed_stocks,
            "stored_records": total_stored_records,
            "data_source": "TuShare API (批量)",
            "incremental": incremental_used,
        }
    
    def _download_with_tushare_single(
        self,
        ts_codes: List[str],
        start_date: str,
        end_date: Optional[str] = None,
        freq: str = "D",
    ) -> Dict:
        """逐只股票下载（回退方案）"""
        success_count = 0
        fail_count = 0
        failed_stocks = []
        total_stored_records = 0
        incremental_used = False
        
        for idx, ts_code in enumerate(ts_codes, 1):
            try:
                # 🔥 限流处理：每秒1次，避免超过TuShare每分钟50次的限制
                if idx > 1:
                    import time
                    time.sleep(1.2)  # 每次间隔1.2秒，确保不超过50次/分钟
                
                df = self.ts_helper.get_daily_data(ts_code, start_date, end_date)
                
                if df is None or len(df) == 0:
                    fail_count += 1
                    failed_stocks.append(ts_code)
                    continue

                # 插入数据库
                records_inserted = 0
                for _, row in df.iterrows():
                    bar = BarData.query.filter_by(
                        ts_code=ts_code,
                        trade_date=row["trade_date"],
                        freq=freq,
                    ).first()
                    if bar is None:
                        bar = BarData(ts_code=ts_code, trade_date=row["trade_date"], freq=freq)
                    bar.open = row.get("open")
                    bar.high = row.get("high")
                    bar.low = row.get("low")
                    bar.close = row.get("close")
                    bar.pre_close = row.get("pre_close")
                    bar.change = row.get("change")
                    bar.pct_chg = row.get("pct_chg")
                    bar.vol = row.get("vol")
                    bar.amount = row.get("amount")
                    db.session.add(bar)
                    records_inserted += 1

                db.session.commit()
                total_stored_records += records_inserted
                success_count += 1
                print(f"✅ {ts_code} 下载成功，存储 {records_inserted} 条记录")
            except Exception as e:
                print(f"❌ 下载 {ts_code} 失败：{e}")
                db.session.rollback()
                fail_count += 1
                failed_stocks.append(ts_code)

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "total": len(ts_codes),
            "failed_stocks": failed_stocks,
            "stored_records": total_stored_records,
            "data_source": "TuShare API",
            "incremental": incremental_used,
        }
    
    def _download_with_baostock(
        self,
        ts_codes: List[str],
        start_date: str,
        end_date: Optional[str] = None,
        freq: str = "D",
    ) -> Dict:
        """
        使用Baostock下载数据（完全免费，无限制！）⭐
        
        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期 YYYYMMDD 或 YYYY-MM-DD
            end_date: 结束日期 YYYYMMDD 或 YYYY-MM-DD
            freq: 数据频率（目前只支持D）
            
        Returns:
            下载结果字典
        """
        if freq != "D":
            logger.warning(f"Baostock暂只支持日线数据，freq={freq}将被忽略")
        
        success_count = 0
        fail_count = 0
        failed_stocks = []
        skipped_stocks = []  # 🆕 数据已是最新，无需下载的股票
        total_stored_records = 0
        incremental_used = False
        
        # 格式化日期（Baostock需要YYYY-MM-DD格式）
        def format_date(date_str: str) -> str:
            if not date_str:
                return datetime.now().strftime("%Y-%m-%d")
            if '-' in date_str:
                return date_str
            if len(date_str) == 8:
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            return date_str
        
        start_date_formatted = format_date(start_date)
        end_date_formatted = format_date(end_date) if end_date else datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"🚀 使用Baostock下载 {len(ts_codes)} 只股票数据: {start_date_formatted} ~ {end_date_formatted}")
        
        # 登录Baostock（使用上下文管理器，自动登出）
        with self.bs_helper as bs:
            for idx, ts_code in enumerate(ts_codes, 1):
                try:
                    # 增量下载逻辑
                    actual_start_date = start_date_formatted
                    existing_max_date = db.session.query(
                        func.max(BarData.trade_date)
                    ).filter(
                        BarData.ts_code == ts_code,
                        BarData.freq == freq
                    ).scalar()
                    
                    if existing_max_date:
                        # 已有数据，从最大日期的下一天开始下载
                        try:
                            from datetime import datetime, timedelta
                            max_date_obj = datetime.strptime(existing_max_date, '%Y%m%d')
                            next_date_obj = max_date_obj + timedelta(days=1)
                            actual_start_date = next_date_obj.strftime('%Y-%m-%d')
                            incremental_used = True
                            logger.debug(f"🔄 增量下载 {ts_code}：已有数据至 {existing_max_date}，从 {actual_start_date} 开始")
                        except Exception as e:
                            logger.warning(f"增量下载日期计算失败，使用原始日期：{e}")
                            actual_start_date = start_date_formatted
                        
                        # 如果计算出的开始日期晚于结束日期，说明数据已是最新
                        if actual_start_date > end_date_formatted:
                            logger.debug(f"✅ {ts_code} 数据已是最新，无需下载")
                            success_count += 1
                            continue
                    
                    # 🔄 从Baostock获取数据（带自动重试）
                    max_retries = 3  # 最多重试3次
                    retry_delay = 2  # 重试间隔2秒
                    df = None
                    
                    for retry in range(max_retries):
                        try:
                            if retry > 0:
                                import time
                                logger.info(f"🔄 {ts_code} 第{retry+1}次重试...")
                                time.sleep(retry_delay)
                            
                            logger.debug(f"📡 正在获取 {ts_code} 数据: {actual_start_date} ~ {end_date_formatted}")
                            df = bs.get_daily_data(
                                ts_code=ts_code,
                                start_date=actual_start_date,
                                end_date=end_date_formatted,
                                adjust="2"  # 前复权
                            )
                            
                            # 如果获取到数据，跳出重试循环
                            if df is not None and len(df) > 0:
                                if retry > 0:
                                    logger.info(f"✅ {ts_code} 第{retry+1}次重试成功！")
                                break
                                
                        except Exception as e:
                            logger.warning(f"⚠️ {ts_code} 第{retry+1}次尝试失败: {e}")
                            if retry == max_retries - 1:
                                logger.error(f"❌ {ts_code} {max_retries}次重试后仍然失败")
                    
                    # 检查最终结果
                    if df is None or len(df) == 0:
                        # 检查是否是因为日期超出范围（数据已是最新）
                        if existing_max_date and actual_start_date >= end_date_formatted:
                            logger.debug(f"✅ {ts_code} 数据已是最新（跳过）")
                            success_count += 1
                            skipped_stocks.append(ts_code)
                        else:
                            fail_count += 1
                            failed_stocks.append(ts_code)
                            logger.warning(f"⚠️ {ts_code} 在 {actual_start_date}~{end_date_formatted} 期间无数据（可能停牌或已退市）")
                        continue
                    
                    # 插入数据库
                    records_inserted = 0
                    for _, row in df.iterrows():
                        # 转换日期格式：YYYY-MM-DD -> YYYYMMDD
                        trade_date = row['date'].strftime('%Y%m%d') if hasattr(row['date'], 'strftime') else row['date'].replace('-', '')
                        
                        bar = BarData.query.filter_by(
                            ts_code=ts_code,
                            trade_date=trade_date,
                            freq=freq,
                        ).first()
                        if bar is None:
                            bar = BarData(ts_code=ts_code, trade_date=trade_date, freq=freq)
                        
                        bar.open = float(row['open']) if row['open'] else None
                        bar.high = float(row['high']) if row['high'] else None
                        bar.low = float(row['low']) if row['low'] else None
                        bar.close = float(row['close']) if row['close'] else None
                        bar.vol = float(row['volume']) if row['volume'] else None
                        bar.amount = float(row['amount']) if row['amount'] else None
                        # Baostock不提供这些字段，设为None
                        bar.pre_close = None
                        bar.change = None
                        bar.pct_chg = None
                        
                        db.session.add(bar)
                        records_inserted += 1
                    
                    db.session.commit()
                    total_stored_records += records_inserted
                    success_count += 1
                    
                    if idx % 10 == 0:  # 每10只输出一次进度
                        logger.info(f"📊 进度: {idx}/{len(ts_codes)} ({success_count} 成功, {fail_count} 失败)")
                    
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    logger.error(f"❌ 下载 {ts_code} 处理失败（已重试{max_retries}次）：{e}")
                    logger.debug(f"详细错误:\n{error_detail}")
                    db.session.rollback()
                    fail_count += 1
                    failed_stocks.append(ts_code)
        
        logger.info(f"✅ Baostock下载完成: {success_count}/{len(ts_codes)} 成功, 存储 {total_stored_records} 条记录")
        if skipped_stocks:
            logger.info(f"📋 {len(skipped_stocks)} 只股票数据已是最新，无需下载")
        
        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "total": len(ts_codes),
            "failed_stocks": failed_stocks,
            "skipped_stocks": skipped_stocks,  # 🆕 跳过的股票列表
            "stored_records": total_stored_records,
            "data_source": "Baostock (免费无限制)",
            "incremental": incremental_used,
        }

    def get_bar_data(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        freq: str = "D",
    ) -> List[Dict]:
        """
        获取 K 线数据。

        Args:
            ts_code: 股票代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            freq: 数据频率

        Returns:
            K 线数据列表
        """
        query = BarData.query.filter_by(ts_code=ts_code, freq=freq)
        if start_date:
            query = query.filter(BarData.trade_date >= start_date)
        if end_date:
            query = query.filter(BarData.trade_date <= end_date)

        bars = query.order_by(BarData.trade_date).all()
        return [bar.to_dict() for bar in bars]

    def get_data_stats(self) -> Dict:
        """
        获取数据统计信息。

        Returns:
            { "total_stocks": 总股票数, "downloaded_stocks": 已下载股票数, "total_bars": 总K线数, ... }
        """
        total_stocks = Stock.query.count()
        downloaded_stocks = db.session.query(BarData.ts_code).distinct().count()
        total_bars = BarData.query.count()

        # 日期范围
        date_range_query = db.session.query(
            func.min(BarData.trade_date), func.max(BarData.trade_date)
        ).first()
        date_range = {
            "start": date_range_query[0] if date_range_query[0] else None,
            "end": date_range_query[1] if date_range_query[1] else None,
        }

        return {
            "total_stocks": total_stocks,
            "downloaded_stocks": downloaded_stocks,
            "total_bars": total_bars,
            "date_range": date_range,
        }

    def delete_bar_data(self, ts_code: str) -> int:
        """
        删除单只股票的 K 线数据。

        Args:
            ts_code: 股票代码

        Returns:
            删除的记录数
        """
        deleted = BarData.query.filter_by(ts_code=ts_code).delete()
        db.session.commit()
        return deleted

    def check_data_integrity(
        self,
        ts_codes: List[str],
        start_date: str,
        end_date: str,
        freq: str = "D",
    ) -> Dict:
        """
        🔴 v1.1 新增：检查指定股票在指定日期范围内的数据完整性。

        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            freq: 数据频率（D/W/M）

        Returns:
            {
                "complete": [完整的股票列表],
                "incomplete": [不完整的股票列表],
                "missing": [无数据的股票列表],
                "summary": {统计信息}
            }
        """
        from datetime import datetime, timedelta

        complete = []
        incomplete = []
        missing = []

        # 计算预期的交易日数量（粗略估算）
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        total_days = (end_dt - start_dt).days + 1
        # 假设交易日约占总天数的 70%（去除周末和节假日）
        expected_records = int(total_days * 0.7) if freq == "D" else total_days

        for ts_code in ts_codes:
            try:
                # 查询该股票的数据
                records = BarData.query.filter(
                    BarData.ts_code == ts_code,
                    BarData.freq == freq,
                    BarData.trade_date >= start_date,
                    BarData.trade_date <= end_date
                ).order_by(BarData.trade_date).all()

                actual_count = len(records)

                # 获取股票名称
                stock = Stock.query.filter_by(ts_code=ts_code).first()
                stock_name = stock.name if stock else "未知"

                if actual_count == 0:
                    # 完全无数据
                    missing.append({
                        "ts_code": ts_code,
                        "name": stock_name,
                        "records": 0,
                        "message": "无数据"
                    })
                elif actual_count < expected_records * 0.8:  # 少于预期的80%认为不完整
                    # 数据不完整
                    data_range = [records[0].trade_date, records[-1].trade_date] if records else []
                    missing_dates = expected_records - actual_count
                    incomplete.append({
                        "ts_code": ts_code,
                        "name": stock_name,
                        "records": actual_count,
                        "expected_records": expected_records,
                        "missing_dates": missing_dates,
                        "data_range": data_range
                    })
                else:
                    # 数据完整
                    data_range = [records[0].trade_date, records[-1].trade_date] if records else []
                    complete.append({
                        "ts_code": ts_code,
                        "name": stock_name,
                        "records": actual_count,
                        "expected_records": expected_records,
                        "data_range": data_range
                    })
            except Exception as e:
                print(f"检查 {ts_code} 数据完整性失败：{e}")
                missing.append({
                    "ts_code": ts_code,
                    "name": "检查失败",
                    "records": 0,
                    "message": str(e)
                })

        # 统计信息
        total = len(ts_codes)
        completeness_rate = (len(complete) / total * 100) if total > 0 else 0

        return {
            "complete": complete,
            "incomplete": incomplete,
            "missing": missing,
            "summary": {
                "total": total,
                "complete": len(complete),
                "incomplete": len(incomplete),
                "missing": len(missing),
                "completeness_rate": round(completeness_rate, 2)
            }
        }

    def get_market_overview(self) -> Dict:
        """
        🔴【轻量级接口】获取大盘概览数据（一次性返回所有数据）
        
        优化点：
        - 单次查询，批量处理
        - 减少数据库查询次数
        - 前端从100+请求 → 1请求
        
        Returns:
            {
                "indexes": [...],        # 主要指数
                "top_gainers": [...],    # 涨幅榜 TOP20
                "top_losers": [...],     # 跌幅榜 TOP20
                "market_stats": {...}    # 市场统计
            }
        """
        from models.index_data import IndexData
        
        result = {
            "indexes": [],
            "top_gainers": [],
            "top_losers": [],
            "market_stats": {
                "total": 0,
                "up_count": 0,
                "down_count": 0,
                "flat_count": 0,
                "limit_up_count": 0,
                "limit_down_count": 0
            }
        }
        
        try:
            # 1. 获取主要指数的最新数据
            main_indexes = [
                '000001.SH',  # 上证指数
                '000300.SH',  # 沪深300
                '399001.SZ',  # 深证成指
                '399006.SZ',  # 创业板指
                '000688.SH',  # 科创50
                '000016.SH'   # 上证50
            ]
            
            for ts_code in main_indexes:
                # 获取最新2条数据（计算涨跌）
                latest_data = db.session.query(IndexData).filter(
                    IndexData.ts_code == ts_code
                ).order_by(IndexData.trade_date.desc()).limit(2).all()
                
                if len(latest_data) >= 2:
                    latest = latest_data[0]
                    previous = latest_data[1]
                    
                    change = latest.close - previous.close
                    pct_chg = (change / previous.close) * 100 if previous.close != 0 else 0
                    
                    result["indexes"].append({
                        "ts_code": ts_code,
                        "name": latest.name,
                        "close": latest.close,
                        "change": round(change, 2),
                        "pct_chg": round(pct_chg, 2),
                        "volume": latest.volume,
                        "amount": latest.volume * latest.close  # 估算成交额
                    })
            
            # 2. 获取所有有K线数据的股票（批量查询）
            # 使用子查询获取每只股票最新2条数据
            from sqlalchemy import and_
            
            # 获取所有有数据的股票代码
            stock_codes = db.session.query(BarData.ts_code).distinct().all()
            stock_codes = [code[0] for code in stock_codes]
            
            # 批量获取每只股票的最新2条数据并计算涨跌幅
            stock_changes = []
            for ts_code in stock_codes[:200]:  # 限制处理数量，避免太慢
                try:
                    latest_bars = db.session.query(BarData).filter(
                        BarData.ts_code == ts_code
                    ).order_by(BarData.trade_date.desc()).limit(2).all()
                    
                    if len(latest_bars) >= 2:
                        latest = latest_bars[0]
                        previous = latest_bars[1]
                        
                        pct_chg = ((latest.close - previous.close) / previous.close) * 100 if previous.close != 0 else 0
                        
                        # 获取股票名称
                        stock = Stock.query.filter_by(ts_code=ts_code).first()
                        name = stock.name if stock else ts_code
                        
                        stock_changes.append({
                            "ts_code": ts_code,
                            "name": name,
                            "close": latest.close,
                            "pct_chg": round(pct_chg, 2)
                        })
                        
                        # 统计市场数据
                        result["market_stats"]["total"] += 1
                        if pct_chg > 0:
                            result["market_stats"]["up_count"] += 1
                        elif pct_chg < 0:
                            result["market_stats"]["down_count"] += 1
                        else:
                            result["market_stats"]["flat_count"] += 1
                        
                        if pct_chg >= 9.9:
                            result["market_stats"]["limit_up_count"] += 1
                        elif pct_chg <= -9.9:
                            result["market_stats"]["limit_down_count"] += 1
                            
                except Exception as e:
                    print(f"处理{ts_code}失败：{e}")
                    continue
            
            # 3. 排序获取涨跌幅榜
            result["top_gainers"] = sorted(stock_changes, key=lambda x: x["pct_chg"], reverse=True)[:20]
            result["top_losers"] = sorted(stock_changes, key=lambda x: x["pct_chg"])[:20]
            
            print(f"✅ 大盘概览：{len(result['indexes'])}个指数，{result['market_stats']['total']}只股票")
            
        except Exception as e:
            print(f"❌ 获取大盘概览失败：{e}")
            import traceback
            traceback.print_exc()
        
        return result

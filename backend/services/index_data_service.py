"""
指数数据服务
处理指数日K线的下载、保存和查询
"""
from models.index_data import IndexDaily
from utils.database import db
from datetime import datetime, timedelta
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class IndexDataService:
    """指数数据服务"""
    
    # 主要指数列表
    MAIN_INDICES = {
        '000001.SH': '上证指数',
        '399001.SZ': '深证成指',
        '000300.SH': '沪深300',
        '000016.SH': '上证50',
        '399006.SZ': '创业板指',
        '000688.SH': '科创50',
    }
    
    @staticmethod
    def _convert_to_ak_symbol(ts_code: str) -> str:
        """
        转换代码格式：000001.SH → sh000001
        
        Args:
            ts_code: 标准代码
        
        Returns:
            AKShare代码
        """
        if ts_code.endswith('.SH'):
            return 'sh' + ts_code.replace('.SH', '')
        elif ts_code.endswith('.SZ'):
            return 'sz' + ts_code.replace('.SZ', '')
        else:
            return ts_code
    
    @staticmethod
    def save_daily_data(
        ts_code: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None
    ) -> int:
        """
        下载并保存指数日K线到数据库
        
        Args:
            ts_code: 指数代码 000001.SH
            start_date: 开始日期 20260101 或 2026-01-01
            end_date: 结束日期 20260130 或 2026-01-30
        
        Returns:
            保存的记录数
        """
        from flask import current_app
        
        try:
            import akshare as ak
            
            # 转换代码格式
            ak_symbol = IndexDataService._convert_to_ak_symbol(ts_code)
            
            logger.info(f"下载 {ts_code} 日K线数据...")
            
            # 获取数据
            df = ak.stock_zh_index_daily(symbol=ak_symbol)
            
            if df is None or df.empty:
                logger.warning(f"{ts_code} 未获取到数据")
                return 0
            
            # 筛选日期
            if start_date:
                start_date_clean = start_date.replace('-', '')
                df['date'] = df['date'].astype(str)
                df = df[df['date'] >= start_date_clean]
            
            if end_date:
                end_date_clean = end_date.replace('-', '')
                df = df[df['date'] <= end_date_clean]
            
            if df.empty:
                logger.warning(f"{ts_code} 指定日期范围内无数据")
                return 0
            
            # 批量插入（需要在application context中）
            saved_count = 0
            try:
                for _, row in df.iterrows():
                    try:
                        # 检查是否已存在
                        exists = IndexDaily.query.filter_by(
                            ts_code=ts_code,
                            trade_date=str(row['date'])
                        ).first()
                        
                        if exists:
                            # 更新现有记录
                            exists.open = float(row['open'])
                            exists.close = float(row['close'])
                            exists.high = float(row['high'])
                            exists.low = float(row['low'])
                            exists.volume = int(row['volume'])
                        else:
                            # 插入新记录
                            record = IndexDaily(
                                ts_code=ts_code,
                                trade_date=str(row['date']),
                                open=float(row['open']),
                                close=float(row['close']),
                                high=float(row['high']),
                                low=float(row['low']),
                                volume=int(row['volume'])
                            )
                            db.session.add(record)
                            saved_count += 1
                    
                    except Exception as e:
                        logger.error(f"保存单条记录失败：{e}")
                        continue
                
                db.session.commit()
                logger.info(f"✅ {ts_code} 保存了 {saved_count} 条新记录")
                return saved_count
            except Exception as e:
                db.session.rollback()
                raise e
            
        except ImportError:
            logger.error("❌ AKShare 未安装，请执行：pip install akshare")
            return 0
        except Exception as e:
            logger.error(f"❌ 保存 {ts_code} 失败：{e}")
            return 0
    
    @staticmethod
    def get_daily_data(
        ts_code: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[dict]:
        """
        从数据库获取指数日K线数据
        
        Args:
            ts_code: 指数代码
            start_date: 开始日期 20260101
            end_date: 结束日期 20260130
            limit: 限制返回条数（从最新日期开始取）
        
        Returns:
            日K线数据列表（按日期升序）
        """
        try:
            query = IndexDaily.query.filter_by(ts_code=ts_code)
            
            if start_date:
                start_date_clean = start_date.replace('-', '')
                query = query.filter(IndexDaily.trade_date >= start_date_clean)
            
            if end_date:
                end_date_clean = end_date.replace('-', '')
                query = query.filter(IndexDaily.trade_date <= end_date_clean)
            
            # 如果有limit，先降序取最新的N条
            if limit:
                query = query.order_by(IndexDaily.trade_date.desc()).limit(limit)
                records = query.all()
                # 然后反转为升序返回
                records.reverse()
            else:
                # 没有limit，直接升序
                query = query.order_by(IndexDaily.trade_date)
                records = query.all()
            
            return [r.to_dict() for r in records]
        
        except Exception as e:
            logger.error(f"查询 {ts_code} 失败：{e}")
            return []
    
    @staticmethod
    def update_all_indices(start_date: Optional[str] = None, end_date: Optional[str] = None):
        """
        更新所有主要指数（每天收盘后执行）
        
        Args:
            start_date: 开始日期（默认今天）
            end_date: 结束日期（默认今天）
        """
        if not start_date:
            start_date = datetime.now().strftime('%Y%m%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        
        logger.info(f"\n{'='*80}")
        logger.info(f"📦 批量更新指数日K线数据")
        logger.info(f"   时间范围：{start_date} - {end_date}")
        logger.info(f"   指数数量：{len(IndexDataService.MAIN_INDICES)}")
        logger.info(f"{'='*80}")
        
        total_saved = 0
        for i, (ts_code, name) in enumerate(IndexDataService.MAIN_INDICES.items(), 1):
            logger.info(f"\n[{i}/{len(IndexDataService.MAIN_INDICES)}] {name} ({ts_code})")
            count = IndexDataService.save_daily_data(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            total_saved += count
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🎉 批量更新完成！共保存 {total_saved} 条新记录")
        logger.info(f"{'='*80}\n")
        
        return total_saved
    
    @staticmethod
    def get_latest_trade_date(ts_code: str) -> Optional[str]:
        """
        获取指定指数最新的交易日期
        
        Returns:
            交易日期字符串 20260130，如果没有数据返回None
        """
        try:
            record = IndexDaily.query.filter_by(ts_code=ts_code)\
                .order_by(IndexDaily.trade_date.desc())\
                .first()
            return record.trade_date if record else None
        except Exception as e:
            logger.error(f"查询最新交易日失败：{e}")
            return None
    
    @staticmethod
    def get_stats():
        """
        获取指数数据统计信息
        
        Returns:
            统计字典
        """
        try:
            stats = {}
            for ts_code, name in IndexDataService.MAIN_INDICES.items():
                count = IndexDaily.query.filter_by(ts_code=ts_code).count()
                latest_date = IndexDataService.get_latest_trade_date(ts_code)
                stats[ts_code] = {
                    'name': name,
                    'count': count,
                    'latest_date': latest_date
                }
            return stats
        except Exception as e:
            logger.error(f"获取统计信息失败：{e}")
            return {}


if __name__ == "__main__":
    # 测试
    print("📊 测试指数数据服务\n")
    
    # 下载近7天数据
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
    
    print(f"下载上证指数 {start_date} - {end_date} 数据")
    count = IndexDataService.save_daily_data('000001.SH', start_date, end_date)
    print(f"保存了 {count} 条记录\n")
    
    # 查询数据
    print("查询最近5天数据：")
    data = IndexDataService.get_daily_data('000001.SH', limit=5)
    for item in data:
        print(f"  {item['trade_date']}: 收盘 {item['close']:.2f}")

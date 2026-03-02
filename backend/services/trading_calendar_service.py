"""
交易日历服务 - StockQuant Pro
负责从TuShare拉取交易日历数据
"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from utils.database import db
from models.trading_calendar import TradingCalendar

logger = logging.getLogger(__name__)


class TradingCalendarService:
    """交易日历服务"""

    def __init__(self):
        # 获取TuShare Token
        self.tushare_token = os.getenv("TUSHARE_TOKEN")

        # 尝试从Application读取
        if not self.tushare_token:
            try:
                import sys
                sys.path.insert(0, '../..')
                from Application import TUSHARE_TOKEN
                self.tushare_token = TUSHARE_TOKEN
            except Exception:
                pass

        # 尝试从settings读取
        if not self.tushare_token:
            try:
                from config.settings import settings
                self.tushare_token = getattr(settings, 'TUSHARE_TOKEN', None)
            except Exception:
                pass

        if not self.tushare_token:
            logger.warning("⚠️ 未找到TuShare Token，无法同步交易日历")
            self.ts = None
        else:
            try:
                import tushare as ts
                self.ts = ts.pro_api(token=self.tushare_token)
                logger.info(f"✅ TuShare初始化成功")
            except Exception as e:
                logger.error(f"❌ TuShare初始化失败: {e}")
                self.ts = None

    def sync_from_tushare(self, start_date: str = "20240101", end_date: str = "20271231") -> Dict:
        """
        从TuShare同步交易日历数据

        Args:
            start_date: 开始日期 YYYYMMDD，默认 20240101
            end_date: 结束日期 YYYYMMDD，默认 20271231

        Returns:
            {
                "success": True/False,
                "total": 总记录数,
                "added": 新增记录数,
                "updated": 更新记录数,
                "start_date": start_date,
                "end_date": end_date,
                "error": 错误信息
            }
        """
        result = {
            "success": False,
            "total": 0,
            "added": 0,
            "updated": 0,
            "start_date": start_date,
            "end_date": end_date,
            "error": None
        }

        if not self.ts:
            result["error"] = "TuShare未初始化，请检查Token配置"
            return result

        try:
            logger.info(f"📡 开始同步交易日历: {start_date} ~ {end_date}")

            # 调用TuShare接口
            df = self.ts.trade_cal(
                exchange='SSE',  # 上交所
                start_date=start_date,
                end_date=end_date,
                is_open='1'  # 1=只返回交易日，0=返回全部（我们用全部）
            )

            # 重新获取全部数据（包括非交易日）
            df = self.ts.trade_cal(
                exchange='SSE',
                start_date=start_date,
                end_date=end_date
            )

            if df is None or len(df) == 0:
                result["error"] = "未获取到数据"
                return result

            logger.info(f"📊 从TuShare获取到 {len(df)} 条交易日历数据")

            # 批量处理
            added = 0
            updated = 0

            for _, row in df.iterrows():
                cal_date = row['cal_date']
                is_open = row['is_open']  # 1=开市（交易日）, 0=休市

                # 判断是否是周末
                date_obj = datetime.strptime(cal_date, "%Y%m%d")
                is_weekend = date_obj.weekday() >= 5  # 5=周六, 6=周日

                # 判断是否是节假日（非交易日且非周末）
                is_holiday = (is_open == 0) and (not is_weekend)

                # 节假日名称（简单判断）
                holiday_name = None
                if is_holiday:
                    month = date_obj.month
                    day = date_obj.day
                    if month == 1 and day >= 1:
                        holiday_name = "元旦"
                    elif month == 2 or month == 1:
                        # 春节（简单判断，实际日期每年不同）
                        if 20 <= day <= 28 or (month == 2 and day <= 15):
                            holiday_name = "春节"
                    elif month == 4 and 4 <= day <= 6:
                        holiday_name = "清明节"
                    elif month == 5 and 1 <= day <= 3:
                        holiday_name = "劳动节"
                    elif month == 6:
                        holiday_name = "端午节"
                    elif month == 10 and 1 <= day <= 7:
                        holiday_name = "国庆节"
                    else:
                        holiday_name = "节假日"

                # 查找或创建记录
                record = TradingCalendar.query.get(cal_date)

                if record:
                    # 更新已有记录
                    updated += 1
                    record.is_trading_day = (is_open == 1)
                    record.is_weekend = is_weekend
                    record.is_holiday = is_holiday
                    record.holiday_name = holiday_name if is_holiday else None
                    record.exchange = 'SSE'
                    record.updated_at = datetime.utcnow()
                else:
                    # 创建新记录
                    added += 1
                    record = TradingCalendar(
                        cal_date=cal_date,
                        is_trading_day=(is_open == 1),
                        is_weekend=is_weekend,
                        is_holiday=is_holiday,
                        holiday_name=holiday_name if is_holiday else None,
                        exchange='SSE'
                    )
                    db.session.add(record)

            # 提交事务
            db.session.commit()

            result["success"] = True
            result["total"] = len(df)
            result["added"] = added
            result["updated"] = updated

            logger.info(f"✅ 交易日历同步完成: 总计{result['total']}条, 新增{added}条, 更新{updated}条")

            return result

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ 同步交易日历失败: {e}")
            result["error"] = str(e)
            return result

    def is_trading_day(self, cal_date: str) -> bool:
        """
        判断指定日期是否为交易日

        Args:
            cal_date: 日期 YYYYMMDD

        Returns:
            True=交易日, False=非交易日
        """
        try:
            record = TradingCalendar.query.get(cal_date)
            if record:
                return record.is_trading_day

            # 如果数据库中没有记录，返回None（未知）
            logger.warning(f"⚠️ 交易日历中没有记录: {cal_date}")
            return None
        except Exception as e:
            logger.error(f"❌ 查询交易日失败: {e}")
            return None

    def get_trading_days(self, start_date: str, end_date: str) -> List[str]:
        """
        获取指定日期范围内的所有交易日

        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            交易日列表 ["20240101", "20240102", ...]
        """
        try:
            records = TradingCalendar.query.filter(
                TradingCalendar.cal_date >= start_date,
                TradingCalendar.cal_date <= end_date,
                TradingCalendar.is_trading_day == True
            ).order_by(TradingCalendar.cal_date).all()

            return [r.cal_date for r in records]
        except Exception as e:
            logger.error(f"❌ 获取交易日列表失败: {e}")
            return []

    def get_non_trading_days(self, start_date: str, end_date: str) -> List[Dict]:
        """
        获取指定日期范围内的所有非交易日

        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            非交易日列表 [{"date": "20240101", "reason": "元旦"}, ...]
        """
        try:
            records = TradingCalendar.query.filter(
                TradingCalendar.cal_date >= start_date,
                TradingCalendar.cal_date <= end_date,
                TradingCalendar.is_trading_day == False
            ).order_by(TradingCalendar.cal_date).all()

            return [
                {
                    "date": r.cal_date,
                    "is_weekend": r.is_weekend,
                    "is_holiday": r.is_holiday,
                    "holiday_name": r.holiday_name
                }
                for r in records
            ]
        except Exception as e:
            logger.error(f"❌ 获取非交易日列表失败: {e}")
            return []

    def get_stats(self) -> Dict:
        """
        获取交易日历统计信息

        Returns:
            统计信息
        """
        try:
            total = TradingCalendar.query.count()
            trading_days = TradingCalendar.query.filter_by(is_trading_day=True).count()
            non_trading_days = total - trading_days
            weekends = TradingCalendar.query.filter_by(is_weekend=True).count()
            holidays = TradingCalendar.query.filter_by(is_holiday=True).count()

            # 获取日期范围
            earliest = db.session.query(
                db.func.min(TradingCalendar.cal_date)
            ).scalar()
            latest = db.session.query(
                db.func.max(TradingCalendar.cal_date)
            ).scalar()

            return {
                "total": total,
                "trading_days": trading_days,
                "non_trading_days": non_trading_days,
                "weekends": weekends,
                "holidays": holidays,
                "date_range": {
                    "earliest": earliest,
                    "latest": latest
                }
            }
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {}


# 单例
trading_calendar_service = TradingCalendarService()

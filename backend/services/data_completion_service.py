"""
数据补全服务 - 自动补全K线和因子数据
==========================================
通用逻辑：
1. 检查缺失的日期
2. 下载K线数据
3. 计算因子数据
4. 返回补全结果
"""
import logging
from typing import List, Dict
from datetime import datetime, timedelta
from models.bar_data import BarData
from models.factor_data import FactorData
from services.data_service import DataService
from services.factor_service import FactorService
from utils.database import db

logger = logging.getLogger(__name__)


class DataCompletionService:
    """数据补全服务"""
    
    def __init__(self):
        self.data_service = DataService()
        self.factor_service = FactorService()
    
    def ensure_data_ready(
        self, 
        stock_pool: List[str], 
        start_date: str, 
        end_date: str,
        skip_weekends: bool = True
    ) -> Dict:
        """
        确保指定期间的K线和因子数据都准备好
        
        Args:
            stock_pool: 股票池
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            skip_weekends: 是否跳过周末
            
        Returns:
            {
                "success": True/False,
                "dates_processed": [],
                "kline_result": {},
                "factor_result": {},
                "errors": []
            }
        """
        result = {
            "success": False,
            "dates_processed": [],
            "kline_result": {},
            "factor_result": {},
            "errors": []
        }
        
        try:
            # 1. 生成日期列表
            trade_dates = self._get_date_range(start_date, end_date, skip_weekends)
            logger.info(f"需要处理的日期: {len(trade_dates)}天 ({start_date} 至 {end_date})")
            
            if not trade_dates:
                result["success"] = True
                result["errors"].append("日期范围内无交易日")
                return result
            
            # 2. 检查并补全K线数据
            kline_dates_needed = self._check_missing_kline(stock_pool, trade_dates)
            if kline_dates_needed:
                logger.info(f"需要下载K线数据的日期: {len(kline_dates_needed)}天")
                kline_result = self._download_kline_batch(stock_pool, kline_dates_needed)
                result["kline_result"] = kline_result
                
                if kline_result.get("fail_count", 0) > 0:
                    # 提供更详细的错误信息
                    failed_stocks = kline_result.get("failed_stocks", [])
                    fail_count = kline_result.get("fail_count", 0)
                    success_count = kline_result.get("success_count", 0)
                    
                    # 只显示前5只失败的股票
                    sample_stocks = failed_stocks[:5]
                    stock_list = ', '.join(sample_stocks)
                    if len(failed_stocks) > 5:
                        stock_list += f"...等{len(failed_stocks)}只"
                    
                    error_msg = f"K线下载部分失败: {fail_count}只失败 / {fail_count + success_count}只总数 ({stock_list})"
                    result["errors"].append(error_msg)
            else:
                logger.info("K线数据已完整")
                result["kline_result"] = {"message": "K线数据已完整"}
            
            # 3. 检查并补全因子数据
            factor_dates_needed = self._check_missing_factors(stock_pool, trade_dates)
            if factor_dates_needed:
                logger.info(f"需要计算因子的日期: {len(factor_dates_needed)}天")
                factor_result = self._calculate_factors_batch(stock_pool, factor_dates_needed)
                result["factor_result"] = factor_result
                
                if factor_result.get("total_failed", 0) > 0:
                    # 提供更详细的错误信息
                    failed_count = factor_result.get("total_failed", 0)
                    success_count = factor_result.get("total_success", 0)
                    error_msg = f"因子计算部分失败: {failed_count}个失败 / {failed_count + success_count}个总数"
                    
                    # 如果有详细失败信息，添加日期信息（完整显示所有天数）
                    if factor_result.get("failed_details"):
                        failed_dates = [f"{d['date']}({d['count']}只)" for d in factor_result["failed_details"]]
                        error_msg += f"，涉及: {', '.join(failed_dates)}"
                    
                    result["errors"].append(error_msg)
            else:
                logger.info("因子数据已完整")
                result["factor_result"] = {"message": "因子数据已完整"}
            
            result["dates_processed"] = trade_dates
            result["success"] = len(result["errors"]) == 0
            
            return result
            
        except Exception as e:
            logger.error(f"数据补全失败: {e}")
            result["errors"].append(str(e))
            return result
    
    def _get_date_range(self, start_date: str, end_date: str, skip_weekends: bool) -> List[str]:
        """生成日期范围（可选跳过周末）"""
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")
        dates = []
        current = start
        
        while current <= end:
            if not skip_weekends or current.weekday() < 5:  # 周一到周五
                dates.append(current.strftime("%Y%m%d"))
            current += timedelta(days=1)
        
        return dates
    
    def _check_missing_kline(self, stock_pool: List[str], trade_dates: List[str]) -> List[str]:
        """检查缺失的K线数据日期"""
        missing_dates = []
        
        for date in trade_dates:
            # 检查这一天有多少股票有K线数据
            count = BarData.query.filter(
                BarData.ts_code.in_(stock_pool),
                BarData.trade_date == date,
                BarData.freq == "D"
            ).count()
            
            # 覆盖率判断逻辑：
            # - 如果 < 80%，认为数据不完整，需要补全（包括0%的情况）
            # - 如果 ≥ 80%，数据已完整
            coverage = count / len(stock_pool) if stock_pool else 0
            if coverage < 0.8:
                missing_dates.append(date)
                logger.debug(f"{date}: K线覆盖率 {coverage*100:.1f}%，需要补全")
            else:
                logger.debug(f"{date}: K线覆盖率 {coverage*100:.1f}%，数据已完整")
        
        return missing_dates
    
    def _check_missing_factors(self, stock_pool: List[str], trade_dates: List[str]) -> List[str]:
        """检查缺失的因子数据日期"""
        from models.bar_data import BarData
        missing_dates = []

        for date in trade_dates:
            # 🔴 优先使用交易日历判断是否为交易日
            is_trading = self._is_trading_day(date)

            if is_trading is False:
                # 明确是非交易日，跳过
                logger.debug(f"{date}: 非交易日（根据交易日历），跳过")
                continue
            elif is_trading is None:
                # 交易日历中没有该日期，使用K线覆盖率作为备用方案
                kline_count = BarData.query.filter(
                    BarData.ts_code.in_(stock_pool),
                    BarData.trade_date == date
                ).count()

                kline_coverage = kline_count / len(stock_pool) if stock_pool else 0
                if kline_coverage < 0.2:
                    logger.debug(f"{date}: K线覆盖率{kline_coverage*100:.1f}%，跳过（可能是非交易日）")
                    continue
                else:
                    logger.debug(f"{date}: 交易日历无记录，但K线覆盖率{kline_coverage*100:.1f}%，继续")

            # 检查这一天有多少股票有因子数据
            count = FactorData.query.filter(
                FactorData.ts_code.in_(stock_pool),
                FactorData.trade_date == date
            ).count()

            # 如果覆盖率低于80%，认为需要补全
            coverage = count / len(stock_pool) if stock_pool else 0
            if coverage < 0.8:
                missing_dates.append(date)
                logger.debug(f"{date}: 因子覆盖率 {coverage*100:.1f}%，需要计算")
            else:
                logger.debug(f"{date}: 因子覆盖率 {coverage*100:.1f}%，数据已完整")

        return missing_dates

    def _is_trading_day(self, cal_date: str) -> bool:
        """
        判断指定日期是否为交易日（使用交易日历）

        Args:
            cal_date: 日期 YYYYMMDD

        Returns:
            True=交易日, False=非交易日, None=未知（数据库中无记录）
        """
        try:
            from models.trading_calendar import TradingCalendar
            record = TradingCalendar.query.get(cal_date)
            if record:
                return record.is_trading_day
            return None
        except Exception as e:
            logger.debug(f"查询交易日历失败: {e}")
            return None
    
    def _download_kline_batch(self, stock_pool: List[str], dates: List[str]) -> Dict:
        """批量下载K线数据"""
        if not dates:
            return {"message": "无需下载"}
        
        start_date = min(dates)
        end_date = max(dates)
        
        logger.info(f"📡 开始下载K线: {len(stock_pool)}只股票, {start_date} 至 {end_date}")
        
        result = self.data_service.download_stock_data(
            ts_codes=stock_pool,
            start_date=start_date,
            end_date=end_date,
            freq="D",
            data_source="tushare"  # 🔴 直接使用TuShare（Baostock服务当前不稳定）
        )
        
        logger.info(f"K线下载完成: 成功{result.get('success_count', 0)}/{result.get('total', 0)}, "
                   f"存储{result.get('stored_records', 0)}条记录")
        
        return result
    
    def _calculate_factors_batch(self, stock_pool: List[str], dates: List[str]) -> Dict:
        """批量计算因子数据"""
        if not dates:
            return {"message": "无需计算"}
        
        total_success = 0
        total_failed = 0
        results = []
        failed_details = []  # 记录失败详情
        
        logger.info(f"开始计算因子: {len(stock_pool)}只股票 × {len(dates)}天")
        
        for date in dates:
            logger.info(f"计算因子: {date}")
            result = FactorService.calculate_factors_real(
                ts_codes=stock_pool,
                trade_date=date,
                factor_codes=None,  # 计算所有因子
                overwrite=False
            )
            
            success_count = result.get("success_count", 0)
            fail_count = result.get("fail_count", 0)
            total_success += success_count
            total_failed += fail_count
            
            results.append({
                "date": date,
                "success": success_count,
                "failed": fail_count
            })
            
            # 记录失败的股票
            if fail_count > 0:
                failed_stocks = result.get("failed_stocks", [])
                if failed_stocks:
                    failed_details.append({
                        "date": date,
                        "count": fail_count,
                        "stocks": failed_stocks[:10]  # 只记录前10只
                    })
            
            logger.info(f"{date}: 成功{success_count}/{result.get('total', 0)}, "
                       f"耗时{result.get('execution_time', 0)}秒")
        
        result_data = {
            "total_success": total_success,
            "total_failed": total_failed,
            "dates_processed": len(dates),
            "details": results
        }
        
        if failed_details:
            result_data["failed_details"] = failed_details
        
        return result_data


# 单例
data_completion_service = DataCompletionService()

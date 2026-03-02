"""
Baostock数据服务 - 完全免费，无限制
官方文档: http://baostock.com/baostock/index.php/
"""
import baostock as bs
import baostock.common.contants as bs_constants
import pandas as pd
import socket
from datetime import datetime, timedelta
from typing import Optional, List
import logging
import threading

logger = logging.getLogger(__name__)

# 🔴 设置Baostock socket超时（关键修复）
# Baostock库默认没有超时设置，导致连接不上时无限阻塞
_SOCKET_TIMEOUT = 15  # 秒


class BaostockHelper:
    """Baostock数据助手 - 完全免费，无API调用限制"""
    
    def __init__(self):
        self.is_logged_in = False
        
    def _test_connection(self) -> bool:
        """测试Baostock服务器是否可达（快速检测）"""
        try:
            # 先用简单的socket测试连接
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(_SOCKET_TIMEOUT)
            result = test_socket.connect_ex((bs_constants.BAOSTOCK_SERVER_IP, bs_constants.BAOSTOCK_SERVER_PORT))
            test_socket.close()
            
            if result == 0:
                logger.info(f"✅ Baostock服务器连接测试成功")
                return True
            else:
                logger.warning(f"⚠️ Baostock服务器连接失败，错误码: {result}")
                return False
        except Exception as e:
            logger.warning(f"⚠️ Baostock服务器连接测试失败: {e}")
            return False
    
    def login(self):
        """登录Baostock（带超时保护）"""
        if self.is_logged_in:
            return
        
        # 🔴 步骤1：快速测试服务器是否可达
        if not self._test_connection():
            raise TimeoutError("Baostock服务器不可达，跳过登录")
        
        try:
            logger.info("🔐 尝试登录Baostock...")
            
            # 🔴 关键修复：设置全局默认socket超时
            # Baostock库在socketutil.py中创建socket时没有设置超时
            socket.setdefaulttimeout(_SOCKET_TIMEOUT)
            
            lg = bs.login()
            
            # 恢复默认socket超时设置
            socket.setdefaulttimeout(None)
            
            if lg.error_code != '0':
                logger.error(f"❌ Baostock登录失败: {lg.error_msg}")
                raise Exception(f"Baostock登录失败: {lg.error_msg}")
            
            logger.info("✅ Baostock登录成功")
            self.is_logged_in = True
            
        except socket.timeout as e:
            socket.setdefaulttimeout(None)
            logger.error(f"❌ Baostock socket超时: {e}")
            raise TimeoutError("Baostock网络连接超时")
        except TimeoutError:
            socket.setdefaulttimeout(None)
            raise
        except Exception as e:
            socket.setdefaulttimeout(None)
            logger.error(f"❌ Baostock登录异常: {e}")
            raise TimeoutError(f"Baostock服务不可用: {e}")
    
    def logout(self):
        """登出Baostock"""
        if self.is_logged_in:
            bs.logout()
            self.is_logged_in = False
            logger.info("👋 Baostock已登出")
    
    def __enter__(self):
        """上下文管理器：进入"""
        self.login()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器：退出"""
        self.logout()
    
    def convert_ts_code_to_baostock(self, ts_code: str) -> str:
        """
        转换TuShare代码格式到Baostock格式
        TuShare: 000001.SZ -> Baostock: sz.000001
        TuShare: 600000.SH -> Baostock: sh.600000
        """
        if not ts_code or '.' not in ts_code:
            return ts_code
        
        code, exchange = ts_code.split('.')
        exchange_map = {
            'SZ': 'sz',
            'SH': 'sh',
            'BJ': 'bj'  # 北交所
        }
        baostock_exchange = exchange_map.get(exchange.upper(), exchange.lower())
        return f"{baostock_exchange}.{code}"
    
    def convert_baostock_to_ts_code(self, bs_code: str) -> str:
        """
        转换Baostock代码格式到TuShare格式
        Baostock: sz.000001 -> TuShare: 000001.SZ
        Baostock: sh.600000 -> TuShare: 600000.SH
        """
        if not bs_code or '.' not in bs_code:
            return bs_code
        
        exchange, code = bs_code.split('.')
        exchange_map = {
            'sz': 'SZ',
            'sh': 'SH',
            'bj': 'BJ'
        }
        ts_exchange = exchange_map.get(exchange.lower(), exchange.upper())
        return f"{code}.{ts_exchange}"
    
    def get_daily_data(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        adjust: str = "2"  # 复权类型：1-后复权，2-前复权，3-不复权
    ) -> Optional[pd.DataFrame]:
        """
        获取日线数据
        
        Args:
            ts_code: 股票代码（TuShare格式，如 000001.SZ）
            start_date: 开始日期（格式：YYYY-MM-DD 或 YYYYMMDD）
            end_date: 结束日期（格式：YYYY-MM-DD 或 YYYYMMDD）
            adjust: 复权类型（"1"-后复权，"2"-前复权，"3"-不复权）
        
        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount
        """
        self.login()
        
        # 转换代码格式
        bs_code = self.convert_ts_code_to_baostock(ts_code)
        
        # 格式化日期
        start_date = self._format_date(start_date)
        end_date = self._format_date(end_date)
        
        logger.debug(f"📊 获取 {bs_code} 的日线数据: {start_date} ~ {end_date}")
        
        # 获取数据
        # frequency: d=日k线，w=周k线，m=月k线，5=5分钟，15=15分钟，30=30分钟，60=60分钟
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount,adjustflag",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag=adjust
        )
        
        if rs.error_code != '0':
            logger.warning(f"⚠️ 获取{bs_code}数据失败: {rs.error_msg}")
            return None
        
        # 转换为DataFrame
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            logger.debug(f"📭 {bs_code} 在 {start_date}~{end_date} 无数据")
            return None
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 数据类型转换
        df['date'] = pd.to_datetime(df['date'])
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 过滤无效数据
        df = df.dropna(subset=['close'])
        df = df[df['close'] > 0]
        
        logger.debug(f"✅ 获取到 {len(df)} 条数据")
        return df
    
    def get_stock_list(self) -> List[dict]:
        """
        获取所有A股列表
        
        Returns:
            List of dict with keys: code, code_name, exchange
        """
        self.login()
        
        logger.info("📋 获取A股列表...")
        
        # 获取证券基本资料
        rs = bs.query_stock_basic()
        if rs.error_code != '0':
            logger.error(f"❌ 获取股票列表失败: {rs.error_msg}")
            return []
        
        # 转换为列表
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 只保留A股（不包括退市股）
        df = df[
            (df['type'] == '1') &  # 1-股票，2-指数，3-其它
            (df['status'] == '1')   # 1-正常，0-停牌
        ]
        
        # 转换为TuShare格式
        stock_list = []
        for _, row in df.iterrows():
            ts_code = self.convert_baostock_to_ts_code(row['code'])
            stock_list.append({
                'code': ts_code,
                'code_name': row['code_name'],
                'exchange': row['code'].split('.')[0].upper()
            })
        
        logger.info(f"✅ 获取到 {len(stock_list)} 只A股")
        return stock_list
    
    def _format_date(self, date_str: str) -> str:
        """
        格式化日期为 YYYY-MM-DD 格式
        
        Args:
            date_str: 日期字符串（YYYY-MM-DD 或 YYYYMMDD）
        
        Returns:
            格式化后的日期字符串（YYYY-MM-DD）
        """
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d")
        
        # 如果已经是YYYY-MM-DD格式，直接返回
        if '-' in date_str:
            return date_str
        
        # 如果是YYYYMMDD格式，转换为YYYY-MM-DD
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        
        return date_str


# 全局实例（单例模式）
_baostock_instance = None


def get_baostock_helper() -> BaostockHelper:
    """获取Baostock助手的全局实例"""
    global _baostock_instance
    if _baostock_instance is None:
        _baostock_instance = BaostockHelper()
    return _baostock_instance

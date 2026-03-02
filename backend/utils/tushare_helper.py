"""
TuShare 数据源封装 - StockQuant Pro
提供股票列表、日线数据等获取接口。

配置 token：在 .env 或环境变量中设置 TUSHARE_TOKEN。
"""
import os
from typing import Optional
import pandas as pd


class TushareHelper:
    """TuShare 辅助类"""

    def __init__(self, token: Optional[str] = None):
        """
        初始化 TuShare。

        Args:
            token: TuShare token（可选，优先从参数获取，否则从环境变量或配置读取）
        """
        # 优先级：参数 > 环境变量 > 配置文件
        if token:
            self.token = token
        else:
            import os
            self.token = os.getenv("TUSHARE_TOKEN", "")
            # 如果环境变量为空，尝试从配置读取
            if not self.token:
                try:
                    from config import config as app_config
                    self.token = app_config['default'].TUSHARE_TOKEN
                except:
                    pass
        
        self.pro = None
        if self.token:
            try:
                import tushare as ts
                ts.set_token(self.token)
                self.pro = ts.pro_api()
                print(f"✅ TuShare 初始化成功，Token: {self.token[:20]}...")
            except ImportError:
                print("Warning: tushare 未安装，请执行 pip install tushare")
            except Exception as e:
                print(f"Warning: TuShare 初始化失败: {e}")
        else:
            print("⚠️  TuShare Token 未配置")

    def is_available(self) -> bool:
        """检查 TuShare 是否可用"""
        return self.pro is not None

    def get_stock_basic(
        self,
        exchange: Optional[str] = None,
        list_status: str = "L",
    ) -> Optional[pd.DataFrame]:
        """
        获取股票列表。

        Args:
            exchange: 交易所（SSE/SZSE）
            list_status: 上市状态（L-上市，D-退市，P-暂停）

        Returns:
            DataFrame，包含 ts_code, symbol, name, area, industry, market, exchange, list_date 等字段
            失败返回 None
        """
        if not self.is_available():
            return None
        try:
            df = self.pro.stock_basic(
                exchange=exchange or "",
                list_status=list_status,
                fields="ts_code,symbol,name,area,industry,market,exchange,list_date,list_status",
            )
            return df
        except Exception as e:
            print(f"获取股票列表失败：{e}")
            return None

    def get_daily_data(
        self,
        ts_code: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        获取单只股票日线数据。

        Args:
            ts_code: 股票代码（如 000001.SZ）
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD（可选）

        Returns:
            DataFrame，包含 ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount 等
            失败返回 None
        """
        if not self.is_available():
            return None
        try:
            df = self.pro.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date or "",
            )
            return df
        except Exception as e:
            print(f"获取 {ts_code} 日线数据失败：{e}")
            return None

    def get_daily_by_date(
        self,
        trade_date: str,
        ts_codes: Optional[list] = None,
    ) -> Optional[pd.DataFrame]:
        """
        按日期批量获取日线数据（高效！）
        
        根据TuShare文档: https://tushare.pro/document/2?doc_id=27
        - 可以通过 trade_date 获取某天所有股票数据
        - 也可以通过 ts_code 传入多个股票（逗号分隔）
        
        Args:
            trade_date: 交易日期 YYYYMMDD
            ts_codes: 股票代码列表（可选，不传则获取全市场）

        Returns:
            DataFrame，包含该日期所有股票的数据
        """
        if not self.is_available():
            return None
        try:
            if ts_codes:
                # 多股票用逗号拼接，一次请求获取
                ts_code_str = ','.join(ts_codes)
                df = self.pro.daily(
                    ts_code=ts_code_str,
                    trade_date=trade_date,
                )
            else:
                # 获取全市场某天数据
                df = self.pro.daily(trade_date=trade_date)
            return df
        except Exception as e:
            print(f"获取 {trade_date} 日线数据失败：{e}")
            return None
    
    def get_daily_batch(
        self,
        ts_codes: list,
        start_date: str,
        end_date: Optional[str] = None,
        batch_size: int = 50,
    ) -> Optional[pd.DataFrame]:
        """
        批量获取多只股票的日线数据
        
        TuShare支持多股票同时获取（逗号分隔），但有长度限制
        这里分批处理，每批50只
        
        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            batch_size: 每批股票数量（默认50）

        Returns:
            合并后的DataFrame
        """
        if not self.is_available():
            return None
        
        all_data = []
        
        for i in range(0, len(ts_codes), batch_size):
            batch = ts_codes[i:i+batch_size]
            ts_code_str = ','.join(batch)
            
            try:
                df = self.pro.daily(
                    ts_code=ts_code_str,
                    start_date=start_date,
                    end_date=end_date or "",
                )
                if df is not None and len(df) > 0:
                    all_data.append(df)
            except Exception as e:
                print(f"批量获取第{i//batch_size+1}批数据失败：{e}")
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return None

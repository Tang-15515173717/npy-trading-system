"""
获取大盘指数数据 - TuShare
支持获取上证指数、深证成指、沪深300等主要指数的历史数据
"""
import os
import sys
import pandas as pd
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.tushare_helper import TushareHelper

# 主要指数代码
INDEX_CODES = {
    '000001.SH': '上证指数',
    '399001.SZ': '深证成指',
    '000300.SH': '沪深300',
    '000016.SH': '上证50',
    '399006.SZ': '创业板指',
    '000688.SH': '科创50',
    '000905.SH': '中证500',
    '000852.SH': '中证1000',
}

def get_index_data(
    ts_code: str,
    start_date: str = '20230101',
    end_date: str = None
):
    """
    获取指数数据
    
    Args:
        ts_code: 指数代码（如 000001.SH）
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD（可选，默认今天）
    
    Returns:
        DataFrame: 指数数据
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')
    
    print(f"\n{'='*80}")
    print(f"📊 获取指数数据：{INDEX_CODES.get(ts_code, ts_code)}")
    print(f"{'='*80}")
    print(f"指数代码：{ts_code}")
    print(f"时间范围：{start_date} ~ {end_date}")
    print()
    
    # 初始化TuShare
    helper = TushareHelper()
    
    if not helper.is_available():
        print("❌ TuShare 未配置或不可用")
        return None
    
    try:
        # 获取指数日线数据
        df = helper.pro.index_daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields='ts_code,trade_date,close,open,high,low,pre_close,change,pct_chg,vol,amount'
        )
        
        if df is None or df.empty:
            print(f"❌ 未获取到数据")
            return None
        
        # 按日期排序
        df = df.sort_values('trade_date')
        
        print(f"✅ 成功获取 {len(df)} 条数据")
        print()
        print("📊 数据预览：")
        print(df.head(10))
        print()
        print("📊 最新数据：")
        print(df.tail(5))
        print()
        
        # 计算一些统计信息
        first_close = df.iloc[0]['close']
        last_close = df.iloc[-1]['close']
        total_return = (last_close - first_close) / first_close * 100
        max_close = df['close'].max()
        min_close = df['close'].min()
        
        print("📈 统计信息：")
        print(f"   起始点位：{first_close:.2f}")
        print(f"   最新点位：{last_close:.2f}")
        print(f"   最高点位：{max_close:.2f}")
        print(f"   最低点位：{min_close:.2f}")
        print(f"   区间涨跌：{'+' if total_return > 0 else ''}{total_return:.2f}%")
        print()
        
        return df
        
    except Exception as e:
        print(f"❌ 获取失败：{str(e)}")
        return None


def get_all_major_indices(start_date: str = '20230101', end_date: str = None):
    """
    获取所有主要指数数据
    
    Args:
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD（可选）
    
    Returns:
        dict: {指数代码: DataFrame}
    """
    results = {}
    
    print("\n" + "="*80)
    print("📊 批量获取主要指数数据")
    print("="*80)
    print(f"共 {len(INDEX_CODES)} 个指数")
    print()
    
    for ts_code, name in INDEX_CODES.items():
        df = get_index_data(ts_code, start_date, end_date)
        if df is not None:
            results[ts_code] = df
        
        # API限速
        import time
        time.sleep(0.5)
    
    print("\n" + "="*80)
    print("📊 获取完成统计")
    print("="*80)
    print(f"✅ 成功：{len(results)} 个指数")
    print(f"❌ 失败：{len(INDEX_CODES) - len(results)} 个指数")
    print()
    
    return results


def save_to_csv(df: pd.DataFrame, ts_code: str, output_dir: str = './data/indices'):
    """
    保存指数数据到CSV文件
    
    Args:
        df: 指数数据
        ts_code: 指数代码
        output_dir: 输出目录
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f"{output_dir}/{ts_code}_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"💾 已保存到：{filename}")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("📊 大盘指数数据获取工具")
    print("="*80)
    print()
    print("支持的指数：")
    for code, name in INDEX_CODES.items():
        print(f"  {code:15} {name}")
    print()
    
    # 示例1：获取上证指数最近3年数据
    print("\n【示例1】获取上证指数数据")
    df_sh = get_index_data('000001.SH', '20230101', '20260130')
    
    # 示例2：获取沪深300数据
    print("\n【示例2】获取沪深300数据")
    df_hs300 = get_index_data('000300.SH', '20230101', '20260130')
    
    # 示例3：批量获取所有主要指数（谨慎使用，注意API限速）
    # print("\n【示例3】批量获取所有指数")
    # all_indices = get_all_major_indices('20230101', '20260130')
    
    print("\n" + "="*80)
    print("✅ 完成！")
    print("="*80)
    print()
    print("💡 使用建议：")
    print("   1. 单次获取单个指数数据：get_index_data(ts_code, start_date, end_date)")
    print("   2. 注意TuShare API限速（建议间隔0.5秒以上）")
    print("   3. 可以将数据保存到数据库或CSV文件")
    print()

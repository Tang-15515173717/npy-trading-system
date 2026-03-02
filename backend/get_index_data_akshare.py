"""
使用 AKShare 获取大盘指数数据（免费方案）
AKShare: https://akshare.akfamily.xyz/
"""
import sys
import pandas as pd
from datetime import datetime

print("=" * 80)
print("📊 AKShare 大盘指数数据获取工具（免费）")
print("=" * 80)
print()

# 检查AKShare是否安装
try:
    import akshare as ak
    print("✅ AKShare 已安装")
    print(f"   版本：{ak.__version__}")
except ImportError:
    print("❌ AKShare 未安装")
    print()
    print("请执行以下命令安装：")
    print("   pip install akshare")
    print()
    print("或使用国内镜像加速：")
    print("   pip install akshare -i https://pypi.tuna.tsinghua.edu.cn/simple")
    sys.exit(1)

print()

# 主要指数映射（标准代码 → AKShare代码）
INDEX_MAPPING = {
    '000001.SH': ('sh000001', '上证指数'),
    '399001.SZ': ('sz399001', '深证成指'),
    '000300.SH': ('sh000300', '沪深300'),
    '000016.SH': ('sh000016', '上证50'),
    '399006.SZ': ('sz399006', '创业板指'),
    '000688.SH': ('sh000688', '科创50'),
    '000905.SH': ('sh000905', '中证500'),
    '000852.SH': ('sh000852', '中证1000'),
}

def get_index_data(ts_code: str, start_date: str = '2023-01-01'):
    """
    获取指数数据
    
    Args:
        ts_code: 标准指数代码（如 000001.SH）
        start_date: 开始日期 YYYY-MM-DD
    
    Returns:
        DataFrame
    """
    if ts_code not in INDEX_MAPPING:
        print(f"❌ 不支持的指数代码：{ts_code}")
        return None
    
    ak_symbol, index_name = INDEX_MAPPING[ts_code]
    
    print(f"\n{'='*80}")
    print(f"📊 获取指数数据：{index_name}")
    print(f"{'='*80}")
    print(f"标准代码：{ts_code}")
    print(f"AK代码：  {ak_symbol}")
    print(f"开始日期：{start_date}")
    print()
    
    try:
        # 获取指数日线数据
        df = ak.stock_zh_index_daily(symbol=ak_symbol)
        
        if df is None or df.empty:
            print("❌ 未获取到数据")
            return None
        
        # 添加指数代码列
        df['ts_code'] = ts_code
        df['index_name'] = index_name
        
        # 重命名列（统一格式）
        df = df.rename(columns={
            'date': 'trade_date',
            'volume': 'vol'
        })
        
        # 转换日期格式
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y%m%d')
        
        # 筛选日期
        start_date_str = start_date.replace('-', '')
        df = df[df['trade_date'] >= start_date_str]
        
        # 排序
        df = df.sort_values('trade_date')
        
        print(f"✅ 成功获取 {len(df)} 条数据")
        print()
        print("📊 数据预览（最早5条）：")
        print(df.head())
        print()
        print("📊 数据预览（最新5条）：")
        print(df.tail())
        print()
        
        # 计算统计信息
        first_row = df.iloc[0]
        last_row = df.iloc[-1]
        first_close = first_row['close']
        last_close = last_row['close']
        total_return = (last_close - first_close) / first_close * 100
        max_close = df['close'].max()
        min_close = df['close'].min()
        
        print("📈 统计信息：")
        print(f"   数据起始：{first_row['trade_date']}")
        print(f"   数据截止：{last_row['trade_date']}")
        print(f"   起始点位：{first_close:.2f}")
        print(f"   最新点位：{last_close:.2f}")
        print(f"   最高点位：{max_close:.2f}")
        print(f"   最低点位：{min_close:.2f}")
        print(f"   区间涨跌：{'+' if total_return > 0 else ''}{total_return:.2f}%")
        print()
        
        return df
        
    except Exception as e:
        print(f"❌ 获取失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return None


def save_to_csv(df: pd.DataFrame, ts_code: str, output_dir: str = './data/indices'):
    """保存到CSV文件"""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    index_name = INDEX_MAPPING[ts_code][1]
    filename = f"{output_dir}/{ts_code}_{index_name}_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"💾 已保存到：{filename}")
    return filename


if __name__ == "__main__":
    print("\n💡 支持的指数列表：")
    print("-" * 80)
    for code, (ak_code, name) in INDEX_MAPPING.items():
        print(f"  {code:15} {name:12} (AK: {ak_code})")
    print()
    
    # 示例1：获取上证指数
    print("\n【示例1】获取上证指数数据（最近3年）")
    df_sh = get_index_data('000001.SH', '2023-01-01')
    if df_sh is not None:
        save_to_csv(df_sh, '000001.SH')
    
    # 示例2：获取沪深300
    print("\n【示例2】获取沪深300数据（最近3年）")
    df_hs300 = get_index_data('000300.SH', '2023-01-01')
    if df_hs300 is not None:
        save_to_csv(df_hs300, '000300.SH')
    
    # 示例3：获取创业板指
    print("\n【示例3】获取创业板指数据（最近1年）")
    df_cy = get_index_data('399006.SZ', '2025-01-01')
    
    print("\n" + "="*80)
    print("✅ 完成！")
    print("="*80)
    print()
    print("💡 使用建议：")
    print("   1. AKShare完全免费，无需注册")
    print("   2. 数据实时更新，覆盖所有主要指数")
    print("   3. 可以集成到回测系统作为基准对比")
    print("   4. 数据已保存到 ./data/indices/ 目录")
    print()
    print("📚 更多信息：")
    print("   官方文档：https://akshare.akfamily.xyz/")
    print("   指数数据：https://akshare.akfamily.xyz/data/index/index.html")
    print()

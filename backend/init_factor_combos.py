"""
因子组合初始化脚本 - StockQuant Pro v2.3
预设6个经典多因子组合
"""
from services.factor_combo_service import FactorComboService
import json


# 因子组合定义
# 每个因子: factor_code, score(0-100,总分=100), direction(long=正向, short=负向)

FACTOR_COMBOS = [
    # ============================================
    # 1. 价值型组合 (Value)
    # 理念：低估值 + 高股息 + 高ROE
    # 适合：保守型投资者，追求稳定收益
    # ============================================
    {
        "name": "价值低估精选",
        "description": "选取低估值、高股息、优质资产的股票，适合价值投资风格",
        "factors": [
            {"factor_code": "pe_ratio", "score": 25, "direction": "short"},  # 市盈率越低越好
            {"factor_code": "pb_ratio", "score": 20, "direction": "short"},  # 市净率越低越好
            {"factor_code": "dividend_yield", "score": 20, "direction": "long"},  # 股息率越高越好
            {"factor_code": "roe", "score": 20, "direction": "long"},  # ROE越高越好
            {"factor_code": "gross_margin", "score": 15, "direction": "long"},  # 毛利率越高越好
        ],
        "selection_rule": {"type": "topk", "k": 50}
    },

    # ============================================
    # 2. 成长型组合 (Growth)
    # 理念：高增长 + 高盈利 + 高ROE
    # 适合：激进型投资者，追求高收益
    # ============================================
    {
        "name": "高成长精选",
        "description": "选取高营收增长、高利润增长、高ROE的股票，适合成长投资风格",
        "factors": [
            {"factor_code": "revenue_growth", "score": 25, "direction": "long"},  # 营收增长越高越好
            {"factor_code": "profit_growth", "score": 25, "direction": "long"},  # 利润增长越高越好
            {"factor_code": "roe", "score": 20, "direction": "long"},  # ROE越高越好
            {"factor_code": "net_margin", "score": 15, "direction": "long"},  # 净利率越高越好
            {"factor_code": "return_20d", "score": 15, "direction": "long"},  # 20日收益越高越好
        ],
        "selection_rule": {"type": "topk", "k": 30}
    },

    # ============================================
    # 3. 质量型组合 (Quality)
    # 理念：高盈利 + 高毛利 + 低负债
    # 适合：稳健型投资者，注重基本面
    # ============================================
    {
        "name": "优质企业精选",
        "description": "选取高盈利质量、低负债、稳健经营的股票，适合价值与质量并重的投资者",
        "factors": [
            {"factor_code": "roe", "score": 25, "direction": "long"},  # ROE越高越好
            {"factor_code": "gross_margin", "score": 20, "direction": "long"},  # 毛利率越高越好
            {"factor_code": "net_margin", "score": 20, "direction": "long"},  # 净利率越高越好
            {"factor_code": "debt_ratio", "score": 20, "direction": "short"},  # 资产负债率越低越好
            {"factor_code": "total_asset_turnover", "score": 15, "direction": "long"},  # 资产周转率越高越好
        ],
        "selection_rule": {"type": "topk", "k": 40}
    },

    # ============================================
    # 4. 动量型组合 (Momentum)
    # 理念：强动量 + 强势趋势
    # 适合：趋势交易者，顺势而为
    # ============================================
    {
        "name": "强势动量精选",
        "description": "选取近期涨幅强劲、技术指标向好的股票，适合趋势交易风格",
        "factors": [
            {"factor_code": "return_20d", "score": 25, "direction": "long"},  # 20日收益越高越好
            {"factor_code": "return_60d", "score": 20, "direction": "long"},  # 60日收益越高越好
            {"factor_code": "rsi_14", "score": 15, "direction": "long"},  # RSI适中偏高表示强势
            {"factor_code": "macd", "score": 20, "direction": "long"},  # MACD正值表示多头
            {"factor_code": "volume_ratio", "score": 20, "direction": "long"},  # 量比越高表示越活跃
        ],
        "selection_rule": {"type": "topk", "k": 30}
    },

    # ============================================
    # 5. 综合均衡型组合 (Balanced)
    # 理念：价值 + 成长 + 质量 + 动量
    # 适合：长期投资者，多维度选股
    # ============================================
    {
        "name": "多因子均衡精选",
        "description": "综合估值、成长、质量、动量四个维度均衡选股，适合长期价值投资",
        "factors": [
            {"factor_code": "pe_ratio", "score": 15, "direction": "short"},  # 低估值
            {"factor_code": "roe", "score": 20, "direction": "long"},  # 高ROE（质量）
            {"factor_code": "profit_growth", "score": 15, "direction": "long"},  # 高增长（成长）
            {"factor_code": "return_20d", "score": 20, "direction": "long"},  # 强动量
            {"factor_code": "dividend_yield", "score": 10, "direction": "long"},  # 高股息
            {"factor_code": "net_margin", "score": 10, "direction": "long"},  # 高盈利
            {"factor_code": "volume_ratio", "score": 10, "direction": "long"},  # 高活跃度
        ],
        "selection_rule": {"type": "topk", "k": 50}
    },

    # ============================================
    # 6. 低波动稳健型组合 (Low Volatility)
    # 理念：低波动 + 高股息 + 低估值
    # 适合：风险厌恶型，追求稳定收益
    # ============================================
    {
        "name": "低波动稳健精选",
        "description": "选取低波动、高股息、低估值的股票，适合风险厌恶型投资者",
        "factors": [
            {"factor_code": "volatility_20d", "score": 25, "direction": "short"},  # 低波动率越好
            {"factor_code": "beta", "score": 20, "direction": "short"},  # 低Beta表示低风险
            {"factor_code": "dividend_yield", "score": 25, "direction": "long"},  # 高股息
            {"factor_code": "pe_ratio", "score": 15, "direction": "short"},  # 低估值
            {"factor_code": "roe", "score": 15, "direction": "long"},  # 适当ROE
        ],
        "selection_rule": {"type": "topk", "k": 40}
    },
]


def init_factor_combos():
    """初始化因子组合"""
    print("\n" + "="*60)
    print("📊 初始化多因子组合")
    print("="*60 + "\n")

    for combo in FACTOR_COMBOS:
        name = combo["name"]
        description = combo["description"]
        factors = combo["factors"]
        selection_rule = combo["selection_rule"]

        # 检查是否已存在
        existing = None
        try:
            result = FactorComboService.list(page=1, page_size=100)
            for item in result.get("items", []):
                if item["name"] == name:
                    existing = item
                    break
        except Exception as e:
            print(f"  ⚠️  查询失败: {e}")
            existing = None

        if existing:
            print(f"  ⏭️  跳过: {name} (已存在)")
            continue

        # 创建新组合
        try:
            factor_config = {"factors": factors}
            result = FactorComboService.create(
                name=name,
                factor_config=factor_config,
                selection_rule=selection_rule
            )
            print(f"  ✅ 创建: {name}")
            print(f"      - 因子数量: {len(factors)}")
            print(f"      - 选股规则: {selection_rule['type']} top {selection_rule.get('k', selection_rule.get('threshold', 'N/A'))}")

            # 显示因子详情
            for f in factors:
                direction_cn = "正向" if f["direction"] == "long" else "负向"
                print(f"        - {f['factor_code']}: {f['score']}分 ({direction_cn})")

        except Exception as e:
            print(f"  ❌ 创建失败: {name} - {e}")

    print("\n" + "="*60)
    print("✅ 因子组合初始化完成！")
    print("="*60 + "\n")


if __name__ == "__main__":
    from app import create_app
    app = create_app()

    with app.app_context():
        init_factor_combos()

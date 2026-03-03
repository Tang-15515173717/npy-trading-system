"""
支付配置文件
用于配置蓝兔支付网关参数
蓝兔支付官网: https://www.ltzf.cn
文档: https://www.ltzf.cn/doc
"""

# ==================== 蓝兔支付配置 ====================
# 蓝兔支付优势：
# - 支付宝和微信官方合作伙伴
# - 个人、个体户、企业都可以申请
# - 官方直接签约，无需营业执照
# - 资金由支付宝、微信支付官方直连结算
# - 更安全，避免二次清算风险

PAYMENT_CONFIG = {
    # 商户ID（登录蓝兔支付后台获取）
    'merchant_id': 'YOUR_MERCHANT_ID',

    # 商户密钥（登录蓝兔支付后台获取）
    'merchant_key': 'YOUR_MERCHANT_KEY',
}

# ==================== 环境变量配置（推荐） ====================
# 在 .env 文件或环境变量中设置：
# LANZHI_MERCHANT_ID=your_merchant_id
# LANZHI_MERCHANT_KEY=your_merchant_key

# ==================== 开发测试��置 ====================
# 开发环境可以使用测试模式
# PAYMENT_CONFIG = {
#     'merchant_id': 'test_merchant_id',
#     'merchant_key': 'test_merchant_key',
# }

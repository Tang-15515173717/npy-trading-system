"""
聚合支付网关 - 支持支付宝和微信支付
使用第三方聚合支付平台（如PayJS、易支付等）
"""
import requests
import hashlib
import json
from typing import Dict, Any, Optional
from datetime import datetime
import uuid


class AggregatePaymentGateway:
    """
    聚合支付网关类

    支持的支付平台：
    - PayJS: https://payjs.cn （推荐，个人可用）
    - 易支付: 各类易支付平台
    """

    def __init__(self, gateway_url: str, merchant_id: str, merchant_key: str):
        """
        初始化支付网关

        Args:
            gateway_url: 支付网关API地址
            merchant_id: 商户ID
            merchant_key: 商户密钥
        """
        self.gateway_url = gateway_url.rstrip('/')
        self.merchant_id = merchant_id
        self.merchant_key = merchant_key

    def _generate_sign(self, params: Dict[str, Any]) -> str:
        """
        生成签名

        Args:
            params: 待签名参数

        Returns:
            签名字符串
        """
        # 过滤空值和sign字段
        filtered = {k: v for k, v in params.items() if v is not None and v != '' and k != 'sign'}
        # 按key排序
        sorted_params = sorted(filtered.items())
        # 拼接字符串
        sign_str = '&'.join([f'{k}={v}' for k, v in sorted_params])
        # 添加密钥
        sign_str += f'&key={self.merchant_key}'
        # MD5签名
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

    def create_order(
        self,
        out_trade_no: str,
        total_fee: int,
        body: str,
        pay_type: int = 1,
        notify_url: Optional[str] = None,
        return_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建支付订单

        Args:
            out_trade_no: 商户订单号
            total_fee: 金额（分）
            body: 商品描述
            pay_type: 支付类型 (1=支付宝, 2=微信)
            notify_url: 异步通知地址
            return_url: 同步跳转地址

        Returns:
            支付信息字典
        """
        params = {
            'mchid': self.merchant_id,
            'out_trade_no': out_trade_no,
            'total_fee': total_fee,
            'body': body,
            'notify_url': notify_url,
            'return_url': return_url
        }

        # 生成签名
        params['sign'] = self._generate_sign(params)

        try:
            # 发起请求
            response = requests.post(
                f'{self.gateway_url}/api/submit',
                data=params,
                timeout=30
            )
            result = response.json()

            if result.get('return_code') == 1 or result.get('code') == 0:
                return {
                    'success': True,
                    'order_id': out_trade_no,
                    'pay_url': result.get('qrcode') or result.get('payurl'),
                    'native_url': result.get('qrcode'),
                    'h5_url': result.get('payurl'),
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('msg', result.get('return_msg', '创建订单失败')),
                    'raw_response': result
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }

    def query_order(self, out_trade_no: str) -> Dict[str, Any]:
        """
        查询订单状态

        Args:
            out_trade_no: 商户订单号

        Returns:
            订单状态信息
        """
        params = {
            'mchid': self.merchant_id,
            'out_trade_no': out_trade_no
        }

        params['sign'] = self._generate_sign(params)

        try:
            response = requests.post(
                f'{self.gateway_url}/api/order/query',
                data=params,
                timeout=30
            )
            result = response.json()

            if result.get('return_code') == 1 or result.get('code') == 0:
                return {
                    'success': True,
                    'status': result.get('status') or result.get('trade_state'),
                    'total_fee': result.get('total_fee'),
                    'transaction_id': result.get('transaction_id'),
                    'time_end': result.get('time_end'),
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('msg', '查询失败'),
                    'raw_response': result
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }

    def verify_notify(self, data: Dict[str, Any]) -> bool:
        """
        验证支付回调通知

        Args:
            data: 回调数据

        Returns:
            是否验证成功
        """
        received_sign = data.pop('sign', None)
        if not received_sign:
            return False

        calculated_sign = self._generate_sign(data)
        return received_sign == calculated_sign

    def close_order(self, out_trade_no: str) -> Dict[str, Any]:
        """
        关闭订单

        Args:
            out_trade_no: 商户订单号

        Returns:
            关闭结果
        """
        params = {
            'mchid': self.merchant_id,
            'out_trade_no': out_trade_no
        }

        params['sign'] = self._generate_sign(params)

        try:
            response = requests.post(
                f'{self.gateway_url}/api/order/close',
                data=params,
                timeout=30
            )
            result = response.json()

            if result.get('return_code') == 1:
                return {
                    'success': True,
                    'message': '订单已关闭'
                }
            else:
                return {
                    'success': False,
                    'error': result.get('msg', '关闭失败')
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }


class PayJSGateway(AggregatePaymentGateway):
    """
    PayJS支付网关
    文档: https://payjs.cn/api/
    """

    def __init__(self, merchant_id: str, merchant_key: str):
        super().__init__(
            gateway_url='https://payjs.cn',
            merchant_id=merchant_id,
            merchant_key=merchant_key
        )


# 创建支付网关实例（从配置文件读取）
def create_payment_gateway(config: Dict[str, str] = None) -> AggregatePaymentGateway:
    """
    创建支付网关实例

    Args:
        config: 配置字典，包含 gateway_url, merchant_id, merchant_key

    Returns:
        支付网关实例
    """
    if config is None:
        # 优先从config文件读取
        try:
            from payments.config import PAYMENT_CONFIG
            config = PAYMENT_CONFIG
        except ImportError:
            # 从环境变量读取
            import os
            config = {
                'gateway_url': os.getenv('PAYMENT_GATEWAY_URL', 'https://payjs.cn'),
                'merchant_id': os.getenv('PAYMENT_MERCHANT_ID', ''),
                'merchant_key': os.getenv('PAYMENT_MERCHANT_KEY', '')
            }

    return AggregatePaymentGateway(
        gateway_url=config['gateway_url'],
        merchant_id=config['merchant_id'],
        merchant_key=config['merchant_key']
    )

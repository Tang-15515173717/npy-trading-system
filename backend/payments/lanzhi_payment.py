"""
蓝兔支付网关 - 支持支付宝和微信支付
蓝兔支付官网: https://www.ltzf.cn
文档: https://www.ltzf.cn/doc

优势：
- 支付宝和微信官方合作伙伴
- 个人、个体户、企业都可以申请
- 官方直接签约，无需营业执照
- 资金由支付宝、微信支付官方直连结算
"""
import requests
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
import time


class LanzhiPaymentGateway:
    """
    蓝兔支付网关类

    支持的支付方式：
    - 微信扫码支付 (native)
    - 微信H5支付 (h5)
    - 支付宝扫码支付 (native)
    - 支付宝H5支付 (h5)
    - 一码付 (merge)
    """

    def __init__(self, merchant_id: str, merchant_key: str):
        """
        初始化支付网关

        Args:
            merchant_id: 商户号
            merchant_key: 商户密钥
        """
        self.merchant_id = merchant_id
        self.merchant_key = merchant_key
        self.gateway_url = 'https://api.ltzf.cn'

    def _generate_sign(self, params: Dict[str, Any]) -> str:
        """
        生成签名（MD5方式，与微信支付V2一致）

        Args:
            params: 待签名参数

        Returns:
            签名字符串（大写）
        """
        # 过滤空值和sign字段
        filtered = {k: v for k, v in params.items()
                   if v is not None and v != '' and k != 'sign'}

        # 按key排序
        sorted_params = sorted(filtered.items())

        # 拼接字符串
        sign_str = '&'.join([f'{k}={v}' for k, v in sorted_params])

        # 添加密钥
        sign_str += f'&key={self.merchant_key}'

        # MD5签名并转大写
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()

    def create_wxpay_native(
        self,
        out_trade_no: str,
        total_fee: str,
        body: str,
        notify_url: str,
        attach: str = None,
        time_expire: str = None
    ) -> Dict[str, Any]:
        """
        创建微信扫码支付订单

        Args:
            out_trade_no: 商户订单号
            total_fee: 支付金额（字符串格式，如 "0.01"）
            body: 商品描述
            notify_url: 支付通知地址
            attach: 附加数据
            time_expire: 订单失效时间（如 "5m", "1h"）

        Returns:
            支付信息字典
        """
        params = {
            'mch_id': self.merchant_id,
            'out_trade_no': out_trade_no,
            'total_fee': total_fee,
            'body': body,
            'timestamp': str(int(time.time())),
            'notify_url': notify_url,
            'attach': attach,
            'time_expire': time_expire
        }

        # 生成签名
        params['sign'] = self._generate_sign(params)

        try:
            response = requests.post(
                f'{self.gateway_url}/api/wxpay/native',
                data=params,
                timeout=30
            )
            result = response.json()

            if result.get('code') == 0:
                return {
                    'success': True,
                    'order_id': out_trade_no,
                    'code_url': result['data'].get('code_url'),  # 微信原生支付链接
                    'qr_code_url': result['data'].get('QRcode_url'),  # 蓝兔生成的二维码
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('msg', '创建订单失败'),
                    'raw_response': result
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }

    def create_alipay_native(
        self,
        out_trade_no: str,
        total_fee: str,
        body: str,
        notify_url: str,
        return_url: str = None,
        attach: str = None,
        time_expire: str = None
    ) -> Dict[str, Any]:
        """
        创建支付宝扫码支付订单

        Args:
            out_trade_no: 商户订单号
            total_fee: 支付金额（字符串格式，如 "0.01"）
            body: 商品描述
            notify_url: 支付通知地址
            return_url: 回跳地址
            attach: 附加数据
            time_expire: 订单失效时间（如 "5m", "1h"）

        Returns:
            支付信息字典
        """
        params = {
            'mch_id': self.merchant_id,
            'out_trade_no': out_trade_no,
            'total_fee': total_fee,
            'body': body,
            'timestamp': str(int(time.time())),
            'notify_url': notify_url,
            'return_url': return_url,
            'attach': attach,
            'time_expire': time_expire
        }

        # 生成签名
        params['sign'] = self._generate_sign(params)

        try:
            response = requests.post(
                f'{self.gateway_url}/api/alipay/native',
                data=params,
                timeout=30
            )
            result = response.json()

            if result.get('code') == 0:
                return {
                    'success': True,
                    'order_id': out_trade_no,
                    'qr_code_url': result.get('data'),  # 蓝兔生成的二维码链接
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('msg', '创建订单失败'),
                    'raw_response': result
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }

    def create_merge_native(
        self,
        out_trade_no: str,
        total_fee: str,
        body: str,
        notify_url: str,
        return_url: str = None,
        attach: str = None,
        time_expire: str = None
    ) -> Dict[str, Any]:
        """
        创建一码付订单（微信+支付宝通用）

        Args:
            out_trade_no: 商户订单号
            total_fee: 支付金额（字符串格式，如 "0.01"）
            body: 商品描述
            notify_url: 支付通知地址
            return_url: 回跳地址
            attach: 附加数据
            time_expire: 订单失效时间（如 "5m", "1h"）

        Returns:
            支付信息字典
        """
        params = {
            'mch_id': self.merchant_id,
            'out_trade_no': out_trade_no,
            'total_fee': total_fee,
            'body': body,
            'timestamp': str(int(time.time())),
            'notify_url': notify_url,
            'return_url': return_url,
            'attach': attach,
            'time_expire': time_expire
        }

        # 生成签名
        params['sign'] = self._generate_sign(params)

        try:
            response = requests.post(
                f'{self.gateway_url}/api/merge/native',
                data=params,
                timeout=30
            )
            result = response.json()

            if result.get('code') == 0:
                return {
                    'success': True,
                    'order_id': out_trade_no,
                    'qr_code_url': result.get('data'),  # 蓝兔生成的二维码链接
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('msg', '创建订单失败'),
                    'raw_response': result
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }

    def query_wxpay_order(self, out_trade_no: str) -> Dict[str, Any]:
        """
        查询微信支付订单状态

        Args:
            out_trade_no: 商户订单号

        Returns:
            订单状态信息
        """
        params = {
            'mch_id': self.merchant_id,
            'out_trade_no': out_trade_no,
            'timestamp': str(int(time.time()))
        }

        params['sign'] = self._generate_sign(params)

        try:
            response = requests.post(
                f'{self.gateway_url}/api/wxpay/get_pay_order',
                data=params,
                timeout=30
            )
            result = response.json()

            if result.get('code') == 0:
                data = result.get('data', {})
                return {
                    'success': True,
                    'status': 'paid' if data.get('pay_status') == 1 else 'unpaid',
                    'pay_status': data.get('pay_status'),
                    'pay_no': data.get('pay_no'),
                    'success_time': data.get('success_time'),
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

    def query_alipay_order(self, out_trade_no: str) -> Dict[str, Any]:
        """
        查询支付宝订单状态

        Args:
            out_trade_no: 商户订单号

        Returns:
            订单状态信息
        """
        params = {
            'mch_id': self.merchant_id,
            'out_trade_no': out_trade_no,
            'timestamp': str(int(time.time()))
        }

        params['sign'] = self._generate_sign(params)

        try:
            response = requests.post(
                f'{self.gateway_url}/api/alipay/get_pay_order',
                data=params,
                timeout=30
            )
            result = response.json()

            if result.get('code') == 0:
                data = result.get('data', {})
                return {
                    'success': True,
                    'status': 'paid' if data.get('pay_status') == 1 else 'unpaid',
                    'pay_status': data.get('pay_status'),
                    'pay_no': data.get('pay_no'),
                    'success_time': data.get('success_time'),
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


def create_lanzhi_payment(config: Dict[str, str] = None) -> LanzhiPaymentGateway:
    """
    创建蓝兔支付网关实例

    Args:
        config: 配置字典，包含 merchant_id, merchant_key

    Returns:
        支付网关实例
    """
    if config is None:
        # 从环境变量或配置文件读取
        import os
        config = {
            'merchant_id': os.getenv('LANZHI_MERCHANT_ID', ''),
            'merchant_key': os.getenv('LANZHI_MERCHANT_KEY', '')
        }

    return LanzhiPaymentGateway(
        merchant_id=config['merchant_id'],
        merchant_key=config['merchant_key']
    )

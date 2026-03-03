"""
随行付支付网关
官网: https://www.vbill.cn
费率: 约 0.38%-0.6%

优势:
- 持有央行支付牌照
- 支持个人/个体户/企业
- 费率较低
- 资金安全
"""
import requests
import hashlib
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime


class SuixingPayGateway:
    """
    随行付支付网关

    支持的支付方式：
    - 微信扫码支付 (wechat)
    - 支付宝扫码支付 (alipay)
    - 云闪付 (unionpay)
    """

    def __init__(
        self,
        mchid: str,           # 商户号
        mchkey: str,          # 商户密钥
        tid: str = '88888888',  # 终端号
        sign_type: str = 'MD5'   # 签名方式: MD5 或 RSA
    ):
        """
        初始化随行付网关

        Args:
            mchid: 商户号（随行付后台获取）
            mchkey: 商户密钥（随行付后台获取）
            tid: 终端号（默认 88888888）
            sign_type: 签名方式
        """
        self.mchid = mchid
        self.mchkey = mchkey
        self.tid = tid
        self.sign_type = sign_type
        self.gateway_url = 'https://api.suixingpay.com'

    def _generate_sign(self, params: Dict[str, Any]) -> str:
        """
        生成签名

        签名规则：
        1. 按参数名ASCII码从小到大排序
        2. 拼接成 key1=value1&key2=value2 格式
        3. 末尾追加 &key=商户密钥
        4. MD5 加密并转大写
        """
        # 过滤空值和sign字段
        filtered = {k: v for k, v in params.items()
                   if v is not None and v != '' and k != 'sign' and k != 'sign_type'}

        # 按key排序
        sorted_params = sorted(filtered.items())

        # 拼接字符串
        sign_str = '&'.join([f'{k}={v}' for k, v in sorted_params])

        # 添加密钥
        sign_str += f'&key={self.mchkey}'

        # MD5签名并转大写
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()

    def create_order(
        self,
        out_trade_no: str,
        total_fee: int,
        body: str,
        pay_type: str = 'wechat',
        notify_url: str = None,
        return_url: str = None,
        attach: str = None
    ) -> Dict[str, Any]:
        """
        创建支付订单

        Args:
            out_trade_no: 商户订单号
            total_fee: 金额（单位：分）
            body: 商品描述
            pay_type: 支付类型 (wechat/alipay/unionpay)
            notify_url: 异步通知地址
            return_url: 同步返回地址
            attach: 附加数据

        Returns:
            {
                'success': True/False,
                'qr_code': '二维码链接',
                'code_url': '原生支付链接',
                'order_no': '平台订单号',
                'error': '错误信息'
            }
        """
        # 公共参数
        params = {
            'mchid': self.mchid,
            'mchorderno': out_trade_no,
            'paytype': pay_type,
            'amount': total_fee,
            'client_ip': '127.0.0.1',
            'datetime': datetime.now().strftime('%Y%m%d%H%M%S'),
            'tid': self.tid,
            'sign_type': self.sign_type,
        }

        # 可选参数
        if body:
            params['goodsname'] = body[:64]  # 限制长度
        if notify_url:
            params['notifyurl'] = notify_url
        if return_url:
            params['returnurl'] = return_url
        if attach:
            params['attach'] = attach[:128]  # 限制长度

        # 生成签名
        params['sign'] = self._generate_sign(params)

        try:
            # 根据支付类型选择接口
            if pay_type == 'wechat':
                url = f'{self.gateway_url}/qr/qutoPay'
            elif pay_type == 'alipay':
                url = f'{self.gateway_url}/qr/aliPay'
            else:
                url = f'{self.gateway_url}/qr/unionPay'

            response = requests.post(
                url,
                data=params,
                timeout=30,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )

            result = response.json()

            # 处理响应
            if result.get('respCode') == '00' or result.get('returnCode') == 'SUCCESS':
                return {
                    'success': True,
                    'order_no': out_trade_no,
                    'platform_order_no': result.get('orderno') or result.get('orderNo'),
                    'qr_code': result.get('codeimg') or result.get('qrCode'),  # 二维码图片URL
                    'code_url': result.get('codeurl') or result.get('codeUrl'),  # 支付链接
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('respMsg') or result.get('returnMsg') or '创建订单失败',
                    'error_code': result.get('respCode'),
                    'raw_response': result
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'请求异常: {str(e)}'
            }

    def query_order(self, out_trade_no: str) -> Dict[str, Any]:
        """
        查询订单状态

        Args:
            out_trade_no: 商户订单号

        Returns:
            {
                'success': True/False,
                'status': 'SUCCESS'/'PROCESSING'/'FAILED'/'CLOSED',
                'transaction_id': '平台订单号',
                'amount': 100,  # 单位：分
                'error': '错误信息'
            }
        """
        params = {
            'mchid': self.mchid,
            'mchorderno': out_trade_no,
            'datetime': datetime.now().strftime('%Y%m%d%H%M%S'),
            'sign_type': self.sign_type,
        }

        params['sign'] = self._generate_sign(params)

        try:
            url = f'{self.gateway_url}/trade/query'
            response = requests.post(
                url,
                data=params,
                timeout=30,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )

            result = response.json()

            if result.get('respCode') == '00':
                return {
                    'success': True,
                    'order_no': out_trade_no,
                    'status': result.get('orderStatus'),
                    'transaction_id': result.get('orderno'),
                    'amount': int(result.get('amount', 0)),
                    'pay_time': result.get('paydatetime'),
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('respMsg') or '查询失败',
                    'raw_response': result
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'请求异常: {str(e)}'
            }

    def close_order(self, out_trade_no: str) -> Dict[str, Any]:
        """
        关闭订单

        Args:
            out_trade_no: 商户订单号
        """
        params = {
            'mchid': self.mchid,
            'mchorderno': out_trade_no,
            'datetime': datetime.now().strftime('%Y%m%d%H%M%S'),
            'sign_type': self.sign_type,
        }

        params['sign'] = self._generate_sign(params)

        try:
            url = f'{self.gateway_url}/trade/close'
            response = requests.post(
                url,
                data=params,
                timeout=30,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )

            result = response.json()

            if result.get('respCode') == '00':
                return {
                    'success': True,
                    'message': '订单已关闭',
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('respMsg') or '关闭失败',
                    'raw_response': result
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'请求异常: {str(e)}'
            }

    def refund(self, out_trade_no: str, refund_no: str, total_fee: int, refund_fee: int, reason: str = None) -> Dict[str, Any]:
        """
        申请退款

        Args:
            out_trade_no: 商户订单号
            refund_no: 商户退款单号
            total_fee: 订单总金额（分）
            refund_fee: 退款金额（分）
            reason: 退款原因

        Returns:
            {
                'success': True/False,
                'refund_no': '平台退款单号',
                'error': '错误信息'
            }
        """
        params = {
            'mchid': self.mchid,
            'mchrefundno': refund_no,
            'mchorderno': out_trade_no,
            'amount': total_fee,
            'refundamount': refund_fee,
            'datetime': datetime.now().strftime('%Y%m%d%H%M%S'),
            'sign_type': self.sign_type,
        }

        if reason:
            params['refundreason'] = reason[:128]

        params['sign'] = self._generate_sign(params)

        try:
            url = f'{self.gateway_url}/trade/refund'
            response = requests.post(
                url,
                data=params,
                timeout=30,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )

            result = response.json()

            if result.get('respCode') == '00':
                return {
                    'success': True,
                    'order_no': out_trade_no,
                    'refund_no': refund_no,
                    'refund_id': result.get('refundorderno'),
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('respMsg') or '退款失败',
                    'raw_response': result
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'请求异常: {str(e)}'
            }

    def verify_notify(self, data: Dict[str, Any]) -> bool:
        """
        验证异步通知签名

        Args:
            data: 回调数据

        Returns:
            True/False
        """
        received_sign = data.get('sign')
        if not received_sign:
            return False

        calculated_sign = self._generate_sign(data)
        return received_sign == calculated_sign


def create_suixing_payment(config: Dict[str, str] = None) -> SuixingPayGateway:
    """
    创建随行付支付网关实例

    Args:
        config: 配置字典

    Returns:
        支付网关实例
    """
    if config is None:
        import os
        config = {
            'mchid': os.getenv('SUIXING_PAY_MCHID', ''),
            'mchkey': os.getenv('SUIXING_PAY_MCHKEY', ''),
            'tid': os.getenv('SUIXING_PAY_TID', '88888888'),
            'sign_type': os.getenv('SUIXING_PAY_SIGN_TYPE', 'MD5'),
        }

    return SuixingPayGateway(
        mchid=config['mchid'],
        mchkey=config['mchkey'],
        tid=config.get('tid', '88888888'),
        sign_type=config.get('sign_type', 'MD5')
    )


# 测试代码
if __name__ == '__main__':
    # 测试配置（替换为真实配置）
    config = {
        'mchid': 'YOUR_MCHID',
        'mchkey': 'YOUR_MCHKEY',
        'tid': '88888888',
    }

    gateway = create_suixing_payment(config)

    # 测试创建订单
    result = gateway.create_order(
        out_trade_no='TEST' + datetime.now().strftime('%Y%m%d%H%M%S'),
        total_fee=100,  # 1元 = 100分
        body='测试商品',
        pay_type='wechat',
        notify_url='https://your-domain.com/api/payment/notify/suixing'
    )

    print("创建订单结果：")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试查询订单
    if result.get('success'):
        query_result = gateway.query_order(result['order_no'])
        print("\n查询订单结果：")
        print(json.dumps(query_result, indent=2, ensure_ascii=False))

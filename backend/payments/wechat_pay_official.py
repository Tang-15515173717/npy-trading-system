"""
微信官方支��接口示例
需要企业资质才能申请
文档: https://pay.weixin.qq.com/wiki/doc/apiv3/index.shtml
"""
import requests
import hashlib
import hmac
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime
import xml.etree.ElementTree as ET


class WechatPayOfficial:
    """
    微信官方支付 V3 版本
    需要企业资质：营业执照、对公账户、ICP备案
    """

    def __init__(
        self,
        appid: str,           # 微信公众号/小程序APPID
        mchid: str,           # 商户号
        api_key: str,         # API密钥（V2版本使用）
        api_key_v3: str,      # API密钥（V3版本使用）
        cert_path: str,       # 商户证书路径
        key_path: str,        # 商户证书私钥路径
        notify_url: str       # 异步通知地址
    ):
        self.appid = appid
        self.mchid = mchid
        self.api_key = api_key
        self.api_key_v3 = api_key_v3
        self.cert_path = cert_path
        self.key_path = key_path
        self.notify_url = notify_url

        # API地址
        self.api_url = 'https://api.mch.weixin.qq.com'

    def create_native_pay_v2(
        self,
        out_trade_no: str,
        total_fee: int,
        body: str,
        attach: str = None,
        time_expire: str = None
    ) -> Dict[str, Any]:
        """
        创建微信Native支付订单（V2版本）

        Args:
            out_trade_no: 商户订单号
            total_fee: 支付金额（单位：分）
            body: 商品描述
            attach: 附加数据
            time_expire: 订单失效时间

        Returns:
            支付信息字典
        """
        params = {
            'appid': self.appid,
            'mch_id': self.mchid,
            'nonce_str': self._generate_nonce_str(),
            'body': body,
            'out_trade_no': out_trade_no,
            'total_fee': total_fee,
            'spbill_create_ip': '127.0.0.1',
            'notify_url': self.notify_url,
            'trade_type': 'NATIVE',
            'attach': attach,
            'time_expire': time_expire
        }

        # 生成签名
        params['sign'] = self._generate_sign_v2(params)

        # 转换为XML
        xml_data = self._dict_to_xml(params)

        try:
            response = requests.post(
                f'{self.api_url}/pay/unifiedorder',
                data=xml_data.encode('utf-8'),
                headers={'Content-Type': 'application/xml'},
                timeout=30
            )

            # 解析XML响应
            result = self._xml_to_dict(response.text)

            if result.get('return_code') == 'SUCCESS' and result.get('result_code') == 'SUCCESS':
                return {
                    'success': True,
                    'order_id': out_trade_no,
                    'code_url': result.get('code_url'),  # 二维码链接
                    'prepay_id': result.get('prepay_id'),
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('return_msg') or result.get('err_code_des'),
                    'raw_response': result
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }

    def create_native_pay_v3(
        self,
        out_trade_no: str,
        total_amount: int,
        description: str,
        attach: str = None,
        time_expire: str = None
    ) -> Dict[str, Any]:
        """
        创建微信Native支付订单（V3版本）

        Args:
            out_trade_no: 商户订单号
            total_amount: 支付金额（单位：分）
            description: 商品描述
            attach: 附加数据
            time_expire: 订单失效时间（RFC3339格式）

        Returns:
            支付信息字典
        """
        url = f'{self.api_url}/v3/pay/transactions/native'

        payload = {
            'appid': self.appid,
            'mchid': self.mchid,
            'description': description,
            'out_trade_no': out_trade_no,
            'notify_url': self.notify_url,
            'amount': {
                'total': total_amount,
                'currency': 'CNY'
            }
        }

        if attach:
            payload['attach'] = attach
        if time_expire:
            payload['time_expire'] = time_expire

        # 生成签名
        timestamp = str(int(time.time()))
        nonce_str = self._generate_nonce_str()
        signature = self._generate_sign_v3(
            'POST',
            url,
            timestamp,
            nonce_str,
            json.dumps(payload)
        )

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mchid}",nonce_str="{nonce_str}",timestamp="{timestamp}",serial_no="XXX",signature="{signature}"'
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            result = response.json()

            if response.status_code == 200:
                return {
                    'success': True,
                    'order_id': out_trade_no,
                    'code_url': result.get('code_url'),
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('message'),
                    'raw_response': result
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }

    def query_order_v2(self, out_trade_no: str) -> Dict[str, Any]:
        """查询订单（V2版本）"""
        params = {
            'appid': self.appid,
            'mch_id': self.mchid,
            'out_trade_no': out_trade_no,
            'nonce_str': self._generate_nonce_str()
        }

        params['sign'] = self._generate_sign_v2(params)
        xml_data = self._dict_to_xml(params)

        try:
            response = requests.post(
                f'{self.api_url}/pay/orderquery',
                data=xml_data.encode('utf-8'),
                headers={'Content-Type': 'application/xml'},
                timeout=30
            )

            result = self._xml_to_dict(response.text)

            if result.get('return_code') == 'SUCCESS' and result.get('result_code') == 'SUCCESS':
                return {
                    'success': True,
                    'status': 'paid' if result.get('trade_state') == 'SUCCESS' else 'unpaid',
                    'trade_state': result.get('trade_state'),
                    'transaction_id': result.get('transaction_id'),
                    'total_fee': result.get('total_fee'),
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('return_msg') or result.get('err_code_des'),
                    'raw_response': result
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }

    def verify_notify_v2(self, data: dict) -> bool:
        """验证V2回调签名"""
        received_sign = data.pop('sign', None)
        if not received_sign:
            return False

        calculated_sign = self._generate_sign_v2(data)
        return received_sign == calculated_sign

    def _generate_sign_v2(self, params: Dict[str, Any]) -> str:
        """
        生成V2签名（MD5方式）

        V2签名算法：
        1. 参数按ASCII码排序
        2. 拼接成 key1=value1&key2=value2
        3. 末尾追加 &key=API密钥
        4. MD5加密并转大写
        """
        # 过滤空值和sign字段
        filtered = {k: v for k, v in params.items()
                   if v is not None and v != '' and k != 'sign'}

        # 按key排序
        sorted_params = sorted(filtered.items())

        # 拼接字符串
        sign_str = '&'.join([f'{k}={v}' for k, v in sorted_params])

        # 添加密钥
        sign_str += f'&key={self.api_key}'

        # MD5签名并转大写
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()

    def _generate_sign_v3(
        self,
        method: str,
        url: str,
        timestamp: str,
        nonce_str: str,
        body: str
    ) -> str:
        """
        生成V3签名（SHA256-RSA方式）

        V3签名算法：
        1. 构造签名串：HTTP方法\nURL\n时间戳\n随机串\n请求体\n
        2. 使用商户私钥对签名串进行SHA256-RSA2048签名
        3. 对签名结果进行Base64编码
        """
        # 构造签名串
        sign_str = f"{method}\n{url}\n{timestamp}\n{nonce_str}\n{body}\n"

        # 使用商户私钥签名（需要加载证书）
        # 这里简化了实际实现
        # 实际需要使用 M2Crypto 或 cryptography 库加载证书
        import base64
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend

        # 加载商户私钥
        with open(self.key_path, 'rb') as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )

        # 签名
        signature = private_key.sign(
            sign_str.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # Base64编码
        return base64.b64encode(signature).decode('utf-8')

    def _generate_nonce_str(self) -> str:
        """生成随机字符串"""
        import random
        import string
        return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

    def _dict_to_xml(self, data: Dict[str, Any]) -> str:
        """字典转XML"""
        xml = '<xml>'
        for k, v in data.items():
            xml += f'<{k}>{v}</{k}>'
        xml += '</xml>'
        return xml

    def _xml_to_dict(self, xml_str: str) -> Dict[str, Any]:
        """XML转字典"""
        root = ET.fromstring(xml_str)
        return {child.tag: child.text for child in root}


# 使用示例
if __name__ == '__main__':
    # 初始化（需要从微信支付后台获取）
    wechat_pay = WechatPayOfficial(
        appid='wx1234567890abcdef',
        mchid='1234567890',
        api_key='abc123...',
        api_key_v3='def456...',
        cert_path='/path/to/cert.pem',
        key_path='/path/to/key.pem',
        notify_url='https://your-domain.com/api/payment/notify/wechat'
    )

    # 创建订单
    result = wechat_pay.create_native_pay_v2(
        out_trade_no='ORDER20250302123456',
        total_fee=1900,  # 19.00元 = 1900分
        body='StockQuant Pro 基础版'
    )

    print(result)

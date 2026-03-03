"""
支付API - 提供支付订单创建、查询、回调等功能
"""
from flask import Blueprint, request, jsonify, g, current_app
from utils.auth_decorator import token_required, get_current_tenant_id, get_current_user_id
from utils.database import db
from models.payment import PaymentOrder, PaymentRecord
from models.user import Tenant
from utils.plan_config import PLAN_PRICES, PLAN_LIMITS
from payments.lanzhi_payment import create_lanzhi_payment
from payments.wechat_pay_simple import create_wechat_payment
from payments.suixing_pay import create_suixing_payment
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

payment_bp = Blueprint('payment', __name__, url_prefix='/api/payment')


@payment_bp.route('/create-order', methods=['POST'])
@token_required
def create_payment_order():
    """
    创建支付订单

    Request Body:
        {
            "plan": "basic" | "pro" | "enterprise",
            "pay_type": "alipay" | "wechat"
        }

    Response:
        {
            "success": true,
            "data": {
                "order_no": "订单号",
                "amount": 1900,
                "amount_yuan": 19.00,
                "pay_url": "支付链接",
                "qr_code": "二维码内容"
            }
        }
    """
    try:
        data = request.get_json()
        plan = data.get('plan')
        pay_type = data.get('pay_type', 'wechat')  # 默认使用微信

        # 验证套餐类型
        if plan not in PLAN_PRICES:
            return jsonify({
                'success': False,
                'error': '无效的套餐类型'
            }), 400

        # 验证支付类型
        if pay_type not in ['alipay', 'wechat']:
            return jsonify({
                'success': False,
                'error': '无效的支付类型'
            }), 400

        # 获取价格
        price_yuan = PLAN_PRICES[plan]
        price_fen = int(price_yuan * 100)

        # 生成订单号
        order_no = f"VNPY{datetime.now().strftime('%Y%m%d%H%M%S')}{get_current_user_id()}{plan[:2].upper()}"

        # 创建订单记录
        order = PaymentOrder(
            order_no=order_no,
            tenant_id=get_current_tenant_id(),
            user_id=get_current_user_id(),
            plan_type=plan,
            amount=price_fen,
            body=f"StockQuant Pro {PLAN_LIMITS[plan]['name']} - 1个月",
            pay_type=pay_type,
            status='pending'
        )
        db.session.add(order)
        db.session.commit()

        # 调用支付网关创建支付
        # 根据配置选择支付方式
        import os
        payment_provider = os.getenv('PAYMENT_PROVIDER', 'lanzhi')

        if payment_provider == 'wechat_official':
            # 使用微信官方支付
            from payments.wechat_pay_simple import create_wechat_payment
            gateway = create_wechat_payment()
            result = gateway.create_order(
                out_trade_no=order_no,
                total_fee=price_fen,  # 微信支付单位是分
                body=order.body,
                attach=plan,
                time_expire=(datetime.now() + timedelta(minutes=30)).strftime('%Y%m%d%H%M%S')
            )

        elif payment_provider == 'suixing':
            # 使用随行付支付
            from payments.suixing_pay import create_suixing_payment
            gateway = create_suixing_payment()
            notify_url = f"{request.host_url}api/payment/notify/suixing"

            # 随行付的支付类型映射
            suixing_pay_type = 'wechat' if pay_type == 'wechat' else 'alipay'

            result = gateway.create_order(
                out_trade_no=order_no,
                total_fee=price_fen,  # 随行付单位是分
                body=order.body,
                pay_type=suixing_pay_type,
                notify_url=notify_url,
                attach=plan
            )

        else:
            # 使用蓝兔聚合支付（默认）
            gateway = create_lanzhi_payment()
            notify_url = f"{request.host_url}api/payment/notify/{pay_type}"
            return_url = f"{request.host_url}payment/result?order_no={order_no}"

            # 根据支付类型调用不同的方法
            if pay_type == 'wechat':
                result = gateway.create_wxpay_native(
                    out_trade_no=order_no,
                    total_fee=str(price_yuan),  # 蓝兔支付需要字符串格式的元
                    body=order.body,
                    notify_url=notify_url,
                    attach=plan,
                    time_expire="30m"
                )
            else:  # alipay
                result = gateway.create_alipay_native(
                    out_trade_no=order_no,
                    total_fee=str(price_yuan),  # 蓝兔支付需要字符串格式的元
                    body=order.body,
                    notify_url=notify_url,
                    return_url=return_url,
                    attach=plan,
                    time_expire="30m"
                )

        if result['success']:
            # 更新订单支付链接
            # 微信官方支付和蓝兔支付返回的字段不同
            qr_code = result.get('code_url') or result.get('qr_code_url')
            order.pay_url = qr_code
            db.session.commit()

            return jsonify({
                'success': True,
                'data': {
                    'order_no': order_no,
                    'plan': plan,
                    'plan_name': PLAN_LIMITS[plan]['name'],
                    'amount': price_fen,
                    'amount_yuan': price_yuan,
                    'pay_type': pay_type,
                    'qr_code': qr_code,
                    'code_url': result.get('code_url'),  # 微信原生支付链接
                    'qr_code_url': result.get('qr_code_url')  # 蓝兔生成的二维码
                }
            })
        else:
            order.status = 'failed'
            db.session.commit()
            return jsonify({
                'success': False,
                'error': result.get('error', '创建支付订单失败')
            }), 500

    except Exception as e:
        db.session.rollback()
        logger.error(f"创建支付订单失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@payment_bp.route('/order/<order_no>', methods=['GET'])
@token_required
def get_order(order_no):
    """
    查询订单状态

    Args:
        order_no: 订单号
    """
    try:
        order = PaymentOrder.query.filter_by(
            order_no=order_no,
            tenant_id=get_current_tenant_id()
        ).first()

        if not order:
            return jsonify({
                'success': False,
                'error': '订单不存在'
            }), 404

        # 如果订单未支付，主动查询支付网关
        if order.status == 'pending':
            import os
            payment_provider = os.getenv('PAYMENT_PROVIDER', 'lanzhi')

            if payment_provider == 'wechat_official':
                # 使用微信官方支付
                from payments.wechat_pay_simple import create_wechat_payment
                gateway = create_wechat_payment()
                result = gateway.query_order(order_no)

                if result['success'] and result['status'] == 'SUCCESS':
                    order.status = 'paid'
                    order.transaction_id = result.get('transaction_id')
                    order.paid_at = datetime.utcnow()
                    _activate_plan(order)
                    db.session.commit()

            elif payment_provider == 'suixing':
                # 使用随行付支付
                from payments.suixing_pay import create_suixing_payment
                gateway = create_suixing_payment()
                result = gateway.query_order(order_no)

                if result['success'] and result['status'] == 'SUCCESS':
                    order.status = 'paid'
                    order.transaction_id = result.get('transaction_id')
                    order.paid_at = datetime.utcnow()
                    _activate_plan(order)
                    db.session.commit()

            else:
                # 使用蓝兔聚合支付
                gateway = create_lanzhi_payment()

                # 根据支付类型调用不同的查询方法
                if order.pay_type == 'wechat':
                    result = gateway.query_wxpay_order(order_no)
                else:  # alipay
                    result = gateway.query_alipay_order(order_no)

                if result['success']:
                    # 更新订单状态
                    if result['status'] == 'paid':
                        order.status = 'paid'
                        order.transaction_id = result.get('pay_no')
                        order.paid_at = datetime.utcnow()
                        _activate_plan(order)
                        db.session.commit()

        return jsonify({
            'success': True,
            'data': order.to_dict()
        })

    except Exception as e:
        logger.error(f"查询订单失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@payment_bp.route('/orders', methods=['GET'])
@token_required
def get_orders():
    """
    获取当前用户的订单列表

    Query Params:
        status: 订单状态 (pending/paid/failed/closed)
        page: 页码
        page_size: 每页数量
    """
    try:
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))

        query = PaymentOrder.query.filter_by(
            tenant_id=get_current_tenant_id()
        )

        if status:
            query = query.filter_by(status=status)

        query = query.order_by(PaymentOrder.created_at.desc())
        pagination = query.paginate(page=page, per_page=page_size, error_out=False)

        return jsonify({
            'success': True,
            'data': {
                'orders': [order.to_dict() for order in pagination.items],
                'total': pagination.total,
                'page': page,
                'page_size': page_size,
                'pages': pagination.pages
            }
        })

    except Exception as e:
        logger.error(f"获取订单列表失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@payment_bp.route('/notify/<pay_type>', methods=['POST'])
def payment_notify(pay_type):
    """
    支付回调通知
    由支付网关调用，用于异步通知支付结果

    Args:
        pay_type: 支付类型 (alipay/wechat)
    """
    try:
        # 获取回调数据
        if pay_type == 'alipay':
            # 支付宝回调
            data = request.form.to_dict()
        else:
            # 微信回调
            data = request.json

        logger.info(f"收到支付回调: {pay_type}, data: {data}")

        # 验证签名
        import os
        payment_provider = os.getenv('PAYMENT_PROVIDER', 'lanzhi')

        if payment_provider == 'wechat_official':
            from payments.wechat_pay_simple import create_wechat_payment
            gateway = create_wechat_payment()
        elif payment_provider == 'suixing':
            from payments.suixing_pay import create_suixing_payment
            gateway = create_suixing_payment()
        else:
            gateway = create_lanzhi_payment()

        if not gateway.verify_notify(data.copy()):
            logger.warning("支付回调签名验证失败")
            return 'FAIL', 400

        # 获取订单信息
        order_no = data.get('out_trade_no')
        # 蓝兔支付使用 pay_no 作为交易流水号
        transaction_id = data.get('pay_no') or data.get('transaction_id')

        if not order_no:
            logger.warning("回调数据缺少订单号")
            return 'FAIL', 400

        # 查询订单
        order = PaymentOrder.query.filter_by(order_no=order_no).first()

        if not order:
            logger.warning(f"订单不存在: {order_no}")
            return 'FAIL', 404

        # 检查是否已处理
        if order.status == 'paid':
            logger.info(f"订单已处理: {order_no}")
            return 'SUCCESS', 200

        # 更新订单状态
        order.status = 'paid'
        order.transaction_id = transaction_id
        order.paid_at = datetime.utcnow()

        # 激活套餐
        _activate_plan(order)

        # 创建支付记录
        record = PaymentRecord(
            order_no=order_no,
            tenant_id=order.tenant_id,
            user_id=order.user_id,
            pay_type=order.pay_type,
            transaction_id=transaction_id,
            amount=order.amount,
            plan_type=order.plan_type,
            notify_data=str(data)
        )
        db.session.add(record)

        db.session.commit()

        logger.info(f"订单支付成功: {order_no}")

        return 'SUCCESS', 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"处理支付回调失败: {str(e)}", exc_info=True)
        return 'FAIL', 500


@payment_bp.route('/verify-payment', methods=['POST'])
@token_required
def verify_payment():
    """
    验证支付并激活套餐
    用于前端轮询检查支付状态
    """
    try:
        data = request.get_json()
        order_no = data.get('order_no')

        if not order_no:
            return jsonify({
                'success': False,
                'error': '缺少订单号'
            }), 400

        order = PaymentOrder.query.filter_by(
            order_no=order_no,
            tenant_id=get_current_tenant_id()
        ).first()

        if not order:
            return jsonify({
                'success': False,
                'error': '订单不存在'
            }), 404

        # 主动查询支付网关
        if order.status == 'pending':
            import os
            payment_provider = os.getenv('PAYMENT_PROVIDER', 'lanzhi')

            if payment_provider == 'wechat_official':
                # 使用微信官方支付
                from payments.wechat_pay_simple import create_wechat_payment
                gateway = create_wechat_payment()
                result = gateway.query_order(order_no)

                if result['success'] and result['status'] == 'SUCCESS':
                    order.status = 'paid'
                    order.transaction_id = result.get('transaction_id')
                    order.paid_at = datetime.utcnow()
                    _activate_plan(order)
                    db.session.commit()

            elif payment_provider == 'suixing':
                # 使用随行付支付
                from payments.suixing_pay import create_suixing_payment
                gateway = create_suixing_payment()
                result = gateway.query_order(order_no)

                if result['success'] and result['status'] == 'SUCCESS':
                    order.status = 'paid'
                    order.transaction_id = result.get('transaction_id')
                    order.paid_at = datetime.utcnow()
                    _activate_plan(order)
                    db.session.commit()

            else:
                # 使用蓝兔聚合支付
                gateway = create_lanzhi_payment()

                # 根据支付类型调用不同的查询方法
                if order.pay_type == 'wechat':
                    result = gateway.query_wxpay_order(order_no)
                else:  # alipay
                    result = gateway.query_alipay_order(order_no)

                if result['success'] and result['status'] == 'paid':
                    order.status = 'paid'
                    order.transaction_id = result.get('pay_no')
                    order.paid_at = datetime.utcnow()
                    _activate_plan(order)
                    db.session.commit()

        return jsonify({
            'success': True,
            'data': {
                'order_no': order_no,
                'status': order.status,
                'is_paid': order.status == 'paid',
                'plan_type': order.plan_type
            }
        })

    except Exception as e:
        logger.error(f"验证支付失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _activate_plan(order: PaymentOrder):
    """
    激活套餐

    Args:
        order: 支付订单
    """
    from utils.subscription_limits import get_plan_limits

    tenant = Tenant.query.get(order.tenant_id)

    if tenant:
        # 更新套餐
        tenant.plan = order.plan_type
        limits = get_plan_limits(order.plan_type)
        tenant.max_strategies = limits['max_strategies']
        tenant.max_backtests_per_day = limits['max_backtests_per_day']
        tenant.updated_at = datetime.utcnow()

        logger.info(f"租户 {order.tenant_id} 套餐已激活为 {order.plan_type}")

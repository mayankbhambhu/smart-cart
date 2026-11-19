"""Checkout, payment confirmation, digital receipts and order history."""
import io
import json
import logging

import qrcode
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

from app.api.routes.cart import active_cart
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Order, OrderStatus, Store, User
from app.models._mixins import utcnow
from app.schemas import CheckoutIn, PaymentConfirmIn
from app.services import payments
from app.services.orders import create_order_from_cart, mark_paid, receipt_code

router = APIRouter(tags=["checkout & orders"])
log = logging.getLogger("orders")


def order_dict(db: Session, o: Order, with_code: bool = True) -> dict:
    store = db.get(Store, o.store_id)
    return {
        "id": o.id, "number": o.number, "store_id": o.store_id, "store_name": store.name if store else "",
        "fulfilment": o.fulfilment, "status": o.status, "subtotal": o.subtotal, "discount": o.discount,
        "delivery_fee": o.delivery_fee, "tax": o.tax, "total": o.total, "currency": settings.CURRENCY,
        "delivery_address": o.delivery_address, "pickup_slot": o.pickup_slot, "payment_method": o.payment_method,
        "payment_provider": o.payment_provider, "paid_at": o.paid_at, "created_at": o.created_at,
        "exit_verified_at": o.exit_verified_at,
        "receipt_code": receipt_code(o) if with_code else None,
        "items": [{"product_id": i.product_id, "name": i.name, "quantity": i.quantity, "unit_price": i.unit_price,
                   "line_total": round(i.unit_price * i.quantity, 2),
                   "location": f"Aisle {i.aisle}, Row {i.row}" if i.aisle else None} for i in o.items],
    }


def _own_order(db: Session, order_id: int, user: User) -> Order:
    o = db.query(Order).options(selectinload(Order.items)).filter_by(id=order_id).first()
    if not o or o.user_id != user.id:
        raise HTTPException(404, "Order not found")
    return o


@router.post("/checkout")
def checkout(data: CheckoutIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """One-tap checkout: freezes the cart into an order and opens a payment with the gateway."""
    cart = active_cart(db, user)
    order = create_order_from_cart(db, cart, data.delivery_address or user.default_address, data.pickup_slot)
    order.payment_method = data.payment_method
    order.payment_provider = payments.provider_for(data.payment_method)
    intent = payments.create_intent(order, data.payment_method, user.email)
    order.payment_ref = intent["reference"]
    db.commit()
    return {"order": order_dict(db, order, with_code=False), "payment": intent}


@router.post("/payments/confirm")
def confirm_payment(data: PaymentConfirmIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Client calls this after the payment sheet / UPI app / PayPal returns. The server verifies
    with the gateway before issuing the exit receipt."""
    order = _own_order(db, data.order_id, user)
    if order.status == OrderStatus.PENDING_PAYMENT.value:
        if not payments.verify_payment(order, data.model_dump()):
            raise HTTPException(402, "Payment not completed yet")
        mark_paid(db, order)
        db.commit()
    return order_dict(db, order)


@router.post("/payments/stripe/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, stripe_signature: str = Header(None), db: Session = Depends(get_db)):
    import stripe

    body = await request.body()
    try:
        event = stripe.Webhook.construct_event(body, stripe_signature, settings.STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Bad signature")
    if event["type"] == "payment_intent.succeeded":
        ref = event["data"]["object"]["id"]
        order = db.query(Order).filter_by(payment_ref=ref).first()
        if order:
            mark_paid(db, order)
            db.commit()
    return {"received": True}


@router.post("/payments/razorpay/webhook", include_in_schema=False)
async def razorpay_webhook(request: Request, x_razorpay_signature: str = Header(None), db: Session = Depends(get_db)):
    import hashlib
    import hmac

    body = await request.body()
    expected = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not x_razorpay_signature or not hmac.compare_digest(expected, x_razorpay_signature):
        raise HTTPException(400, "Bad signature")
    payload = json.loads(body)
    if payload.get("event") == "payment_link.paid":
        ref = payload["payload"]["payment_link"]["entity"]["id"]
        order = db.query(Order).filter_by(payment_ref=ref).first()
        if order:
            mark_paid(db, order)
            db.commit()
    return {"received": True}


@router.get("/orders")
def my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(Order).options(selectinload(Order.items))
            .filter(Order.user_id == user.id, Order.status != OrderStatus.PENDING_PAYMENT.value)
            .order_by(Order.id.desc()).limit(100).all())
    return [order_dict(db, o) for o in rows]


@router.get("/orders/{order_id}")
def get_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return order_dict(db, _own_order(db, order_id, user))


@router.get("/orders/{order_id}/receipt.png")
def receipt_qr(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The digital receipt barcode (QR) scanned at the exit gate."""
    order = _own_order(db, order_id, user)
    code = receipt_code(order)
    if not code:
        raise HTTPException(409, "Order is not paid yet")
    img = qrcode.make(code, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = _own_order(db, order_id, user)
    if order.status not in (OrderStatus.PREPARING.value, OrderStatus.PENDING_PAYMENT.value):
        raise HTTPException(409, "This order can no longer be cancelled")
    from app.services.inventory import adjust_stock

    if order.status == OrderStatus.PREPARING.value:
        for it in order.items:
            adjust_stock(db, order.store_id, it.product_id, it.quantity)
        payments.refund(order)
    order.status = OrderStatus.CANCELLED.value
    order.updated_at = utcnow()
    db.commit()
    return order_dict(db, order)

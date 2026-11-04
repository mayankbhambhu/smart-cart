"""Order lifecycle: cart -> order -> paid -> fulfilled. Shared by all payment providers."""
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.realtime import hub
from app.core.security import make_receipt_code
from app.models import Cart, Inventory, Order, OrderItem, OrderStatus, Role
from app.models._mixins import utcnow
from app.services.inventory import adjust_stock
from app.services.notify import notify, notify_roles
from app.services.pricing import quote_cart


def _order_number() -> str:
    return "FF" + utcnow().strftime("%y%m%d") + secrets.token_hex(3).upper()


def create_order_from_cart(db: Session, cart: Cart, address: str | None, pickup_slot) -> Order:
    if not cart.items:
        raise HTTPException(400, "Your cart is empty")
    if cart.mode == "delivery" and not address:
        raise HTTPException(400, "A delivery address is required")
    if cart.mode == "pickup" and not pickup_slot:
        raise HTTPException(400, "Choose a pickup slot")

    # Drop any previous unpaid order for this cart (e.g. user went back and changed items)
    for stale in db.query(Order).filter_by(user_id=cart.user_id, status=OrderStatus.PENDING_PAYMENT.value).all():
        db.delete(stale)

    q = quote_cart(db, cart)
    order = Order(
        number=_order_number(), user_id=cart.user_id, store_id=cart.store_id, fulfilment=cart.mode,
        subtotal=q.subtotal, discount=q.discount, delivery_fee=q.delivery_fee, tax=q.tax, total=q.total,
        cost_total=q.cost_total, offer_id=q.offer.id if q.offer else None,
        delivery_address=address if cart.mode == "delivery" else None,
        pickup_slot=pickup_slot if cart.mode == "pickup" else None,
    )
    locs = {i.product_id: i for i in db.query(Inventory).filter(
        Inventory.store_id == cart.store_id, Inventory.product_id.in_([c.product_id for c in cart.items]))}
    for it in cart.items:
        inv = locs.get(it.product_id)
        if cart.mode != "instore" and (not inv or inv.quantity < it.quantity):
            raise HTTPException(409, f"{it.product.name}: only {inv.quantity if inv else 0} left")
        order.items.append(OrderItem(
            product_id=it.product_id, name=it.product.name, quantity=it.quantity, unit_price=it.unit_price,
            unit_cost=it.product.cost_price, aisle=inv.aisle if inv else None, row=inv.row if inv else None))
    db.add(order)
    db.flush()
    return order


def mark_paid(db: Session, order: Order) -> Order:
    if order.status != OrderStatus.PENDING_PAYMENT.value:
        return order  # idempotent (webhook + client confirm can both arrive)
    order.paid_at = utcnow()
    order.receipt_nonce = secrets.token_hex(8)
    if order.fulfilment == "instore":
        order.status = OrderStatus.PAID.value  # goods already in the shopper's smart cart
    else:
        order.status = OrderStatus.PREPARING.value
        for it in order.items:  # delivery/pickup stock is taken at payment time
            adjust_stock(db, order.store_id, it.product_id, -it.quantity)

    cart = db.query(Cart).filter_by(user_id=order.user_id, status="active").first()
    if cart:
        cart.status = "checked_out"

    notify(db, order.user_id, "order", f"Payment received — {order.number}",
           "Show your digital receipt at the exit gate." if order.fulfilment == "instore"
           else "We're preparing your order.", link=f"/orders/{order.id}")
    if order.fulfilment != "instore":
        notify_roles(db, order.store_id, [Role.FLOOR_MANAGER], "order",
                     f"New {order.fulfilment} order {order.number}", f"{len(order.items)} items, ₹{order.total:.2f}")
    hub.publish(f"store:{order.store_id}", "order_paid",
                {"order_id": order.id, "number": order.number, "total": order.total, "fulfilment": order.fulfilment})
    return order


def receipt_code(order: Order) -> str | None:
    return make_receipt_code(order.id, order.receipt_nonce) if order.receipt_nonce else None

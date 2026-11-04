"""Basket pricing: subtotal, offers, delivery fee and GST."""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Cart, Offer
from app.models._mixins import utcnow


@dataclass
class Quote:
    subtotal: float
    discount: float
    delivery_fee: float
    tax: float
    total: float
    cost_total: float
    offer: Offer | None
    offer_message: str | None = None

    def as_dict(self) -> dict:
        return {
            "subtotal": self.subtotal, "discount": self.discount, "delivery_fee": self.delivery_fee,
            "tax": self.tax, "total": self.total, "currency": settings.CURRENCY,
            "offer_code": self.offer.code if self.offer else None, "offer_message": self.offer_message,
        }


def find_offer(db: Session, code: str | None, store_id: int) -> Offer | None:
    if not code:
        return None
    now = utcnow()
    offer = db.query(Offer).filter(Offer.code == code.upper(), Offer.is_active.is_(True)).first()
    if not offer or offer.starts_at > now or (offer.ends_at and offer.ends_at < now):
        return None
    if offer.store_id not in (None, store_id):
        return None
    return offer


def quote_cart(db: Session, cart: Cart) -> Quote:
    subtotal = sum(i.unit_price * i.quantity for i in cart.items)
    cost = sum(i.product.cost_price * i.quantity for i in cart.items)
    offer = find_offer(db, cart.offer_code, cart.store_id)
    discount, msg = 0.0, None
    if cart.offer_code and not offer:
        msg = "This offer code is invalid or expired"
    elif offer:
        eligible = subtotal if offer.category_id is None else sum(
            i.unit_price * i.quantity for i in cart.items if i.product.category_id == offer.category_id)
        if subtotal < offer.min_order:
            msg, offer = f"Add ₹{offer.min_order - subtotal:.0f} more to use {offer.code}", None
        else:
            discount = min(eligible * offer.discount_percent / 100, offer.max_discount)
            msg = f"{offer.title} applied"
    fee = 0.0
    if cart.mode == "delivery" and cart.items and subtotal - discount < settings.FREE_DELIVERY_ABOVE:
        fee = settings.DELIVERY_FEE
    taxable = max(subtotal - discount, 0)
    tax = round(taxable * settings.TAX_RATE, 2)
    total = round(taxable + tax + fee, 2)
    return Quote(round(subtotal, 2), round(discount, 2), fee, tax, total, round(cost, 2), offer, msg)

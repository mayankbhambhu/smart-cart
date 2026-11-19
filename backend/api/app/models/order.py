import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import Timestamped


class Fulfilment(str, enum.Enum):
    DELIVERY = "delivery"
    PICKUP = "pickup"
    INSTORE = "instore"


class OrderStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    PREPARING = "preparing"
    READY = "ready"  # ready for pickup
    OUT_FOR_DELIVERY = "out_for_delivery"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Order(Timestamped, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    fulfilment: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.PENDING_PAYMENT, index=True)

    subtotal: Mapped[float] = mapped_column(Float)
    discount: Mapped[float] = mapped_column(Float, default=0)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0)
    tax: Mapped[float] = mapped_column(Float, default=0)
    total: Mapped[float] = mapped_column(Float)
    cost_total: Mapped[float] = mapped_column(Float, default=0)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id"))

    delivery_address: Mapped[str | None] = mapped_column(Text)
    pickup_slot: Mapped[datetime | None] = mapped_column(DateTime)

    payment_provider: Mapped[str | None] = mapped_column(String(20))  # stripe|paypal|razorpay|mock
    payment_method: Mapped[str | None] = mapped_column(String(20))  # card|apple_pay|google_pay|upi|paypal
    payment_ref: Mapped[str | None] = mapped_column(String(120), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)

    receipt_nonce: Mapped[str | None] = mapped_column(String(32))
    exit_verified_at: Mapped[datetime | None] = mapped_column(DateTime)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    name: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    unit_cost: Mapped[float] = mapped_column(Float)
    aisle: Mapped[int | None] = mapped_column(Integer)
    row: Mapped[int | None] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")

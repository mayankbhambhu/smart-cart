from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import Timestamped, utcnow


class Store(Timestamped, Base):
    """A physical branch. The floor is modelled as a grid of parallel aisles
    (numbered left to right) each with `rows_per_aisle` shelf sections, joined by a
    front and a back cross-aisle. That is enough to compute walking routes."""

    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(80), index=True)
    pincode: Mapped[str] = mapped_column(String(12), default="")
    phone: Mapped[str] = mapped_column(String(20), default="")
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    opens_at: Mapped[int] = mapped_column(Integer, default=7)  # hour of day
    closes_at: Mapped[int] = mapped_column(Integer, default=23)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", use_alter=True))

    # Layout
    aisle_count: Mapped[int] = mapped_column(Integer, default=8)
    rows_per_aisle: Mapped[int] = mapped_column(Integer, default=6)
    delivery_radius_km: Mapped[float] = mapped_column(Float, default=5.0)

    gates: Mapped[list["ExitGate"]] = relationship(back_populates="store", cascade="all, delete-orphan")


class ExitGate(Base):
    __tablename__ = "exit_gates"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    api_key: Mapped[str] = mapped_column(String(64), unique=True)  # gate hardware authenticates with this
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    store: Mapped[Store] = relationship(back_populates="gates")


class GateEvent(Base):
    __tablename__ = "gate_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    gate_id: Mapped[int] = mapped_column(ForeignKey("exit_gates.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    opened: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

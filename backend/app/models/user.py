import enum
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import Timestamped, utcnow


class Role(str, enum.Enum):
    CUSTOMER = "customer"
    WORKER = "worker"
    FLOOR_MANAGER = "floor_manager"
    STORE_MANAGER = "store_manager"
    OWNER = "owner"
    ADMIN = "admin"


STAFF_ROLES = {Role.WORKER, Role.FLOOR_MANAGER, Role.STORE_MANAGER, Role.OWNER}


class User(Timestamped, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str | None] = mapped_column(String(255))
    auth_provider: Mapped[str] = mapped_column(String(20), default="email")  # email|google|apple|phone
    provider_subject: Mapped[str | None] = mapped_column(String(255), index=True)
    role: Mapped[Role] = mapped_column(String(20), default=Role.CUSTOMER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)

    # Customer profile
    dietary_preferences: Mapped[list] = mapped_column(JSON, default=list)
    default_address: Mapped[str | None] = mapped_column(Text)
    preferred_store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id", use_alter=True))

    # Staff profile
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id", use_alter=True), index=True)
    employee_code: Mapped[str | None] = mapped_column(String(30), unique=True)
    hourly_wage: Mapped[float | None] = mapped_column(Float)
    joined_on: Mapped[date | None] = mapped_column(Date)
    left_on: Mapped[date | None] = mapped_column(Date)

    payment_methods: Mapped[list["PaymentMethod"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def is_staff(self) -> bool:
        return Role(self.role) in STAFF_ROLES


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class PaymentMethod(Timestamped, Base):
    """A saved, tokenised payment method. Card numbers are never stored, only the
    gateway's token (e.g. Stripe PaymentMethod id) plus display info."""

    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # card|upi|paypal|apple_pay|google_pay
    label: Mapped[str] = mapped_column(String(80))  # "Visa •••• 4242", "name@okbank"
    gateway_token: Mapped[str | None] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="payment_methods")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(255))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

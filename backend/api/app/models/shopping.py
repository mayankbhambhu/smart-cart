from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import Timestamped
from app.models.catalog import Product


class ShoppingList(Timestamped, Base):
    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invite_code: Mapped[str] = mapped_column(String(12), unique=True)

    members: Mapped[list["ListMember"]] = relationship(back_populates="list", cascade="all, delete-orphan")
    items: Mapped[list["ListItem"]] = relationship(
        back_populates="list", cascade="all, delete-orphan", order_by="ListItem.id"
    )


class ListMember(Base):
    __tablename__ = "list_members"
    __table_args__ = (UniqueConstraint("list_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("shopping_lists.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    list: Mapped[ShoppingList] = relationship(back_populates="members")


class ListItem(Timestamped, Base):
    __tablename__ = "list_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("shopping_lists.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    added_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    list: Mapped[ShoppingList] = relationship(back_populates="items")
    product: Mapped[Product | None] = relationship()


class Cart(Timestamped, Base):
    """One active cart per user. In `instore` mode the cart is the 'smart cart':
    adding an item immediately deducts it from store inventory."""

    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    mode: Mapped[str] = mapped_column(String(10), default="delivery")  # delivery|pickup|instore
    status: Mapped[str] = mapped_column(String(15), default="active")  # active|checked_out|abandoned
    offer_code: Mapped[str | None] = mapped_column(String(30))

    items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float)
    picked: Mapped[bool] = mapped_column(Boolean, default=False)  # in-store: already in the physical cart

    cart: Mapped[Cart] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()

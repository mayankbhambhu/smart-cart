"""Pydantic request/response schemas."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Auth ------------------------------------------------------------------------
class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    phone: str | None = None


class LoginIn(BaseModel):
    identifier: str  # email or phone
    password: str


class OTPRequestIn(BaseModel):
    phone: str = Field(pattern=r"^\+?[0-9]{10,15}$")


class OTPVerifyIn(BaseModel):
    phone: str
    code: str = Field(min_length=6, max_length=6)
    full_name: str | None = None


class SocialLoginIn(BaseModel):
    id_token: str
    full_name: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(ORM):
    id: int
    email: str | None
    phone: str | None
    full_name: str
    role: str
    auth_provider: str
    store_id: int | None
    preferred_store_id: int | None
    dietary_preferences: list[str]
    default_address: str | None
    must_change_password: bool
    employee_code: str | None = None


class ProfileUpdateIn(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    dietary_preferences: list[str] | None = None
    default_address: str | None = None
    preferred_store_id: int | None = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class PaymentMethodIn(BaseModel):
    kind: str = Field(pattern="^(card|upi|paypal|apple_pay|google_pay)$")
    label: str
    gateway_token: str | None = None
    is_default: bool = False


class PaymentMethodOut(ORM):
    id: int
    kind: str
    label: str
    is_default: bool


# ---- Catalog ---------------------------------------------------------------------
class StoreOut(ORM):
    id: int
    code: str
    name: str
    address: str
    city: str
    pincode: str
    phone: str
    latitude: float
    longitude: float
    opens_at: int
    closes_at: int
    aisle_count: int
    rows_per_aisle: int
    distance_km: float | None = None


class ProductOut(ORM):
    id: int
    sku: str
    barcode: str | None
    name: str
    brand: str
    category_id: int
    unit: str
    mrp: float
    price: float
    image_url: str
    description: str
    tags: list[str]


class StockedProductOut(ProductOut):
    in_stock: bool
    quantity: int
    aisle: int
    row: int
    location: str


# ---- Lists -----------------------------------------------------------------------
class ListCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ListItemIn(BaseModel):
    name: str | None = None
    product_id: int | None = None
    quantity: int = Field(default=1, ge=1, le=99)


class ListItemPatch(BaseModel):
    quantity: int | None = Field(default=None, ge=1, le=99)
    checked: bool | None = None


# ---- Cart / orders ---------------------------------------------------------------
class CartSetupIn(BaseModel):
    store_id: int
    mode: str = Field(pattern="^(delivery|pickup|instore)$")


class CartItemIn(BaseModel):
    product_id: int | None = None
    barcode: str | None = None  # in-store: scan the product barcode
    quantity: int = Field(default=1, ge=1, le=50)


class CartQtyIn(BaseModel):
    quantity: int = Field(ge=0, le=50)


class OfferIn(BaseModel):
    code: str | None


class CheckoutIn(BaseModel):
    payment_method: str = Field(pattern="^(card|apple_pay|google_pay|upi|paypal)$")
    delivery_address: str | None = None
    pickup_slot: datetime | None = None


class PaymentConfirmIn(BaseModel):
    order_id: int


class GateVerifyIn(BaseModel):
    code: str


# ---- Staff -----------------------------------------------------------------------
class CredentialRequestIn(BaseModel):
    full_name: str = Field(min_length=2)
    email: EmailStr
    phone: str
    role: str = Field(pattern="^(worker|floor_manager|store_manager)$")
    hourly_wage: float = Field(gt=0)
    joining_date: date
    notes: str = ""


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(approve|send_back|reject)$")
    note: str = ""


class TaskIn(BaseModel):
    title: str = Field(min_length=2)
    description: str = ""
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    assigned_to_id: int
    due_at: datetime | None = None


class TaskProgressIn(BaseModel):
    status: str = Field(pattern="^(in_progress|done)$")
    completion_note: str | None = None


class TaskReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    feedback: str = ""


class ShiftIn(BaseModel):
    user_id: int
    starts_at: datetime
    ends_at: datetime
    label: str = ""


class InventoryPatch(BaseModel):
    quantity_delta: int | None = None
    quantity: int | None = Field(default=None, ge=0)
    aisle: int | None = Field(default=None, ge=1)
    row: int | None = Field(default=None, ge=1)
    low_stock_threshold: int | None = Field(default=None, ge=0)


class OrderStatusIn(BaseModel):
    status: str = Field(pattern="^(preparing|ready|out_for_delivery|completed|cancelled)$")


class TicketIn(BaseModel):
    category: str = Field(pattern="^(hardware|payments|inventory|account|gate|other)$")
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    subject: str = Field(min_length=3)
    description: str = Field(min_length=3)


class TicketResponseIn(BaseModel):
    status: str = Field(pattern="^(open|in_progress|resolved)$")
    admin_response: str = ""


class StoreCreateIn(BaseModel):
    code: str
    name: str
    address: str
    city: str
    pincode: str = ""
    phone: str = ""
    latitude: float
    longitude: float
    aisle_count: int = 8
    rows_per_aisle: int = 6
    owner_name: str
    owner_email: EmailStr
    owner_phone: str


class OfferCreateIn(BaseModel):
    code: str
    title: str
    discount_percent: float = Field(gt=0, le=90)
    max_discount: float = 100
    min_order: float = 0
    category_id: int | None = None
    ends_at: datetime | None = None


TokenOut.model_rebuild()

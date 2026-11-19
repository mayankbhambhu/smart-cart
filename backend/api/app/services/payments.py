"""Payment gateway adapters.

  card / apple_pay / google_pay -> Stripe PaymentIntent. The mobile app uses Stripe's
                                   PaymentSheet (Apple Pay & Google Pay built in); the web
                                   uses the Payment Request button.
  upi                           -> Razorpay Payment Link (hosted page: UPI apps / QR / collect).
                                   Works identically from the mobile app and the web, no
                                   native SDK needed; verified server-side by link status.
  paypal                        -> PayPal Orders v2 (approve link + capture)

When PAYMENTS_MODE=mock (default in development) every method returns a mock intent that
the client confirms through /payments/mock/confirm, so the full flow is testable without
gateway accounts.
"""
import requests
from fastapi import HTTPException

from app.core.config import settings
from app.models import Order

STRIPE_METHODS = {"card", "apple_pay", "google_pay"}
ALL_METHODS = STRIPE_METHODS | {"upi", "paypal"}


def _paise(amount: float) -> int:
    return int(round(amount * 100))


def provider_for(method: str) -> str:
    if method not in ALL_METHODS:
        raise HTTPException(400, f"Unsupported payment method '{method}'")
    if settings.PAYMENTS_MODE == "mock":
        return "mock"
    return "stripe" if method in STRIPE_METHODS else ("razorpay" if method == "upi" else "paypal")


def create_intent(order: Order, method: str, customer_email: str | None) -> dict:
    provider = provider_for(method)
    base = {"provider": provider, "method": method, "order_id": order.id,
            "amount": order.total, "currency": settings.CURRENCY}

    if provider == "mock":
        return {**base, "reference": f"mock_{order.number}", "client_secret": f"mock_secret_{order.number}"}

    if provider == "stripe":
        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.create(
            amount=_paise(order.total), currency=settings.CURRENCY.lower(),
            automatic_payment_methods={"enabled": True},
            receipt_email=customer_email, metadata={"order_id": order.id, "order_number": order.number},
        )
        return {**base, "reference": intent.id, "client_secret": intent.client_secret,
                "publishable_key": settings.STRIPE_PUBLISHABLE_KEY}

    if provider == "razorpay":
        import razorpay

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        link = client.payment_link.create({
            "amount": _paise(order.total), "currency": "INR", "reference_id": order.number,
            "description": f"{settings.APP_NAME} order {order.number}", "notes": {"order_id": str(order.id)},
            "reminder_enable": False})
        return {**base, "reference": link["id"], "approve_url": link["short_url"]}

    # PayPal
    token = _paypal_token()
    resp = requests.post(f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders", timeout=15,
                         headers={"Authorization": f"Bearer {token}"},
                         json={"intent": "CAPTURE", "purchase_units": [{
                             "reference_id": order.number,
                             "amount": {"currency_code": settings.CURRENCY, "value": f"{order.total:.2f}"}}]})
    resp.raise_for_status()
    data = resp.json()
    approve = next((l["href"] for l in data["links"] if l["rel"] in ("approve", "payer-action")), None)
    return {**base, "reference": data["id"], "approve_url": approve}


def _paypal_token() -> str:
    resp = requests.post(f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token", data={"grant_type": "client_credentials"},
                         auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET), timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def verify_payment(order: Order, payload: dict) -> bool:
    """Server-side confirmation that money actually moved. Never trust the client alone."""
    provider = order.payment_provider
    if provider == "mock":
        return settings.PAYMENTS_MODE == "mock"
    if provider == "stripe":
        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.retrieve(order.payment_ref)
        return intent.status == "succeeded" and intent.amount == _paise(order.total)
    if provider == "razorpay":
        import razorpay

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        link = client.payment_link.fetch(order.payment_ref)
        return link.get("status") == "paid" and int(link.get("amount_paid", 0)) == _paise(order.total)
    if provider == "paypal":
        token = _paypal_token()
        resp = requests.post(f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders/{order.payment_ref}/capture",
                             headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                             timeout=15)
        return resp.ok and resp.json().get("status") == "COMPLETED"
    return False


def refund(order: Order) -> None:
    if order.payment_provider == "stripe" and settings.PAYMENTS_MODE == "live":
        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.Refund.create(payment_intent=order.payment_ref)
    # Razorpay / PayPal refunds follow the same pattern; omitted until accounts are live.

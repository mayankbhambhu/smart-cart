"""Password hashing, JWT tokens, and signed receipt codes."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(user_id: int, role: str, minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=minutes or settings.ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


def generate_temp_password(length: int = 10) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length)) + "!"


def hash_otp(phone: str, code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


# ---- Digital receipt / exit barcode -------------------------------------------------
# Format: FF1.<order_id>.<nonce>.<signature>. The signature is an HMAC so a gate can
# reject forged codes even before it hits the database.

def _receipt_sig(order_id: int, nonce: str) -> str:
    msg = f"{order_id}.{nonce}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:20]


def make_receipt_code(order_id: int, nonce: str) -> str:
    return f"FF1.{order_id}.{nonce}.{_receipt_sig(order_id, nonce)}"


def parse_receipt_code(code: str) -> tuple[int, str] | None:
    try:
        prefix, order_id, nonce, sig = code.strip().split(".")
        oid = int(order_id)
    except ValueError:
        return None
    if prefix != "FF1" or not hmac.compare_digest(sig, _receipt_sig(oid, nonce)):
        return None
    return oid, nonce

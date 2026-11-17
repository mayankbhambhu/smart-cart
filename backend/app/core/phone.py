"""One canonical form for phone numbers (+<country code><number>), used everywhere they are stored or looked up."""
import re

from app.core.config import settings


def to_e164(raw: str) -> str:
    """'98111 11111', '091-9811111111', '+91 98111 11111' -> '+919811111111'. Raises ValueError if invalid."""
    s = re.sub(r"[\s\-().]", "", raw or "")
    if s.startswith("00"):
        s = "+" + s[2:]
    if not s.startswith("+"):
        s = s.lstrip("0")
        cc = settings.PHONE_DEFAULT_COUNTRY_CODE.lstrip("+")
        s = "+" + (s if len(s) > 10 and s.startswith(cc) else cc + s)
    if not re.fullmatch(r"\+[1-9]\d{9,14}", s):
        raise ValueError("Enter a valid mobile number, e.g. +91 98111 11111")
    return s

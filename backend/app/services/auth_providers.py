"""Verification of third-party identity tokens (Google, Apple) and SMS OTP delivery."""
import logging

import jwt
from fastapi import HTTPException

from app.core.config import settings

log = logging.getLogger("auth")
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"


def verify_google_id_token(token: str) -> dict:
    """Returns {sub, email, name}. The mobile/web client obtains the ID token via Google Sign-In."""
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token

    audiences = [a.strip() for a in settings.GOOGLE_CLIENT_IDS.split(",") if a.strip()]
    if not audiences:
        raise HTTPException(503, "Google login is not configured (GOOGLE_CLIENT_IDS)")
    try:
        info = id_token.verify_oauth2_token(token, g_requests.Request(), audience=None)
    except ValueError as exc:
        raise HTTPException(401, f"Invalid Google token: {exc}")
    if info.get("aud") not in audiences:
        raise HTTPException(401, "Google token audience mismatch")
    return {"sub": info["sub"], "email": info.get("email"), "name": info.get("name", "")}


def verify_apple_identity_token(token: str) -> dict:
    audiences = [a.strip() for a in settings.APPLE_BUNDLE_IDS.split(",") if a.strip()]
    if not audiences:
        raise HTTPException(503, "Apple login is not configured (APPLE_BUNDLE_IDS)")
    try:
        key = jwt.PyJWKClient(APPLE_JWKS_URL).get_signing_key_from_jwt(token)
        info = jwt.decode(token, key.key, algorithms=["RS256"], audience=audiences,
                          issuer="https://appleid.apple.com")
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Invalid Apple token: {exc}")
    return {"sub": info["sub"], "email": info.get("email"), "name": ""}


def send_sms(phone: str, body: str) -> bool:
    """Sends via Twilio when configured; otherwise logs (development)."""
    if not settings.TWILIO_ACCOUNT_SID:
        log.warning("SMS to %s: %s  (Twilio not configured, logged only)", phone, body)
        return False
    import requests

    resp = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
        data={"To": phone, "From": settings.TWILIO_FROM_NUMBER, "Body": body},
        auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        timeout=10,
    )
    return resp.ok

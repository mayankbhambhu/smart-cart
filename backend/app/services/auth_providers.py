"""Verification of third-party identity tokens (Google, Apple, Firebase) and SMS OTP delivery."""
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

    audiences = settings.google_audiences
    if not audiences:
        raise HTTPException(503, "Google sign-in is not set up yet (GOOGLE_WEB_CLIENT_ID)")
    try:
        info = id_token.verify_oauth2_token(token, g_requests.Request(), audience=None)
    except ValueError as exc:
        raise HTTPException(401, f"Invalid Google token: {exc}")
    if info.get("aud") not in audiences:
        raise HTTPException(401, "Google token audience mismatch")
    return {"sub": info["sub"], "email": info.get("email"), "name": info.get("name", ""),
            "email_verified": info.get("email_verified") in (True, "true")}


def verify_firebase_id_token(token: str) -> dict:
    """ID token from Firebase Auth (e.g. after an email-link sign-in)."""
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token

    project = settings.FIREBASE_PROJECT_ID
    if not project:
        raise HTTPException(503, "Email-link sign-in is not set up yet (FIREBASE_PROJECT_ID)")
    try:
        info = id_token.verify_firebase_token(token, g_requests.Request(), audience=project)
    except ValueError as exc:
        raise HTTPException(401, f"Invalid Firebase token: {exc}")
    if not info or info.get("iss") != f"https://securetoken.google.com/{project}":
        raise HTTPException(401, "Firebase token issuer mismatch")
    return {"sub": info["sub"], "email": info.get("email"), "name": info.get("name", ""),
            "email_verified": bool(info.get("email_verified"))}


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
    return {"sub": info["sub"], "email": info.get("email"), "name": "",
            "email_verified": info.get("email_verified") in (True, "true")}


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

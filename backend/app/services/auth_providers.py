"""Verification of third-party identity tokens (Google, Apple, Firebase) and SMS OTP delivery."""
import logging

import jwt
import requests
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


def normalize_phone(raw: str) -> str:
    """Canonical +<country><number> form; a clear 400 error if it isn't a phone number."""
    from app.core.phone import to_e164

    try:
        return to_e164(raw)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


def _twilio_error(resp) -> str:
    try:
        return resp.json().get("message") or resp.text
    except ValueError:
        return resp.text


def twilio_verify_enabled() -> bool:
    return bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_VERIFY_SERVICE_SID)


def _verify_url(path: str) -> str:
    return f"https://verify.twilio.com/v2/Services/{settings.TWILIO_VERIFY_SERVICE_SID}/{path}"


def start_verification(phone: str) -> None:
    """Twilio Verify generates the code and sends the SMS."""
    resp = requests.post(_verify_url("Verifications"), data={"To": phone, "Channel": "sms"},
                         auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN), timeout=15)
    if not resp.ok:
        raise HTTPException(502, f"Could not send the code: {_twilio_error(resp)}")


def check_verification(phone: str, code: str) -> bool:
    resp = requests.post(_verify_url("VerificationCheck"), data={"To": phone, "Code": code},
                         auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN), timeout=15)
    if resp.status_code == 404:  # no pending verification: expired, already used or too many attempts
        return False
    if not resp.ok:
        raise HTTPException(502, f"Could not check the code: {_twilio_error(resp)}")
    return resp.json().get("status") == "approved"


def send_sms(phone: str, body: str) -> bool:
    """Sends via Twilio when configured; otherwise logs (development)."""
    if not settings.TWILIO_ACCOUNT_SID:
        log.warning("SMS to %s: %s  (Twilio not configured, logged only)", phone, body)
        return False
    resp = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
        data={"To": phone, "From": settings.TWILIO_FROM_NUMBER, "Body": body},
        auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        timeout=10,
    )
    if not resp.ok:  # tell the person why, instead of claiming the code was sent
        raise HTTPException(502, f"Could not send the SMS: {_twilio_error(resp)}")
    return True

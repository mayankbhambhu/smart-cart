"""Single sign-on with any OpenID Connect provider (Microsoft Entra ID, Google Workspace, Okta,
Auth0, Keycloak...). Authorization-code flow with PKCE, a one-time state and a nonce; the ID token
is verified against the provider's published keys."""
import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException

from app.core.config import settings

_discovery: dict[str, dict] = {}
_jwks: dict[str, jwt.PyJWKClient] = {}


def enabled() -> bool:
    return bool(settings.OIDC_ISSUER and settings.OIDC_CLIENT_ID)


def discovery() -> dict:
    if not enabled():
        raise HTTPException(503, "Single sign-on is not set up yet (OIDC_ISSUER, OIDC_CLIENT_ID)")
    issuer = settings.OIDC_ISSUER.rstrip("/")
    if issuer not in _discovery:
        try:
            r = httpx.get(issuer + "/.well-known/openid-configuration", timeout=10)
            r.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(502, "Could not reach the single sign-on provider")
        _discovery[issuer] = r.json()
    return _discovery[issuer]


def allowed_redirect(url: str) -> bool:
    return any(url.startswith(prefix) for prefix in settings.sso_allowed_redirects)


def callback_url() -> str:
    return settings.API_PUBLIC_URL.rstrip("/") + "/auth/sso/callback"


def new_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def authorize_url(state: str, nonce: str, challenge: str) -> str:
    params = {"response_type": "code", "client_id": settings.OIDC_CLIENT_ID, "redirect_uri": callback_url(),
              "scope": settings.OIDC_SCOPES, "state": state, "nonce": nonce,
              "code_challenge": challenge, "code_challenge_method": "S256"}
    return discovery()["authorization_endpoint"] + "?" + urlencode(params)


def exchange_code(code: str, verifier: str) -> dict:
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": callback_url(),
            "client_id": settings.OIDC_CLIENT_ID, "code_verifier": verifier}
    if settings.OIDC_CLIENT_SECRET:
        data["client_secret"] = settings.OIDC_CLIENT_SECRET
    try:
        r = httpx.post(discovery()["token_endpoint"], data=data, timeout=15)
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach the single sign-on provider")
    if r.status_code >= 400 or "id_token" not in r.json():
        raise HTTPException(401, "Single sign-on was refused by the identity provider")
    return r.json()


def _signing_key(id_token: str):
    uri = discovery()["jwks_uri"]
    if uri not in _jwks:
        _jwks[uri] = jwt.PyJWKClient(uri)
    return _jwks[uri].get_signing_key_from_jwt(id_token).key


def verify_id_token(id_token: str, nonce: str) -> dict:
    try:
        claims = jwt.decode(id_token, _signing_key(id_token), algorithms=["RS256", "ES256"],
                            audience=settings.OIDC_CLIENT_ID, issuer=discovery()["issuer"])
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Invalid single sign-on token: {exc}")
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise HTTPException(401, "Single sign-on nonce mismatch")
    # Entra ID often omits "email" and puts the address in preferred_username / upn.
    email = claims.get("email") or claims.get("preferred_username") or claims.get("upn")
    if not email or "@" not in email:
        raise HTTPException(401, "Your organisation account has no email address")
    # The organisation's directory is the source of truth for its own users' addresses.
    return {"sub": claims["sub"], "email": email.lower(), "name": claims.get("name", ""), "email_verified": True}

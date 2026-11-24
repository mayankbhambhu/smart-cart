"""Google, Firebase email-link and single sign-on (OIDC) sign-in."""
import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.api.routes import auth as auth_routes
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import User
from app.services import sso

ISSUER = "https://idp.example.com"


@pytest.fixture()
def fake_idp(monkeypatch):
    """A tiny OpenID Connect provider: real RSA-signed ID tokens, no network."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "OIDC_ISSUER", ISSUER)
    monkeypatch.setattr(settings, "OIDC_CLIENT_ID", "smartcart-test")
    monkeypatch.setattr(settings, "OIDC_CLIENT_SECRET", "s3cret")
    sso._discovery[ISSUER] = {"issuer": ISSUER, "authorization_endpoint": ISSUER + "/authorize",
                              "token_endpoint": ISSUER + "/token", "jwks_uri": ISSUER + "/jwks"}
    monkeypatch.setattr(sso, "_signing_key", lambda token: key.public_key())
    idp = {"email": "manager.blr01@freshflow.app", "nonce": None, "aud": "smartcart-test", "iss": ISSUER, "seen": {}}

    def exchange(code, verifier):
        idp["seen"] = {"code": code, "verifier": verifier}
        claims = {"sub": "idp-user-1", "email": idp["email"], "name": "SSO User", "aud": idp["aud"], "iss": idp["iss"],
                  "nonce": idp["nonce"], "iat": int(time.time()), "exp": int(time.time()) + 300}
        return {"id_token": jwt.encode(claims, key, algorithm="RS256")}

    monkeypatch.setattr(sso, "exchange_code", exchange)
    yield idp
    sso._discovery.pop(ISSUER, None)


def _start(client, idp, redirect="http://localhost:8001/auth/continue"):
    r = client.get("/auth/sso/start", params={"redirect": redirect}, follow_redirects=False)
    assert r.status_code == 302, r.text
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["code_challenge_method"] == ["S256"] and q["client_id"] == ["smartcart-test"]
    idp["nonce"] = q["nonce"][0]
    return q["state"][0]


def _back(r):
    assert r.status_code == 302
    return parse_qs(urlparse(r.headers["location"]).query)


def test_providers_endpoint_reports_what_is_enabled(client, fake_idp):
    p = client.get("/auth/providers").json()
    assert p["sso"]["enabled"] is True and p["password"]["enabled"] is True
    assert p["firebase_email_link"]["enabled"] is False  # no Firebase project configured in tests


def test_sso_signs_in_existing_staff_account(client, fake_idp):
    state = _start(client, fake_idp)
    q = _back(client.get("/auth/sso/callback", params={"state": state, "code": "abc"}, follow_redirects=False))
    tok = client.post("/auth/exchange", json={"code": q["code"][0]})
    assert tok.status_code == 200 and tok.json()["user"]["role"] == "store_manager"
    assert fake_idp["seen"]["code"] == "abc" and len(fake_idp["seen"]["verifier"]) > 40  # PKCE verifier kept server-side
    # the one-time code and the state are both single-use
    assert client.post("/auth/exchange", json={"code": q["code"][0]}).status_code == 400
    assert client.get("/auth/sso/callback", params={"state": state, "code": "abc"}, follow_redirects=False).status_code == 400


def test_sso_refuses_unknown_people_wrong_audience_and_bad_nonce(client, fake_idp):
    fake_idp["email"] = "stranger@elsewhere.com"
    q = _back(client.get("/auth/sso/callback", params={"state": _start(client, fake_idp), "code": "x"}, follow_redirects=False))
    assert "code" not in q and "no account" in q["error"][0]
    fake_idp["email"], fake_idp["aud"] = "manager.blr01@freshflow.app", "some-other-app"
    q = _back(client.get("/auth/sso/callback", params={"state": _start(client, fake_idp), "code": "x"}, follow_redirects=False))
    assert "Invalid single sign-on token" in q["error"][0]
    fake_idp["aud"] = "smartcart-test"
    state = _start(client, fake_idp)
    fake_idp["nonce"] = "tampered"
    q = _back(client.get("/auth/sso/callback", params={"state": state, "code": "x"}, follow_redirects=False))
    assert "nonce" in q["error"][0]


def test_sso_rejects_return_addresses_not_on_the_allow_list(client, fake_idp):
    r = client.get("/auth/sso/start", params={"redirect": "https://evil.example.com/steal"}, follow_redirects=False)
    assert r.status_code == 400


def test_firebase_email_link_new_shopper_and_existing_staff(client, monkeypatch):
    claims = {"sub": "fb-uid-1", "email": "new.person@example.com", "name": "", "email_verified": True}
    monkeypatch.setattr(auth_routes, "verify_firebase_id_token", lambda t: dict(claims))
    r = client.post("/auth/firebase", json={"id_token": "x", "full_name": "New Person"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "customer"  # new emails become shoppers
    claims.update(sub="fb-uid-2", email="worker1.blr01@freshflow.app")
    assert client.post("/auth/firebase", json={"id_token": "x"}).json()["user"]["role"] == "worker"
    claims.update(sub="fb-uid-3", email="owner.blr01@freshflow.app", email_verified=False)
    assert client.post("/auth/firebase", json={"id_token": "x"}).status_code == 401  # unverified email can't take over


def test_google_refuses_deactivated_accounts(client, monkeypatch):
    with SessionLocal() as db:
        u = User(email="gone@example.com", full_name="Gone", is_active=False)
        db.add(u)
        db.commit()
    monkeypatch.setattr(auth_routes, "verify_google_id_token",
                        lambda t: {"sub": "g-9", "email": "gone@example.com", "name": "", "email_verified": True})
    assert client.post("/auth/google", json={"id_token": "x"}).status_code == 403


def test_handoff_code_moves_a_signed_in_user_once(client, login):
    code = client.post("/auth/handoff", headers=login("admin@freshflow.app")).json()["code"]
    assert client.post("/auth/exchange", json={"code": code}).json()["user"]["role"] == "admin"
    assert client.post("/auth/exchange", json={"code": code}).status_code == 400

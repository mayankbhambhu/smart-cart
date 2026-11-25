"""Customer: auth, stock check, live list sync, in-store smart cart, pay, exit gate."""
from app.core.database import SessionLocal
from app.models import ExitGate, Inventory


def test_register_and_profile(client):
    r = client.post("/auth/register", json={"full_name": "Test User", "email": "t@example.com", "password": "secret123"})
    assert r.status_code == 201
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.patch("/me", json={"dietary_preferences": ["vegan", "gluten_free"]}, headers=h)
    assert r.json()["dietary_preferences"] == ["vegan", "gluten_free"]
    assert client.post("/me/payment-methods", json={"kind": "upi", "label": "test@okbank"}, headers=h).status_code == 201


def test_phone_otp_login(client):
    r = client.post("/auth/otp/request", json={"phone": "+919900000000"})
    code = r.json()["dev_code"]
    assert client.post("/auth/otp/verify", json={"phone": "+919900000000", "code": "000000"}).status_code in (401,)
    r = client.post("/auth/otp/verify", json={"phone": "+919900000000", "code": code, "full_name": "Phone User"})
    assert r.status_code == 200 and r.json()["user"]["auth_provider"] == "phone"


def test_stock_check_and_location(client):
    rows = client.get("/stock-check", params={"q": "milk", "lat": 12.97, "lng": 77.64}).json()
    assert rows and rows[0]["location"].startswith("Aisle")
    items = client.get("/stores/1/products", params={"tags": "vegan", "q": "milk"}).json()
    assert all("vegan" in i["tags"] for i in items)


def test_family_list_and_route(client, login):
    asha, rohan = login("asha@example.com"), login("rohan@example.com")
    lists = client.get("/lists", headers=rohan).json()
    fam = next(l for l in lists if l["name"] == "Verma Family Weekly")
    # spouse adds milk at home -> visible to shopper
    client.post(f"/lists/{fam['id']}/items", json={"name": "Curd"}, headers=asha)
    data = client.get(f"/lists/{fam['id']}", params={"store_id": 1}, headers=rohan).json()
    curd = next(i for i in data["items"] if i["name"] == "Curd")
    assert curd["location"] and curd["product_id"]
    route = client.get(f"/lists/{fam['id']}/route", params={"store_id": 1}, headers=rohan).json()
    assert route["steps"] and route["estimated_total"] > 0


def test_websocket_list_sync(client, login):
    asha, rohan = login("asha@example.com"), login("rohan@example.com")
    lid = client.get("/lists", headers=rohan).json()[0]["id"]
    token = rohan["Authorization"].split()[1]
    with client.websocket_connect(f"/ws?token={token}&channels=list:{lid}") as ws:
        assert f"list:{lid}" in ws.receive_json()["channels"]
        client.post(f"/lists/{lid}/items", json={"name": "Honey"}, headers=asha)
        msg = ws.receive_json()
        assert msg["event"] == "item_added" and msg["data"]["item"] == "Honey"


def test_instore_scan_and_go(client, login):
    h = login("rohan@example.com")
    client.post("/cart/setup", json={"store_id": 1, "mode": "instore"}, headers=h)
    with SessionLocal() as db:
        inv = db.query(Inventory).filter_by(store_id=1, product_id=8).one()
        before = inv.quantity
    cart = client.post("/cart/items", json={"product_id": 8, "quantity": 2}, headers=h).json()
    assert cart["items"][0]["location"].startswith("Aisle")
    with SessionLocal() as db:  # smart cart deducts immediately
        assert db.query(Inventory).filter_by(store_id=1, product_id=8).one().quantity == before - 2
    cart = client.post("/cart/items", json={"barcode": "8900000000241", "quantity": 1}, headers=h).json()
    assert cart["item_count"] == 3 and cart["total"] > 0

    r = client.post("/checkout", json={"payment_method": "upi"}, headers=h).json()
    oid = r["order"]["id"]
    assert r["payment"]["provider"] == "mock"
    order = client.post("/payments/confirm", json={"order_id": oid}, headers=h).json()
    assert order["status"] == "paid" and order["receipt_code"].startswith("FF1.")
    assert client.get(f"/orders/{oid}/receipt.png", headers=h).headers["content-type"] == "image/png"

    with SessionLocal() as db:
        key = db.query(ExitGate).filter_by(store_id=1).first().api_key
        other = db.query(ExitGate).filter_by(store_id=2).first().api_key
    assert client.post("/gate/verify", json={"code": order["receipt_code"]}, headers={"x-gate-key": other}).json()["open"] is False
    ok = client.post("/gate/verify", json={"code": order["receipt_code"]}, headers={"x-gate-key": key}).json()
    assert ok["open"] is True
    forged = order["receipt_code"][:-3] + "abc"
    assert client.post("/gate/verify", json={"code": forged}, headers={"x-gate-key": key}).json()["open"] is False


def test_pickup_order_with_offer(client, login):
    h = login("asha@example.com")
    client.post("/cart/setup", json={"store_id": 1, "mode": "pickup"}, headers=h)
    client.post("/cart/items", json={"product_id": 17, "quantity": 1}, headers=h)
    cart = client.post("/cart/offer", json={"code": "welcome50"}, headers=h).json()
    assert cart["discount"] == 100
    slots = client.get("/stores/1/pickup-slots", params={"day": "2099-01-01"}).json()
    assert slots and slots[0]["available"] == 10
    r = client.post("/checkout", json={"payment_method": "card", "pickup_slot": slots[0]["start"]}, headers=h)
    assert r.status_code == 200, r.text
    order = client.post("/payments/confirm", json={"order_id": r.json()["order"]["id"]}, headers=h).json()
    assert order["status"] == "preparing" and order["fulfilment"] == "pickup"


def test_phone_numbers_are_normalised(client):
    """10-digit numbers typed without +91, with spaces or dashes, reach the same account."""
    from app.services.auth_providers import normalize_phone

    for raw in ("9811111111", "98111 11111", "+91 98111-11111", "09811111111", "00919811111111"):
        assert normalize_phone(raw) == "+919811111111", raw
    r = client.post("/auth/otp/request", json={"phone": "98111 11111"}).json()
    assert r["phone"] == "+919811111111"
    v = client.post("/auth/otp/verify", json={"phone": "9811111111", "code": r["dev_code"]})
    assert v.status_code == 200 and v.json()["user"]["email"] == "asha@example.com"  # existing account, not a new one
    assert client.post("/auth/otp/request", json={"phone": "12ab"}).status_code in (400, 422)


def test_twilio_verify_path(client, monkeypatch):
    """With Twilio Verify configured, Twilio sends and checks the code; no code is ever shown."""
    from app.api.routes import auth as auth_routes

    sent, checks = [], []
    monkeypatch.setattr(auth_routes, "twilio_verify_enabled", lambda: True)
    monkeypatch.setattr(auth_routes, "start_verification", lambda phone: sent.append(phone))
    monkeypatch.setattr(auth_routes, "check_verification", lambda phone, code: checks.append(code) or code == "424242")
    r = client.post("/auth/otp/request", json={"phone": "9822222222"}).json()
    assert sent == ["+919822222222"] and "dev_code" not in r
    assert client.post("/auth/otp/verify", json={"phone": "9822222222", "code": "000000"}).status_code == 401
    ok = client.post("/auth/otp/verify", json={"phone": "+919822222222", "code": "424242"})
    assert ok.status_code == 200 and ok.json()["user"]["email"] == "rohan@example.com"


def test_android_sms_gateway_path(client, monkeypatch):
    """The free Android gateway gets the code in a text; the code is not shown on screen."""
    import re

    from app.core.config import settings
    from app.services import auth_providers

    calls = []

    class Resp:
        status_code, ok, text = 202, True, "{}"

    def fake_post(url, json=None, auth=None, timeout=None, **kw):
        calls.append((url, json, auth))
        return Resp()

    monkeypatch.setattr(settings, "SMSGATE_USERNAME", "gate-user")
    monkeypatch.setattr(settings, "SMSGATE_PASSWORD", "gate-pass")
    monkeypatch.setattr(auth_providers.requests, "post", fake_post)
    r = client.post("/auth/otp/request", json={"phone": "98333 33333"}).json()
    assert "dev_code" not in r and len(calls) == 1
    url, body, auth = calls[0]
    assert url == settings.SMSGATE_URL and auth == ("gate-user", "gate-pass")
    assert body["phoneNumbers"] == ["+919833333333"]
    code = re.search(r"\b(\d{6})\b", body["textMessage"]["text"]).group(1)
    assert client.post("/auth/otp/verify", json={"phone": "9833333333", "code": code}).status_code == 200


def test_otp_refuses_deactivated_accounts(client):
    from app.core.database import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        db.add(User(phone="+919877777777", full_name="Left", is_active=False))
        db.commit()
    r = client.post("/auth/otp/request", json={"phone": "9877777777"}).json()
    assert client.post("/auth/otp/verify", json={"phone": "9877777777", "code": r["dev_code"]}).status_code == 403


def test_phone_numbers_stored_in_one_form(client, login):
    """Numbers typed loosely when creating accounts are stored as +91…, so OTP and password login find them."""
    r = client.post("/auth/register", json={"full_name": "Meena", "email": "meena@example.com", "password": "secret123",
                                            "phone": "98333 44455"})
    assert r.json()["user"]["phone"] == "+919833344455"
    assert client.post("/auth/login", json={"identifier": "9833344455", "password": "secret123"}).status_code == 200
    mgr = login("manager.blr01@freshflow.app")
    req = client.post("/ops/stores/1/credential-requests", headers=mgr, json={
        "full_name": "Ravi", "email": "ravi.new@example.com", "phone": "098 7654 3210", "role": "worker",
        "hourly_wage": 100, "joining_date": "2026-12-01"}).json()
    assert req["phone"] == "+919876543210"
    assert client.post("/auth/register", json={"full_name": "X", "email": "x@example.com", "password": "secret123",
                                               "phone": "12ab"}).status_code == 422

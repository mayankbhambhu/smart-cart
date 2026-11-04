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
    cart = client.post("/cart/items", json={"barcode": "8900000000024", "quantity": 1}, headers=h).json()
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

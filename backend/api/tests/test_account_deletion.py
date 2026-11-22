"""Shoppers can delete their own account (Google Play / App Store requirement)."""


def _register(client, email, name):
    r = client.post("/auth/register", json={"full_name": name, "email": email, "password": "secret123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_shopper_deletes_account(client):
    me = _register(client, "leaving@example.com", "Leaving User")
    friend = _register(client, "staying@example.com", "Staying User")
    client.patch("/me", json={"dietary_preferences": ["vegan"], "default_address": "12 MG Road"}, headers=me)
    client.post("/me/payment-methods", json={"kind": "upi", "label": "leave@okbank"}, headers=me)
    lst = client.post("/lists", json={"name": "Shared"}, headers=me).json()
    assert client.post(f"/lists/join/{lst['invite_code']}", headers=friend).status_code in (200, 201)

    assert client.post("/me/delete", json={"confirm": "no"}, headers=me).status_code == 400
    assert client.post("/me/delete", json={"confirm": "DELETE"}, headers=me).json() == {"deleted": True}

    # signed out everywhere, can't sign in again, and the email is free for a new account
    assert client.get("/me", headers=me).status_code == 401
    assert client.post("/auth/login", json={"identifier": "leaving@example.com", "password": "secret123"}).status_code == 401
    # the family list stays with the other member
    names = [l["name"] for l in client.get("/lists", headers=friend).json()]
    assert "Shared" in names
    _register(client, "leaving@example.com", "Came Back")


def test_staff_cannot_self_delete(client, login):
    r = client.post("/me/delete", json={"confirm": "DELETE"}, headers=login("worker1.blr01@freshflow.app"))
    assert r.status_code == 403

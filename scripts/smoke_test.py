"""End-to-end smoke test: logs in as every role on all three dashboards and exercises the
main flows (Scan & Go -> pay -> exit gate). Needs the 4 servers running (scripts/dev.sh)."""
import httpx, re

PW = "Password@123"
fails = []

def session(port, email):
    c = httpx.Client(base_url=f"http://localhost:{port}", follow_redirects=True, timeout=30)
    r = c.post("/login", data={"identifier": email, "password": PW, "next": "/"})
    assert r.status_code == 200 and "Sign in" not in r.text[:3000] or "Overview" in r.text, (port, email, r.text[:300])
    return c

def check(c, path, label, method="get", data=None):
    r = c.post(path, data=data) if method == "post" else c.get(path)
    bad = r.status_code != 200 or "Traceback" in r.text or 'class="flash error"' in r.text
    if bad:
        m = re.search(r'class="flash error">([^<]+)', r.text)
        fails.append((label, path, r.status_code, m.group(1) if m else r.text[:200]))
    return r

cu = session(8001, "rohan@example.com")
for p in ["/", "/?q=milk", "/?diet=1", "/cart", "/lists", "/lists/1", "/lists/1/items", "/stores", "/stores?q=paneer&lat=12.97&lng=77.64", "/orders", "/profile", "/instore"]:
    check(cu, p, "customer")
check(cu, "/cart/setup", "customer", "post", {"store_id": 1, "mode": "instore"})
check(cu, "/instore", "customer instore")
check(cu, "/instore/pick/1/1", "pick", "post", {"product_id": 8, "quantity": 2})
check(cu, "/cart/scan", "scan", "post", {"code": "8900000000024"})
r = check(cu, "/checkout", "checkout", "post", {"payment_method": "upi"})
oid = re.search(r"/pay/(\d+)/confirm", r.text).group(1)
r = check(cu, f"/pay/{oid}/confirm", "pay", "post", {})
code = re.search(r"(FF1\.\d+\.[0-9a-f]+\.[0-9a-f]+)", r.text).group(1)
img = cu.get(f"/orders/{oid}/receipt.png"); assert img.headers["content-type"] == "image/png"
check(cu, "/cart/setup", "customer", "post", {"store_id": 1, "mode": "pickup"})
check(cu, "/cart", "pickup cart")

for email in ["owner.blr01@freshflow.app", "manager.blr01@freshflow.app", "floor1.blr01@freshflow.app", "worker1.blr01@freshflow.app"]:
    s = session(8002, email)
    for p in ["/", "/tasks", "/tasks?status=done", "/inventory", "/inventory?low=1", "/orders", "/gate", "/shifts", "/attendance",
              "/team", "/analytics", "/analytics?period=year", "/analytics?period=today", "/analytics?period=custom&start=2026-09-01&end=2026-10-15", "/offers", "/support", "/account"]:
        r = s.get(p)
        if r.status_code != 200 or "Traceback" in r.text:
            fails.append((email, p, r.status_code, r.text[:200]))
    if email.startswith("worker"):
        r = check(s, "/gate/1/scan", "gate", "post", {"code": code})
        print("gate result:", "GATE OPEN" in r.text)

ad = session(8003, "admin@freshflow.app")
for p in ["/", "/?period=year", "/requests", "/requests?status=", "/stores", "/stores/1", "/employees", "/employees?active=", "/tickets"]:
    check(ad, p, "admin")
print("FAILURES:", len(fails))
for f in fails: print(f)

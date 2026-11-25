"""End-to-end smoke test of the one website: every role signs in on the same login page, lands in the
right section (shop "/", Store Operations "/store", Admin "/admin"), can't open the others, and the main
flows work (Scan & Go -> pay -> exit gate). Needs the API and the website running (scripts/dev.sh)."""
import re

import httpx

SITE = "http://localhost:8001"
PW = "Password@123"
fails = []


def session(email, next_url="/"):
    """Sign in on the one login page; returns the client and the page we were sent to."""
    c = httpx.Client(base_url=SITE, follow_redirects=True, timeout=30)
    r = c.post("/login", data={"identifier": email, "password": PW, "next": next_url})
    assert r.status_code == 200, (email, r.status_code, r.text[:300])
    return c, r.url.path


def check(c, path, label, method="get", data=None):
    r = c.post(path, data=data) if method == "post" else c.get(path)
    bad = r.status_code != 200 or "Traceback" in r.text or 'class="flash error"' in r.text
    if bad:
        m = re.search(r'class="flash error">([^<]+)', r.text)
        fails.append((label, path, r.status_code, m.group(1) if m else r.text[:200]))
    return r


def expect(label, got, want):
    if got != want:
        fails.append((label, f"expected {want}", f"got {got}"))


# ---- one login page, the right section for each role -----------------------------------
for email, home in [("asha@example.com", "/"), ("worker1.blr01@freshflow.app", "/store/"),
                    ("floor1.blr01@freshflow.app", "/store/"), ("manager.blr01@freshflow.app", "/store/"),
                    ("owner.blr01@freshflow.app", "/store/"), ("admin@freshflow.app", "/admin/")]:
    c, landed = session(email)
    expect(f"{email} lands on", landed, home)
    for other in ("/", "/store/", "/admin/", "/store/tasks", "/admin/stores", "/cart", "/login"):
        r = c.get(other)
        want_inside = (other == home or (home != "/" and other.startswith(home))
                       or (home == "/" and not other.startswith(("/store", "/admin")) and other != "/login"))
        if not want_inside:
            expect(f"{email} opening {other} goes home", r.url.path, home)

# signed out -> login page -> back to the page you asked for (if it's in your section)
anon = httpx.Client(base_url=SITE, follow_redirects=True, timeout=30)
expect("signed-out /store/tasks shows login", anon.get("/store/tasks").url.path, "/login")
expect("old /store/login bookmark", anon.get("/store/login").url.path, "/login")
_, landed = session("manager.blr01@freshflow.app", next_url="/store/tasks")
expect("manager returns to the page asked for", landed, "/store/tasks")
_, landed = session("asha@example.com", next_url="/store/tasks")
expect("shopper can't be sent into /store", landed, "/")

# ---- shop ------------------------------------------------------------------------------------
cu, _ = session("rohan@example.com")
for p in ["/", "/?q=milk", "/?diet=1", "/cart", "/lists", "/lists/1", "/lists/1/items", "/stores",
          "/stores?q=paneer&lat=12.97&lng=77.64", "/orders", "/profile", "/instore", "/privacy", "/account/delete"]:
    check(cu, p, "customer")
check(cu, "/cart/setup", "customer", "post", {"store_id": 1, "mode": "instore"})
check(cu, "/instore", "customer instore")
check(cu, "/instore/pick/1/1", "pick", "post", {"product_id": 8, "quantity": 2})
check(cu, "/cart/scan", "scan", "post", {"code": "8900000000241"})
r = check(cu, "/checkout", "checkout", "post", {"payment_method": "upi"})
oid = re.search(r"/pay/(\d+)/confirm", r.text).group(1)
r = check(cu, f"/pay/{oid}/confirm", "pay", "post", {})
code = re.search(r"(FF1\.\d+\.[0-9a-f]+\.[0-9a-f]+)", r.text).group(1)
img = cu.get(f"/orders/{oid}/receipt.png")
assert img.headers["content-type"] == "image/png"
check(cu, "/cart/setup", "customer", "post", {"store_id": 1, "mode": "pickup"})
check(cu, "/cart", "pickup cart")

# ---- Store Operations (/store) ----------------------------------------------------------------
for email in ["owner.blr01@freshflow.app", "manager.blr01@freshflow.app", "floor1.blr01@freshflow.app",
              "worker1.blr01@freshflow.app"]:
    s, _ = session(email)
    for p in ["/", "/tasks", "/tasks?status=done", "/inventory", "/inventory?low=1", "/orders", "/gate", "/shifts",
              "/attendance", "/team", "/analytics", "/analytics?period=year", "/analytics?period=today",
              "/analytics?period=custom&start=2026-09-01&end=2026-10-15", "/offers", "/support", "/account"]:
        r = s.get("/store" + p)
        if r.status_code != 200 or "Traceback" in r.text:
            fails.append((email, "/store" + p, r.status_code, r.text[:200]))
        elif not r.url.path.startswith("/store/"):
            fails.append((email, "/store" + p, "left the store section", r.url.path))
    links = set(re.findall(r'(?:href|action)="(/[^"#?]*)', s.get("/store/").text))
    stray = [l for l in links if not l.startswith(("/store/", "/static/", "/logout"))]
    if stray:
        fails.append((email, "links outside /store", stray))
    if email.startswith("worker"):
        r = check(s, "/store/gate/1/scan", "gate", "post", {"code": code})
        print("gate result:", "GATE OPEN" in r.text)

# ---- Admin (/admin) --------------------------------------------------------------------------
ad, _ = session("admin@freshflow.app")
for p in ["/", "/?period=year", "/requests", "/requests?status=", "/stores", "/stores/1", "/employees",
          "/employees?active=", "/tickets"]:
    check(ad, "/admin" + p, "admin")
links = set(re.findall(r'(?:href|action)="(/[^"#?]*)', ad.get("/admin/stores").text))
stray = [l for l in links if not l.startswith(("/admin/", "/static/", "/logout"))]
if stray:
    fails.append(("admin", "links outside /admin", stray))

# ---- log out once, logged out everywhere ------------------------------------------------------
ad.get("/logout")
expect("after log out /admin/ asks to sign in", ad.get("/admin/").url.path, "/login")

print("FAILURES:", len(fails))
for f in fails:
    print(f)

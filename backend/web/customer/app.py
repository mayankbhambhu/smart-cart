"""Shop section of the website ("/"): delivery/pickup, in-store Scan & Go, family lists, receipts.
It also owns the one login page for everybody. Mounted by web/main.py."""

from fastapi import Form, Request
from fastapi.responses import RedirectResponse, Response
from markupsafe import Markup

from web.shared.signin import add_signin_routes
from web.shared import WEB_UI_DIR, Api, ApiError, api_for, back, flash, login_required, make_app, render

app, templates = make_app("FreshFlow", WEB_UI_DIR / "customer" / "templates", "customer")
add_signin_routes(app, templates)  # the one login page: password, OTP, Google, email link, SSO
CUSTOMER = {"customer"}
DIETARY = ["vegan", "vegetarian", "gluten_free", "dairy_free", "organic", "sugar_free"]
ICON = {}


def page(request, name, **ctx):
    user = request.session.get("user")
    if user:
        ctx.setdefault("live_channels", [f"user:{user['id']}"])
    return render(templates, request, name, **ctx)


def icons(api: Api) -> dict:
    if not ICON:
        ICON.update({c["id"]: c["icon"] for c in api.get("/categories")})
    return ICON


# ---- auth ------------------------------------------------------------------------------
# ---- shop ------------------------------------------------------------------------------
@app.get("/")
@login_required(CUSTOMER)
async def home(request: Request, q: str = "", category_id: int | None = None, diet: int = 0):
    api = api_for(request)
    cart = api.get("/cart")
    me = api.get("/me")
    tags = ",".join(me["dietary_preferences"]) if diet and me["dietary_preferences"] else None
    products = api.get(f"/stores/{cart['store_id']}/products", q=q, category_id=category_id, tags=tags)
    return page(request, "home.html", cart=cart, me=me, products=products, q=q, category_id=category_id, diet=diet,
                categories=api.get("/categories"), stores=api.get("/stores"), icons=icons(api),
                offers=api.get(f"/stores/{cart['store_id']}/offers"),
                in_cart={i["product_id"]: i["quantity"] for i in cart["items"]})


@app.post("/cart/setup")
@login_required(CUSTOMER)
async def cart_setup(request: Request, store_id: int = Form(...), mode: str = Form(...)):
    api_for(request).post("/cart/setup", {"store_id": store_id, "mode": mode})
    return back(request)


@app.post("/cart/qty")
@login_required(CUSTOMER)
async def cart_qty(request: Request, product_id: int = Form(...), quantity: int = Form(...)):
    api_for(request).put(f"/cart/items/{product_id}", {"quantity": max(quantity, 0)})
    return back(request)


@app.post("/cart/scan")
@login_required(CUSTOMER)
async def cart_scan(request: Request, code: str = Form(...)):
    api = api_for(request)
    body = {"barcode": code.strip()} if code.strip().isdigit() and len(code.strip()) > 8 else None
    if not body:  # typed a name -> search and add the first in-stock match
        cart = api.get("/cart")
        hits = api.get(f"/stores/{cart['store_id']}/products", q=code, in_stock_only=True, limit=1)
        if not hits:
            flash(request, f"No product found for '{code}'", "error")
            return back(request)
        body = {"product_id": hits[0]["id"]}
    cart = api.post("/cart/items", body)
    flash(request, f"Added to your smart cart · total {cart['total']:.2f}")
    return back(request)


@app.post("/cart/offer")
@login_required(CUSTOMER)
async def cart_offer(request: Request, code: str = Form("")):
    cart = api_for(request).post("/cart/offer", {"code": code or None})
    if cart.get("offer_message"):
        flash(request, cart["offer_message"], "ok" if cart["discount"] else "error")
    return back(request)


@app.post("/cart/from-list/{list_id}")
@login_required(CUSTOMER)
async def cart_from_list(request: Request, list_id: int):
    r = api_for(request).post(f"/cart/from-list/{list_id}")
    flash(request, "List items added to cart" + (f" · unavailable: {', '.join(r['skipped'])}" if r["skipped"] else ""))
    return RedirectResponse("/cart", status_code=303)


@app.get("/cart")
@login_required(CUSTOMER)
async def cart_page(request: Request, day: str | None = None):
    api = api_for(request)
    cart = api.get("/cart")
    slots = api.get(f"/stores/{cart['store_id']}/pickup-slots", day=day) if cart["mode"] == "pickup" else []
    return page(request, "cart.html", cart=cart, me=api.get("/me"), slots=slots, stores=api.get("/stores"),
                lists=api.get("/lists"), methods=api.get("/me/payment-methods"))


@app.post("/checkout")
@login_required(CUSTOMER)
async def checkout(request: Request, payment_method: str = Form(...), delivery_address: str = Form(""),
                   pickup_slot: str = Form("")):
    r = api_for(request).post("/checkout", {"payment_method": payment_method,
                                            "delivery_address": delivery_address or None,
                                            "pickup_slot": pickup_slot or None})
    request.session["payment"] = r["payment"]
    return RedirectResponse(f"/pay/{r['order']['id']}", status_code=303)


@app.get("/pay/{order_id}")
@login_required(CUSTOMER)
async def pay_page(request: Request, order_id: int):
    order = api_for(request).get(f"/orders/{order_id}")
    payment = request.session.get("payment") or {}
    if order["status"] != "pending_payment":
        return RedirectResponse(f"/orders/{order_id}", status_code=303)
    return page(request, "pay.html", order=order, payment=payment)


@app.post("/pay/{order_id}/confirm")
@login_required(CUSTOMER)
async def pay_confirm(request: Request, order_id: int):
    api_for(request).post("/payments/confirm", {"order_id": order_id})
    request.session.pop("payment", None)
    flash(request, "Payment successful 🎉")
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


# ---- in-store ---------------------------------------------------------------------------
@app.get("/instore")
@login_required(CUSTOMER)
async def instore(request: Request, list_id: int | None = None):
    api = api_for(request)
    cart = api.get("/cart")
    lists = api.get("/lists")
    if cart["mode"] != "instore":
        return page(request, "instore_start.html", cart=cart, stores=api.get("/stores"), lists=lists)
    store = api.get(f"/stores/{cart['store_id']}")
    list_id = list_id or request.session.get("instore_list") or (lists[0]["id"] if lists else None)
    request.session["instore_list"] = list_id
    route = api.get(f"/lists/{list_id}/route", store_id=cart["store_id"]) if list_id else None
    shopping_list = api.get(f"/lists/{list_id}", store_id=cart["store_id"]) if list_id else None
    channels = [f"user:{request.session['user']['id']}"] + ([f"list:{list_id}"] if list_id else [])
    return page(request, "instore.html", cart=cart, store=store, lists=lists, list_id=list_id, route=route,
                shopping_list=shopping_list, live_channels=channels, methods=api.get("/me/payment-methods"))


@app.post("/instore/pick/{list_id}/{item_id}")
@login_required(CUSTOMER)
async def instore_pick(request: Request, list_id: int, item_id: int, product_id: int = Form(...),
                       quantity: int = Form(1)):
    """Shopper picked an item off the shelf: drop it in the smart cart and tick it on the family list."""
    api = api_for(request)
    api.post("/cart/items", {"product_id": product_id, "quantity": quantity})
    api.patch(f"/lists/{list_id}/items/{item_id}", {"checked": True})
    return back(request)


# ---- lists -----------------------------------------------------------------------------
@app.get("/lists")
@login_required(CUSTOMER)
async def lists_page(request: Request):
    return page(request, "lists.html", lists=api_for(request).get("/lists"))


@app.post("/lists")
@login_required(CUSTOMER)
async def create_list(request: Request, name: str = Form(...)):
    sl = api_for(request).post("/lists", {"name": name})
    return RedirectResponse(f"/lists/{sl['id']}", status_code=303)


@app.post("/lists/join")
@login_required(CUSTOMER)
async def join_list(request: Request, code: str = Form(...)):
    sl = api_for(request).post(f"/lists/join/{code.strip()}")
    flash(request, f"You joined '{sl['name']}'")
    return RedirectResponse(f"/lists/{sl['id']}", status_code=303)


@app.get("/lists/{list_id}")
@login_required(CUSTOMER)
async def list_detail(request: Request, list_id: int):
    api = api_for(request)
    cart = api.get("/cart")
    sl = api.get(f"/lists/{list_id}", store_id=cart["store_id"])
    return page(request, "list_detail.html", sl=sl, cart=cart,
                live_channels=[f"user:{request.session['user']['id']}", f"list:{list_id}"])


@app.get("/lists/{list_id}/items")
@login_required(CUSTOMER)
async def list_items_partial(request: Request, list_id: int):
    api = api_for(request)
    sl = api.get(f"/lists/{list_id}", store_id=api.get("/cart")["store_id"])
    return page(request, "_list_items.html", sl=sl)


@app.post("/lists/{list_id}/items")
@login_required(CUSTOMER)
async def add_list_item(request: Request, list_id: int, name: str = Form(...), quantity: int = Form(1)):
    api_for(request).post(f"/lists/{list_id}/items", {"name": name, "quantity": quantity})
    return back(request)


@app.post("/lists/{list_id}/items/{item_id}/toggle")
@login_required(CUSTOMER)
async def toggle_item(request: Request, list_id: int, item_id: int, checked: int = Form(...)):
    api_for(request).patch(f"/lists/{list_id}/items/{item_id}", {"checked": bool(checked)})
    return back(request)


@app.post("/lists/{list_id}/items/{item_id}/delete")
@login_required(CUSTOMER)
async def delete_item(request: Request, list_id: int, item_id: int):
    api_for(request).delete(f"/lists/{list_id}/items/{item_id}")
    return back(request)


@app.post("/lists/{list_id}/delete")
@login_required(CUSTOMER)
async def delete_list(request: Request, list_id: int):
    api_for(request).delete(f"/lists/{list_id}")
    return RedirectResponse("/lists", status_code=303)


# ---- stores & stock check -------------------------------------------------------------------
@app.get("/stores")
@login_required(CUSTOMER)
async def stores_page(request: Request, q: str = "", lat: float | None = None, lng: float | None = None):
    api = api_for(request)
    return page(request, "stores.html", stores=api.get("/stores", lat=lat, lng=lng), q=q, lat=lat, lng=lng,
                stock=api.get("/stock-check", q=q, lat=lat, lng=lng) if q else None, cart=api.get("/cart"))


# ---- demo barcode sheet -------------------------------------------------------------------
_EAN_L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
_EAN_G = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"]
_EAN_PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def ean13_svg(code: str) -> Markup:
    """An EAN-13 barcode as inline SVG, so the demo products can be scanned from a screen or paper."""
    if not (len(code) == 13 and code.isdigit()):
        return Markup("")
    right = ["".join("1" if c == "0" else "0" for c in x) for x in _EAN_L]
    bits = "101" + "".join((_EAN_L if _EAN_PARITY[int(code[0])][i] == "L" else _EAN_G)[int(d)]
                           for i, d in enumerate(code[1:7]))
    bits += "01010" + "".join(right[int(d)] for d in code[7:]) + "101"
    bars = "".join(f'<rect x="{10 + i * 2}" y="4" width="2" height="70"/>' for i, b in enumerate(bits) if b == "1")
    return Markup(f'<svg viewBox="0 0 {len(bits) * 2 + 20} 92" width="210" role="img" aria-label="Barcode {code}">'
                  f'<rect width="100%" height="100%" fill="#fff"/><g fill="#000">{bars}</g>'
                  f'<text x="50%" y="88" text-anchor="middle" font-size="12" font-family="monospace">{code}</text></svg>')


@app.get("/barcodes")
@login_required(CUSTOMER)
async def barcode_sheet(request: Request):
    """Every product's barcode at your current store: show it on another screen or print it, then
    scan it with Scan & Go (handy for demos without real product labels)."""
    api = api_for(request)
    cart = api.get("/cart")
    return page(request, "barcodes.html", store_id=cart["store_id"],
                products=api.get(f"/stores/{cart['store_id']}/products", limit=200))


templates.env.globals["ean13_svg"] = ean13_svg


@app.post("/stock/add")
@login_required(CUSTOMER)
async def stock_add(request: Request, store_id: int = Form(...), product_id: int = Form(...), product: str = Form("")):
    """"Add" on a stock-check result. The cart belongs to one store, so adding an item from another
    store moves the cart there first (as a pickup order), unless a Scan & Go trip is in progress."""
    api = api_for(request)
    cart = api.get("/cart")
    note = ""
    if cart["store_id"] != store_id:
        if cart["mode"] == "instore" and cart["items"]:
            flash(request, f"You're shopping in-store at {cart['store_name']}. Check out or empty that cart "
                           f"before adding items from another store.", "error")
            return back(request)
        before = cart["item_count"]
        cart = api.post("/cart/setup", {"store_id": store_id, "mode": "pickup" if cart["mode"] == "instore" else cart["mode"]})
        note = f" Your cart is now at {cart['store_name']}."
        if cart["item_count"] < before:
            note += " Items that store doesn't stock were removed."
    cart = api.post("/cart/items", {"product_id": product_id, "quantity": 1})
    flash(request, f"Added {product or 'item'} to your cart · {cart['item_count']} item{'' if cart['item_count'] == 1 else 's'} · total {cart['total']:.2f}.{note}")
    return back(request)


# ---- orders ----------------------------------------------------------------------------
@app.get("/orders")
@login_required(CUSTOMER)
async def orders_page(request: Request):
    return page(request, "orders.html", orders=api_for(request).get("/orders"))


@app.get("/orders/{order_id}")
@login_required(CUSTOMER)
async def order_detail(request: Request, order_id: int):
    return page(request, "order_detail.html", order=api_for(request).get(f"/orders/{order_id}"))


@app.get("/orders/{order_id}/receipt.png")
@login_required(CUSTOMER)
async def receipt_png(request: Request, order_id: int):
    return Response(api_for(request).raw(f"/orders/{order_id}/receipt.png"), media_type="image/png")


@app.post("/orders/{order_id}/cancel")
@login_required(CUSTOMER)
async def cancel_order(request: Request, order_id: int):
    api_for(request).post(f"/orders/{order_id}/cancel")
    flash(request, "Order cancelled. Refund initiated.")
    return back(request)


# ---- profile ---------------------------------------------------------------------------
@app.get("/profile")
@login_required(CUSTOMER)
async def profile(request: Request):
    api = api_for(request)
    return page(request, "profile.html", me=api.get("/me"), methods=api.get("/me/payment-methods"),
                stores=api.get("/stores"), dietary=DIETARY, notifications=api.get("/me/notifications")[:10])


@app.post("/profile")
@login_required(CUSTOMER)
async def save_profile(request: Request):
    form = await request.form()
    body = {"full_name": form.get("full_name"), "phone": form.get("phone") or None,
            "default_address": form.get("default_address"), "dietary_preferences": form.getlist("diet"),
            "preferred_store_id": int(form["preferred_store_id"]) if form.get("preferred_store_id") else None}
    user = api_for(request).patch("/me", body)
    request.session["user"] = user
    flash(request, "Profile saved")
    return back(request)


@app.post("/profile/methods")
@login_required(CUSTOMER)
async def add_method(request: Request, kind: str = Form(...), label: str = Form(...)):
    api_for(request).post("/me/payment-methods", {"kind": kind, "label": label})
    flash(request, "Payment method saved")
    return back(request)


@app.post("/profile/methods/{pm_id}/delete")
@login_required(CUSTOMER)
async def delete_method(request: Request, pm_id: int):
    api_for(request).delete(f"/me/payment-methods/{pm_id}")
    return back(request)


# ---- account deletion (public page: Google Play asks for a web link) ----------------------
@app.get("/account/delete")
async def account_delete_page(request: Request):
    return render(templates, request, "account_delete.html")


@app.post("/account/delete")
async def account_delete(request: Request, confirm: str = Form("")):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login?next=/account/delete", status_code=303)
    try:
        api_for(request).post("/me/delete", {"confirm": confirm})
    except ApiError as e:
        if e.status == 401:
            request.session.clear()
            return RedirectResponse("/login?next=/account/delete", status_code=303)
        flash(request, str(e), "error")
        return RedirectResponse("/account/delete", status_code=303)
    request.session.clear()
    return render(templates, request, "account_delete.html", deleted=True, user=None, token=None)


# ---- store map ---------------------------------------------------------------------------
def store_map(route: dict, done_keys: set | None = None) -> dict:
    """SVG geometry for the in-store map: aisles + the walking path (which only changes aisle
    through the front or back cross-aisle, mirroring the API's routing model)."""
    aisles, rows = route["layout"]["aisles"], route["layout"]["rows"]
    W, rh, top = 70, 36, 36
    H = top * 2 + (rows + 1) * rh

    def xy(a, r):
        return 40 + (a - 1) * W + 18, H - top - r * rh

    pts = [(route["start"]["aisle"], 0)] + [(s["aisle"], s["row"]) for s in route["steps"]] + [(route["end"]["aisle"], 0)]
    path = [xy(*pts[0])]
    for (a1, r1), (a2, r2) in zip(pts, pts[1:]):
        if a1 != a2:
            via = 0 if r1 + r2 <= (rows + 1 - r1) + (rows + 1 - r2) else rows + 1
            path += [xy(a1, via), xy(a2, via)]
        path.append(xy(a2, r2))
    return {"w": 40 + aisles * W + 10, "h": H, "aisles": [
        {"n": a, "x": 40 + (a - 1) * W, "y": H - top - rows * rh - rh / 2, "h": rows * rh} for a in range(1, aisles + 1)],
        "path": " ".join(f"{x:.0f},{y:.0f}" for x, y in path),
        "stops": [{"n": s["step"], "x": xy(s["aisle"], s["row"])[0], "y": xy(s["aisle"], s["row"])[1]}
                  for s in route["steps"]],
        "entrance": xy(route["start"]["aisle"], 0), "exit": xy(route["end"]["aisle"], 0)}


templates.env.globals["store_map"] = store_map

"""Cart for delivery / pickup / in-store 'smart cart' shopping."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Cart, CartItem, Inventory, Product, Store, User
from app.schemas import CartItemIn, CartQtyIn, CartSetupIn, OfferIn
from app.services.inventory import adjust_stock
from app.services.pricing import quote_cart
from app.services.routing import Stop, plan_route

router = APIRouter(prefix="/cart", tags=["cart"])


def active_cart(db: Session, user: User, create_store_id: int | None = None) -> Cart:
    cart = (db.query(Cart).options(selectinload(Cart.items).joinedload(CartItem.product))
            .filter_by(user_id=user.id, status="active").first())
    if not cart:
        store_id = create_store_id or user.preferred_store_id or db.query(Store.id).first()[0]
        cart = Cart(user_id=user.id, store_id=store_id, mode="delivery")
        db.add(cart)
        db.flush()
    return cart


def cart_dict(db: Session, cart: Cart) -> dict:
    inv = {v.product_id: v for v in db.query(Inventory).filter(
        Inventory.store_id == cart.store_id, Inventory.product_id.in_([i.product_id for i in cart.items] or [0]))}
    store = db.get(Store, cart.store_id)
    items = []
    for i in cart.items:
        v = inv.get(i.product_id)
        items.append({"product_id": i.product_id, "name": i.product.name, "unit": i.product.unit,
                      "image_url": i.product.image_url, "quantity": i.quantity, "unit_price": i.unit_price,
                      "mrp": i.product.mrp, "line_total": round(i.unit_price * i.quantity, 2),
                      "location": f"Aisle {v.aisle}, Row {v.row}" if v else None,
                      "aisle": v.aisle if v else None, "row": v.row if v else None,
                      "stock": v.quantity if v else 0, "picked": i.picked})
    return {"id": cart.id, "store_id": cart.store_id, "store_name": store.name if store else "", "mode": cart.mode,
            "items": items, "item_count": sum(i.quantity for i in cart.items), **quote_cart(db, cart).as_dict()}


def _set_line(db: Session, cart: Cart, product: Product, new_qty: int) -> None:
    line = next((i for i in cart.items if i.product_id == product.id), None)
    old_qty = line.quantity if line else 0
    delta = new_qty - old_qty
    if delta == 0:
        return
    if cart.mode == "instore":
        # Smart cart: stock leaves the shelf the moment it goes in the cart (and returns if removed).
        adjust_stock(db, cart.store_id, product.id, -delta)
    else:
        inv = db.query(Inventory).filter_by(store_id=cart.store_id, product_id=product.id).first()
        if not inv:
            raise HTTPException(404, "Not available at this store")
        if inv.quantity < new_qty:
            raise HTTPException(409, f"Only {inv.quantity} of {product.name} available")
    if new_qty == 0 and line:
        cart.items.remove(line)
        db.delete(line)
    elif line:
        line.quantity = new_qty
    else:
        cart.items.append(CartItem(product_id=product.id, quantity=new_qty, unit_price=product.price,
                                   picked=cart.mode == "instore", product=product))


def _release_instore_stock(db: Session, cart: Cart) -> None:
    if cart.mode == "instore":
        for i in cart.items:
            adjust_stock(db, cart.store_id, i.product_id, i.quantity)


@router.get("")
def get_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart = active_cart(db, user)
    db.commit()
    return cart_dict(db, cart)


@router.post("/setup")
def setup_cart(data: CartSetupIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Choose the branch and the mode. Switching mode/store re-validates the basket."""
    if not db.get(Store, data.store_id):
        raise HTTPException(404, "Store not found")
    cart = active_cart(db, user, data.store_id)
    if cart.store_id != data.store_id or cart.mode != data.mode:
        lines = [(i.product, i.quantity) for i in cart.items]
        _release_instore_stock(db, cart)
        for i in list(cart.items):
            db.delete(i)
        cart.items.clear()
        cart.store_id, cart.mode = data.store_id, data.mode
        db.flush()
        for product, qty in lines:  # carry items across when they exist at the new store
            try:
                _set_line(db, cart, product, qty)
            except HTTPException:
                pass
    db.commit()
    return cart_dict(db, cart)


@router.post("/items")
def add_to_cart(data: CartItemIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart = active_cart(db, user)
    if data.barcode:
        product = db.query(Product).filter_by(barcode=data.barcode).first()
    else:
        product = db.get(Product, data.product_id) if data.product_id else None
    if not product:
        raise HTTPException(404, "Product not found")
    line = next((i for i in cart.items if i.product_id == product.id), None)
    _set_line(db, cart, product, (line.quantity if line else 0) + data.quantity)
    db.commit()
    return cart_dict(db, cart)


@router.put("/items/{product_id}")
def set_quantity(product_id: int, data: CartQtyIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    cart = active_cart(db, user)
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    _set_line(db, cart, product, data.quantity)
    db.commit()
    return cart_dict(db, cart)


@router.delete("")
def clear_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart = active_cart(db, user)
    _release_instore_stock(db, cart)
    for i in list(cart.items):
        db.delete(i)
    cart.items.clear()
    cart.offer_code = None
    db.commit()
    return cart_dict(db, cart)


@router.post("/offer")
def apply_offer(data: OfferIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart = active_cart(db, user)
    cart.offer_code = data.code.upper().strip() if data.code else None
    db.commit()
    return cart_dict(db, cart)


@router.post("/from-list/{list_id}")
def cart_from_list(list_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """One tap: put every unchecked, in-stock item of a family list into the cart."""
    from app.api.routes.lists import get_list_for

    sl = get_list_for(db, list_id, user)
    cart = active_cart(db, user)
    skipped = []
    for item in sl.items:
        if item.checked or not item.product_id:
            continue
        product = db.get(Product, item.product_id)
        line = next((i for i in cart.items if i.product_id == product.id), None)
        try:
            _set_line(db, cart, product, (line.quantity if line else 0) + item.quantity)
        except HTTPException:
            skipped.append(item.name)
    db.commit()
    return {**cart_dict(db, cart), "skipped": skipped}


@router.get("/route")
def cart_route(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Route through the store for items in the cart that are not yet picked (pickup staff / shopper)."""
    cart = active_cart(db, user)
    store = db.get(Store, cart.store_id)
    data = cart_dict(db, cart)
    stops = [Stop(key=f"p{i['product_id']}", label=f"{i['name']} ×{i['quantity']}", aisle=i["aisle"], row=i["row"],
                  payload={"product_id": i["product_id"]}) for i in data["items"] if i["aisle"] and not i["picked"]]
    return plan_route(stops, store.aisle_count, store.rows_per_aisle)

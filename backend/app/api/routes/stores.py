"""Store locator, catalog, stock check and pickup slots (public / customer)."""
import math
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import get_db
from app.models import Category, Inventory, Offer, Order, Product, Store
from app.models._mixins import utcnow
from app.schemas import StockedProductOut, StoreOut

router = APIRouter(tags=["stores & catalog"])


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def stocked(inv: Inventory) -> dict:
    p = inv.product
    return StockedProductOut(
        **{k: getattr(p, k) for k in ("id", "sku", "barcode", "name", "brand", "category_id", "unit", "mrp",
                                      "price", "image_url", "description", "tags")},
        in_stock=inv.quantity > 0, quantity=inv.quantity, aisle=inv.aisle, row=inv.row,
        location=f"Aisle {inv.aisle}, Row {inv.row}",
    ).model_dump()


@router.get("/stores", response_model=list[StoreOut])
def list_stores(lat: float | None = None, lng: float | None = None, city: str | None = None,
                db: Session = Depends(get_db)):
    q = db.query(Store).filter(Store.is_active.is_(True))
    if city:
        q = q.filter(func.lower(Store.city) == city.lower())
    out = []
    for s in q.all():
        row = StoreOut.model_validate(s)
        if lat is not None and lng is not None:
            row.distance_km = round(haversine_km(lat, lng, s.latitude, s.longitude), 2)
        out.append(row)
    if lat is not None and lng is not None:
        out.sort(key=lambda s: s.distance_km)
    return out


@router.get("/stores/{store_id}", response_model=StoreOut)
def get_store(store_id: int, db: Session = Depends(get_db)):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(404, "Store not found")
    return store


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name, "icon": c.icon} for c in db.query(Category).order_by(Category.id)]


@router.get("/stores/{store_id}/products")
def store_products(store_id: int, q: str | None = None, category_id: int | None = None,
                   tags: str | None = Query(None, description="comma separated dietary tags"),
                   in_stock_only: bool = False, limit: int = Query(60, le=200), offset: int = 0,
                   db: Session = Depends(get_db)):
    """Catalog for a branch with live stock and shelf location. Also powers 'check stock before
    leaving home' and the in-store 'where is it?' search."""
    query = (db.query(Inventory).join(Product).options(joinedload(Inventory.product))
             .filter(Inventory.store_id == store_id, Product.is_active.is_(True)))
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(or_(func.lower(Product.name).like(like), func.lower(Product.brand).like(like),
                                 Product.barcode == q))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if in_stock_only:
        query = query.filter(Inventory.quantity > 0)
    rows = query.order_by(Product.name).offset(offset).limit(limit * 3 if tags else limit).all()
    items = [stocked(i) for i in rows]
    if tags:
        wanted = {t.strip() for t in tags.split(",") if t.strip()}
        items = [i for i in items if wanted.issubset(set(i["tags"]))][:limit]
    return items


@router.get("/stores/{store_id}/products/{product_id}")
def store_product(store_id: int, product_id: int, db: Session = Depends(get_db)):
    inv = (db.query(Inventory).options(joinedload(Inventory.product))
           .filter_by(store_id=store_id, product_id=product_id).first())
    if not inv:
        raise HTTPException(404, "Not stocked at this store")
    return stocked(inv)


@router.get("/stock-check")
def stock_check(q: str, lat: float | None = None, lng: float | None = None, db: Session = Depends(get_db)):
    """Which nearby branches have this item in stock right now?"""
    like = f"%{q.lower()}%"
    rows = (db.query(Inventory).join(Product).join(Store, Store.id == Inventory.store_id)
            .options(joinedload(Inventory.product))
            .filter(func.lower(Product.name).like(like), Store.is_active.is_(True)).limit(200).all())
    stores = {s.id: s for s in db.query(Store)}
    out = []
    for inv in rows:
        s = stores[inv.store_id]
        out.append({"store_id": s.id, "store_name": s.name, "city": s.city, "product": inv.product.name,
                    "product_id": inv.product_id, "quantity": inv.quantity, "in_stock": inv.quantity > 0,
                    "location": f"Aisle {inv.aisle}, Row {inv.row}", "price": inv.product.price,
                    "distance_km": round(haversine_km(lat, lng, s.latitude, s.longitude), 2)
                    if lat is not None and lng is not None else None})
    out.sort(key=lambda r: (not r["in_stock"], r["distance_km"] or 0))
    return out


@router.get("/stores/{store_id}/offers")
def store_offers(store_id: int, db: Session = Depends(get_db)):
    now = utcnow()
    rows = db.query(Offer).filter(Offer.is_active.is_(True), or_(Offer.store_id.is_(None), Offer.store_id == store_id),
                                  Offer.starts_at <= now, or_(Offer.ends_at.is_(None), Offer.ends_at >= now))
    return [{"id": o.id, "code": o.code, "title": o.title, "discount_percent": o.discount_percent,
             "max_discount": o.max_discount, "min_order": o.min_order, "category_id": o.category_id} for o in rows]


@router.get("/stores/{store_id}/pickup-slots")
def pickup_slots(store_id: int, day: str | None = None, db: Session = Depends(get_db)):
    """Bookable click-and-collect slots for a day (default today), with remaining capacity."""
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(404, "Store not found")
    base = datetime.fromisoformat(day) if day else utcnow()
    start = base.replace(hour=store.opens_at, minute=0, second=0, microsecond=0)
    end = base.replace(hour=store.closes_at - 1, minute=59, second=0, microsecond=0)
    earliest = utcnow() + timedelta(minutes=45)  # time needed to pick the order
    step = timedelta(minutes=settings.PICKUP_SLOT_MINUTES)
    booked: dict[datetime, int] = dict(
        db.query(Order.pickup_slot, func.count(Order.id))
        .filter(Order.store_id == store_id, Order.pickup_slot >= start, Order.pickup_slot <= end,
                Order.status != "cancelled").group_by(Order.pickup_slot).all())
    slots, t = [], start
    while t <= end:
        if t >= earliest:
            left = settings.PICKUP_SLOT_CAPACITY - booked.get(t, 0)
            slots.append({"start": t.isoformat(), "end": (t + step).isoformat(),
                          "label": f"{t:%I:%M %p} – {t + step:%I:%M %p}", "available": max(left, 0)})
        t += step
    return slots

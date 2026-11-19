"""Store operations: live inventory, restock alerts, order fulfilment, offers, gates."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.database import get_db
from app.core.deps import ALL_STAFF, MANAGERS, SUPERVISORS, ensure_store_access, require_roles
from app.core.realtime import hub
from app.models import ExitGate, GateEvent, Inventory, Offer, Order, Product, RestockAlert, User
from app.models._mixins import utcnow
from app.schemas import InventoryPatch, OfferCreateIn, OrderStatusIn
from app.services.inventory import adjust_stock
from app.services.notify import notify

router = APIRouter(prefix="/ops/stores/{store_id}", tags=["store operations"])
staff = require_roles(*ALL_STAFF)


@router.get("/inventory")
def inventory(store_id: int, q: str | None = None, low_only: bool = False, user: User = Depends(staff),
              db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    query = db.query(Inventory).join(Product).options(joinedload(Inventory.product)).filter(Inventory.store_id == store_id)
    if q:
        query = query.filter(func.lower(Product.name).like(f"%{q.lower()}%"))
    if low_only:
        query = query.filter(Inventory.quantity <= Inventory.low_stock_threshold)
    return [{"id": i.id, "product_id": i.product_id, "name": i.product.name, "sku": i.product.sku,
             "quantity": i.quantity, "aisle": i.aisle, "row": i.row, "threshold": i.low_stock_threshold,
             "restock_to": i.restock_to, "low": i.is_low, "price": i.product.price}
            for i in query.order_by(Inventory.aisle, Inventory.row, Product.name).all()]


@router.patch("/inventory/{inventory_id}")
def update_inventory(store_id: int, inventory_id: int, data: InventoryPatch, user: User = Depends(staff),
                     db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    inv = db.get(Inventory, inventory_id)
    if not inv or inv.store_id != store_id:
        raise HTTPException(404, "Not found")
    changes = data.model_dump(exclude_unset=True)
    if user.role == "worker" and set(changes) - {"quantity_delta"}:
        raise HTTPException(403, "Workers can only record restocks")
    if "quantity" in changes:
        adjust_stock(db, store_id, inv.product_id, changes.pop("quantity") - inv.quantity)
    if "quantity_delta" in changes:
        adjust_stock(db, store_id, inv.product_id, changes.pop("quantity_delta"))
    for k, v in changes.items():
        setattr(inv, k, v)
    db.commit()
    hub.publish(f"store:{store_id}", "inventory", {"inventory_id": inv.id, "product_id": inv.product_id,
                                                   "quantity": inv.quantity, "aisle": inv.aisle, "row": inv.row,
                                                   "low": inv.is_low})
    return {"id": inv.id, "quantity": inv.quantity, "aisle": inv.aisle, "row": inv.row, "low": inv.is_low}


@router.get("/alerts")
def restock_alerts(store_id: int, include_resolved: bool = False, user: User = Depends(staff),
                   db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    q = db.query(RestockAlert).options(joinedload(RestockAlert.inventory).joinedload(Inventory.product)) \
        .filter(RestockAlert.store_id == store_id)
    if not include_resolved:
        q = q.filter(RestockAlert.status != "resolved")
    return [{"id": a.id, "product": a.inventory.product.name, "aisle": a.inventory.aisle, "row": a.inventory.row,
             "quantity_now": a.inventory.quantity, "quantity_at_alert": a.quantity_at_alert, "status": a.status,
             "task_id": a.task_id, "created_at": a.created_at} for a in q.order_by(RestockAlert.id.desc()).limit(100)]


@router.get("/orders")
def store_orders(store_id: int, status: str | None = None, fulfilment: str | None = None,
                 user: User = Depends(staff), db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    q = db.query(Order).options(selectinload(Order.items)).filter(Order.store_id == store_id,
                                                                  Order.status != "pending_payment")
    if status:
        q = q.filter(Order.status == status)
    if fulfilment:
        q = q.filter(Order.fulfilment == fulfilment)
    users = {}
    out = []
    for o in q.order_by(Order.id.desc()).limit(150):
        if o.user_id not in users:
            u = db.get(User, o.user_id)
            users[o.user_id] = u.full_name or u.phone or u.email
        out.append({"id": o.id, "number": o.number, "customer": users[o.user_id], "fulfilment": o.fulfilment,
                    "status": o.status, "total": o.total, "paid_at": o.paid_at, "pickup_slot": o.pickup_slot,
                    "delivery_address": o.delivery_address, "exit_verified_at": o.exit_verified_at,
                    "items": [{"name": i.name, "quantity": i.quantity,
                               "location": f"A{i.aisle}-R{i.row}" if i.aisle else ""} for i in o.items]})
    return out


@router.post("/orders/{order_id}/status")
def set_order_status(store_id: int, order_id: int, data: OrderStatusIn, user: User = Depends(staff),
                     db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    order = db.get(Order, order_id)
    if not order or order.store_id != store_id:
        raise HTTPException(404, "Order not found")
    order.status = data.status
    messages = {"ready": "Your order is packed and ready for pickup!",
                "out_for_delivery": "Your order is on the way 🚴",
                "completed": "Order completed. Thanks for shopping!",
                "cancelled": "Your order was cancelled by the store. A refund has been initiated."}
    if data.status in messages:
        notify(db, order.user_id, "order", f"Order {order.number}", messages[data.status], link=f"/orders/{order.id}")
    if data.status == "cancelled":
        for it in order.items:
            adjust_stock(db, store_id, it.product_id, it.quantity)
    db.commit()
    hub.publish(f"store:{store_id}", "order_status", {"order_id": order.id, "status": order.status})
    return {"id": order.id, "status": order.status}


@router.get("/gates")
def gates(store_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    gs = db.query(ExitGate).filter_by(store_id=store_id).all()
    events = (db.query(GateEvent).filter(GateEvent.gate_id.in_([g.id for g in gs] or [0]))
              .order_by(GateEvent.id.desc()).limit(30).all())
    show_keys = user.role in ("owner", "store_manager", "admin")
    return {"gates": [{"id": g.id, "name": g.name, "active": g.is_active,
                       "api_key": g.api_key if show_keys else None} for g in gs],
            "events": [{"id": e.id, "gate_id": e.gate_id, "opened": e.opened, "reason": e.reason,
                        "order_id": e.order_id, "at": e.created_at} for e in events]}


@router.get("/offers")
def offers(store_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    rows = db.query(Offer).filter((Offer.store_id == store_id) | Offer.store_id.is_(None)).order_by(Offer.id.desc())
    return [{"id": o.id, "code": o.code, "title": o.title, "discount_percent": o.discount_percent,
             "max_discount": o.max_discount, "min_order": o.min_order, "is_active": o.is_active,
             "global": o.store_id is None, "ends_at": o.ends_at} for o in rows]


@router.post("/offers", status_code=201)
def create_offer(store_id: int, data: OfferCreateIn, user: User = Depends(require_roles(*MANAGERS)),
                 db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    if db.query(Offer).filter_by(code=data.code.upper()).first():
        raise HTTPException(409, "Offer code already exists")
    o = Offer(store_id=store_id, **{**data.model_dump(), "code": data.code.upper()}, starts_at=utcnow())
    db.add(o)
    db.commit()
    return {"id": o.id, "code": o.code}


@router.post("/offers/{offer_id}/toggle")
def toggle_offer(store_id: int, offer_id: int, user: User = Depends(require_roles(*MANAGERS)),
                 db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    o = db.get(Offer, offer_id)
    if not o or o.store_id != store_id:
        raise HTTPException(404, "Offer not found (platform-wide offers are managed by admin)")
    o.is_active = not o.is_active
    db.commit()
    return {"id": o.id, "is_active": o.is_active}


_ = SUPERVISORS  # exported for symmetry

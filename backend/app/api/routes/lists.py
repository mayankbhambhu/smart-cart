"""Collaborative family shopping lists with live sync."""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.realtime import hub
from app.models import Inventory, ListItem, ListMember, Product, ShoppingList, Store, User
from app.schemas import ListCreateIn, ListItemIn, ListItemPatch
from app.services.routing import Stop, plan_route

router = APIRouter(prefix="/lists", tags=["shopping lists"])


def _member_ids(sl: ShoppingList) -> set[int]:
    return {sl.owner_id} | {m.user_id for m in sl.members}


def get_list_for(db: Session, list_id: int, user: User) -> ShoppingList:
    sl = db.query(ShoppingList).options(selectinload(ShoppingList.items), selectinload(ShoppingList.members)) \
        .filter_by(id=list_id).first()
    if not sl or user.id not in _member_ids(sl):
        raise HTTPException(404, "List not found")
    return sl


def item_dict(i: ListItem, names: dict[int, str]) -> dict:
    return {"id": i.id, "name": i.name, "product_id": i.product_id, "quantity": i.quantity, "checked": i.checked,
            "added_by": names.get(i.added_by_id, ""), "updated_at": i.updated_at}


def list_dict(db: Session, sl: ShoppingList, store_id: int | None = None) -> dict:
    ids = _member_ids(sl) | {i.added_by_id for i in sl.items if i.added_by_id}
    names = {u.id: u.full_name or u.email or u.phone for u in db.query(User).filter(User.id.in_(ids))}
    items = [item_dict(i, names) for i in sl.items]
    if store_id:  # annotate with location + stock at the chosen store
        pids = [i.product_id for i in sl.items if i.product_id]
        inv = {v.product_id: v for v in db.query(Inventory).filter(Inventory.store_id == store_id,
                                                                     Inventory.product_id.in_(pids or [0]))}
        prices = {p.id: p.price for p in db.query(Product).filter(Product.id.in_(pids or [0]))}
        total = 0.0
        for it in items:
            v = inv.get(it["product_id"])
            it["location"] = f"Aisle {v.aisle}, Row {v.row}" if v else None
            it["in_stock"] = bool(v and v.quantity >= it["quantity"])
            it["price"] = prices.get(it["product_id"])
            if it["price"] and not it["checked"]:
                total += it["price"] * it["quantity"]
        return {**_head(sl, names), "items": items, "estimated_total": round(total, 2)}
    return {**_head(sl, names), "items": items}


def _head(sl: ShoppingList, names: dict[int, str]) -> dict:
    return {"id": sl.id, "name": sl.name, "owner_id": sl.owner_id, "invite_code": sl.invite_code,
            "members": [{"id": uid, "name": names.get(uid, "")} for uid in sorted(_member_ids(sl))]}


def _broadcast(db: Session, sl: ShoppingList, event: str, actor: User, extra: dict | None = None) -> None:
    db.refresh(sl)
    hub.publish(f"list:{sl.id}", event, {"actor": actor.full_name, "list": list_dict(db, sl), **(extra or {})})


@router.get("")
def my_lists(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member_of = [m.list_id for m in db.query(ListMember).filter_by(user_id=user.id)]
    lists = db.query(ShoppingList).filter((ShoppingList.owner_id == user.id) | ShoppingList.id.in_(member_of or [0]))
    return [{"id": sl.id, "name": sl.name, "invite_code": sl.invite_code, "owner_id": sl.owner_id,
             "item_count": len(sl.items), "open_count": sum(not i.checked for i in sl.items),
             "member_count": len(sl.members) + 1} for sl in lists]


@router.post("", status_code=201)
def create_list(data: ListCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sl = ShoppingList(name=data.name, owner_id=user.id, invite_code=secrets.token_urlsafe(6)[:8].upper())
    db.add(sl)
    db.commit()
    return list_dict(db, sl)


@router.get("/{list_id}")
def get_list(list_id: int, store_id: int | None = None, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    return list_dict(db, get_list_for(db, list_id, user), store_id)


@router.post("/join/{invite_code}")
def join_list(invite_code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sl = db.query(ShoppingList).filter_by(invite_code=invite_code.upper()).first()
    if not sl:
        raise HTTPException(404, "Invite code not found")
    if user.id not in _member_ids(sl):
        db.add(ListMember(list_id=sl.id, user_id=user.id))
        db.commit()
        _broadcast(db, sl, "member_joined", user)
    return list_dict(db, sl)


@router.delete("/{list_id}", status_code=204)
def delete_list(list_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sl = get_list_for(db, list_id, user)
    if sl.owner_id == user.id:
        db.delete(sl)
    else:  # members just leave
        db.query(ListMember).filter_by(list_id=sl.id, user_id=user.id).delete()
    db.commit()


@router.post("/{list_id}/items", status_code=201)
def add_item(list_id: int, data: ListItemIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sl = get_list_for(db, list_id, user)
    name = data.name
    if data.product_id:
        product = db.get(Product, data.product_id)
        if not product:
            raise HTTPException(404, "Product not found")
        name = product.name
        existing = next((i for i in sl.items if i.product_id == product.id and not i.checked), None)
        if existing:
            existing.quantity += data.quantity
            db.commit()
            _broadcast(db, sl, "item_updated", user, {"item": existing.name})
            return list_dict(db, sl)
    if not name:
        raise HTTPException(400, "Give an item name or product_id")
    if not data.product_id:  # free text ("milk") -> best catalogue match so it can be located in store
        match = db.query(Product).filter(Product.name.ilike(f"%{name}%")).order_by(Product.price).first()
        data.product_id = match.id if match else None
    db.add(ListItem(list_id=sl.id, name=name, product_id=data.product_id, quantity=data.quantity,
                    added_by_id=user.id))
    db.commit()
    _broadcast(db, sl, "item_added", user, {"item": name})
    return list_dict(db, sl)


@router.patch("/{list_id}/items/{item_id}")
def update_item(list_id: int, item_id: int, data: ListItemPatch, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    sl = get_list_for(db, list_id, user)
    item = next((i for i in sl.items if i.id == item_id), None)
    if not item:
        raise HTTPException(404, "Item not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit()
    _broadcast(db, sl, "item_updated", user, {"item": item.name})
    return list_dict(db, sl)


@router.delete("/{list_id}/items/{item_id}")
def delete_item(list_id: int, item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sl = get_list_for(db, list_id, user)
    item = next((i for i in sl.items if i.id == item_id), None)
    if not item:
        raise HTTPException(404, "Item not found")
    name = item.name
    db.delete(item)
    db.commit()
    _broadcast(db, sl, "item_removed", user, {"item": name})
    return list_dict(db, sl)


@router.get("/{list_id}/route")
def list_route(list_id: int, store_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Optimised walk through the aisles for the unchecked items on this list."""
    sl = get_list_for(db, list_id, user)
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(404, "Store not found")
    pending = [i for i in sl.items if not i.checked and i.product_id]
    inv = {v.product_id: v for v in db.query(Inventory).filter(
        Inventory.store_id == store_id, Inventory.product_id.in_([i.product_id for i in pending] or [0]))}
    stops, missing = [], []
    for i in pending:
        v = inv.get(i.product_id)
        if not v or v.quantity <= 0:
            missing.append(i.name)
            continue
        stops.append(Stop(key=f"list-item-{i.id}", label=f"{i.name} ×{i.quantity}", aisle=v.aisle, row=v.row,
                          payload={"list_item_id": i.id, "product_id": i.product_id, "quantity": i.quantity,
                                   "price": v.product.price}))
    route = plan_route(stops, store.aisle_count, store.rows_per_aisle)
    route["unavailable"] = missing + [i.name for i in sl.items if not i.checked and not i.product_id]
    route["estimated_total"] = round(sum(s.payload["price"] * s.payload["quantity"] for s in stops), 2)
    return route

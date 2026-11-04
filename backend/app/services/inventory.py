"""Stock movements. Every change is broadcast to the store channel; crossing the low-stock
threshold raises a RestockAlert, auto-assigns a restock task and alerts staff."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.realtime import hub
from app.models import Inventory, RestockAlert, Role, Task, User
from app.models._mixins import utcnow
from app.services.notify import notify, notify_roles


def get_inventory(db: Session, store_id: int, product_id: int, lock: bool = False) -> Inventory:
    q = db.query(Inventory).filter_by(store_id=store_id, product_id=product_id)
    if lock and db.bind.dialect.name == "postgresql":
        q = q.with_for_update()
    inv = q.first()
    if not inv:
        raise HTTPException(404, "Product is not stocked at this store")
    return inv


def _publish(inv: Inventory) -> None:
    hub.publish(f"store:{inv.store_id}", "inventory", {
        "inventory_id": inv.id, "product_id": inv.product_id, "quantity": inv.quantity,
        "aisle": inv.aisle, "row": inv.row, "low": inv.is_low,
    })


def adjust_stock(db: Session, store_id: int, product_id: int, delta: int) -> Inventory:
    inv = get_inventory(db, store_id, product_id, lock=True)
    if delta < 0 and inv.quantity + delta < 0:
        raise HTTPException(409, f"Only {inv.quantity} left in stock")
    was_low = inv.is_low
    inv.quantity += delta
    db.flush()
    _publish(inv)
    if inv.is_low and not was_low:
        raise_restock_alert(db, inv)
    elif not inv.is_low:
        for alert in db.query(RestockAlert).filter(RestockAlert.inventory_id == inv.id,
                                                   RestockAlert.status != "resolved"):
            alert.status = "resolved"
            alert.resolved_at = utcnow()
    return inv


def raise_restock_alert(db: Session, inv: Inventory) -> RestockAlert | None:
    open_alert = db.query(RestockAlert).filter(RestockAlert.inventory_id == inv.id,
                                               RestockAlert.status != "resolved").first()
    if open_alert:
        return None
    alert = RestockAlert(store_id=inv.store_id, inventory_id=inv.id, quantity_at_alert=inv.quantity)
    db.add(alert)
    db.flush()

    name = inv.product.name
    title = f"Restock {name} — Aisle {inv.aisle}, Row {inv.row}"
    body = f"Only {inv.quantity} left (threshold {inv.low_stock_threshold}). Refill to {inv.restock_to}."

    # Auto-assign to the on-floor worker with the fewest open tasks, if any exist.
    workers = db.query(User).filter(User.store_id == inv.store_id, User.role == Role.WORKER.value,
                                    User.is_active.is_(True)).all()
    manager = db.query(User).filter(User.store_id == inv.store_id,
                                    User.role.in_([Role.FLOOR_MANAGER.value, Role.STORE_MANAGER.value])).first()
    if workers and manager:
        def open_tasks(u: User) -> int:
            return db.query(Task).filter(Task.assigned_to_id == u.id,
                                         Task.status.in_(["assigned", "in_progress"])).count()
        worker = min(workers, key=open_tasks)
        task = Task(store_id=inv.store_id, title=title, description=body, priority="high",
                    assigned_to_id=worker.id, assigned_by_id=manager.id)
        db.add(task)
        db.flush()
        alert.task_id, alert.status = task.id, "assigned"
        notify(db, worker.id, "task", f"New task: {title}", body, link=f"/tasks/{task.id}")

    notify_roles(db, inv.store_id, [Role.FLOOR_MANAGER, Role.STORE_MANAGER], "restock", title, body)
    hub.publish(f"store:{inv.store_id}", "restock_alert",
                {"alert_id": alert.id, "product": name, "aisle": inv.aisle, "row": inv.row,
                 "quantity": inv.quantity})
    return alert

"""Exit gate verification. The gate hardware (or the gate simulator in the store dashboard)
scans the shopper's receipt QR and asks the API whether to open."""
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import ALL_STAFF, ensure_store_access, require_roles
from app.core.realtime import hub
from app.core.security import parse_receipt_code
from app.models import ExitGate, GateEvent, Order, User
from app.models._mixins import utcnow
from app.schemas import GateVerifyIn

router = APIRouter(prefix="/gate", tags=["exit gate"])
PAID_STATES = {"paid", "completed", "ready"}


def verify_at_gate(db: Session, gate: ExitGate, code: str) -> dict:
    def result(opened: bool, reason: str, order: Order | None = None) -> dict:
        db.add(GateEvent(gate_id=gate.id, order_id=order.id if order else None, opened=opened, reason=reason))
        db.commit()
        payload = {"open": opened, "reason": reason, "gate": gate.name,
                   "order_number": order.number if order else None,
                   "items": sum(i.quantity for i in order.items) if order else None,
                   "total": order.total if order else None}
        hub.publish(f"store:{gate.store_id}", "gate", payload)
        return payload

    parsed = parse_receipt_code(code)
    if not parsed:
        return result(False, "Invalid or forged code")
    order = db.get(Order, parsed[0])
    if not order or order.receipt_nonce != parsed[1]:
        return result(False, "Receipt not found")
    if order.store_id != gate.store_id:
        return result(False, "Receipt belongs to a different store", order)
    if order.status not in PAID_STATES:
        return result(False, f"Order is {order.status.replace('_', ' ')}", order)
    if order.exit_verified_at:
        # allow a re-scan within 2 minutes (shopper tapped twice), otherwise block reuse
        if utcnow() - order.exit_verified_at > timedelta(minutes=2):
            return result(False, "Receipt already used", order)
        return result(True, "Already verified — gate open", order)
    if order.paid_at and utcnow() - order.paid_at > timedelta(hours=settings.RECEIPT_VALID_HOURS):
        return result(False, "Receipt expired — please see staff", order)
    order.exit_verified_at = utcnow()
    if order.fulfilment in ("instore", "pickup"):
        order.status = "completed"
    return result(True, "Payment verified — have a nice day!", order)


@router.post("/verify")
def gate_verify(data: GateVerifyIn, x_gate_key: str = Header(...), db: Session = Depends(get_db)):
    gate = db.query(ExitGate).filter_by(api_key=x_gate_key, is_active=True).first()
    if not gate:
        raise HTTPException(401, "Unknown gate")
    return verify_at_gate(db, gate, data.code)


@router.post("/{gate_id}/simulate")
def gate_simulate(gate_id: int, data: GateVerifyIn, user: User = Depends(require_roles(*ALL_STAFF)),
                  db: Session = Depends(get_db)):
    """Staff-side gate simulator / manual override scanner."""
    gate = db.get(ExitGate, gate_id)
    if not gate:
        raise HTTPException(404, "Gate not found")
    ensure_store_access(user, gate.store_id)
    return verify_at_gate(db, gate, data.code)

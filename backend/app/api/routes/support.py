from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import MANAGERS, ensure_store_access, require_roles
from app.core.realtime import hub
from app.models import Role, SupportTicket, User
from app.schemas import TicketIn
from app.services.notify import notify

router = APIRouter(prefix="/ops/stores/{store_id}/tickets", tags=["support"])


def ticket_dict(t: SupportTicket, db: Session) -> dict:
    by = db.get(User, t.raised_by_id)
    return {"id": t.id, "store_id": t.store_id, "category": t.category, "priority": t.priority,
            "subject": t.subject, "description": t.description, "status": t.status,
            "admin_response": t.admin_response, "raised_by": by.full_name if by else "",
            "created_at": t.created_at, "updated_at": t.updated_at, "resolved_at": t.resolved_at}


@router.get("")
def list_tickets(store_id: int, user: User = Depends(require_roles(*MANAGERS)), db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    return [ticket_dict(t, db) for t in db.query(SupportTicket).filter_by(store_id=store_id)
            .order_by(SupportTicket.id.desc())]


@router.post("", status_code=201)
def raise_ticket(store_id: int, data: TicketIn, user: User = Depends(require_roles(*MANAGERS)),
                 db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    t = SupportTicket(store_id=store_id, raised_by_id=user.id, **data.model_dump())
    db.add(t)
    db.flush()
    for admin in db.query(User).filter_by(role=Role.ADMIN.value, is_active=True):
        notify(db, admin.id, "ticket", f"[{t.priority}] {t.subject}", f"Store #{store_id} · {t.category}",
               link="/tickets")
    db.commit()
    hub.publish("admin", "ticket", {"id": t.id, "store_id": store_id, "subject": t.subject, "priority": t.priority})
    return ticket_dict(t, db)

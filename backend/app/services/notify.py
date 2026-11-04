"""Persisted notifications + live push over WebSocket."""
from sqlalchemy.orm import Session

from app.core.realtime import hub
from app.models import Notification, Role, User


def notify(db: Session, user_id: int, kind: str, title: str, body: str = "", link: str | None = None) -> None:
    n = Notification(user_id=user_id, kind=kind, title=title, body=body, link=link)
    db.add(n)
    db.flush()
    hub.publish(f"user:{user_id}", "notification",
                {"id": n.id, "kind": kind, "title": title, "body": body, "link": link})


def notify_roles(db: Session, store_id: int | None, roles: list[Role], kind: str, title: str, body: str = "",
                 link: str | None = None) -> None:
    q = db.query(User).filter(User.role.in_([r.value for r in roles]), User.is_active.is_(True))
    if store_id is not None:
        q = q.filter(User.store_id == store_id)
    for u in q.all():
        notify(db, u.id, kind, title, body, link)

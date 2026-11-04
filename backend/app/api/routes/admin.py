"""Platform admin (your team): credential approvals, stores, employees, support tickets."""
import secrets
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.routes.people import cred_dict, user_brief
from app.api.routes.support import ticket_dict
from app.core.database import get_db
from app.core.deps import require_roles
from app.core.realtime import hub
from app.core.security import generate_temp_password, hash_password
from app.models import (Attendance, CredentialRequest, CredentialStatus, ExitGate, Order, Role, Store,
                        SupportTicket, Task, User)
from app.models._mixins import utcnow
from app.schemas import ReviewIn, StoreCreateIn, TicketResponseIn
from app.services.analytics import resolve_range, store_report
from app.services.notify import notify

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = require_roles(Role.ADMIN)


def _employee_code(db: Session, store: Store) -> str:
    n = db.query(User).filter(User.store_id == store.id).count() + 1
    code = f"{store.code}-{n:04d}"
    while db.query(User).filter_by(employee_code=code).first():
        n += 1
        code = f"{store.code}-{n:04d}"
    return code


@router.get("/overview")
def overview(period: str = "month", user: User = Depends(admin_only), db: Session = Depends(get_db)):
    s, e = resolve_range(period, None, None)
    report = store_report(db, None, s, e)
    per_store = dict(db.query(Order.store_id, func.sum(Order.subtotal - Order.discount))
                     .filter(Order.paid_at >= s, Order.paid_at <= e, Order.status != "cancelled")
                     .group_by(Order.store_id).all())
    return {
        "kpis": report["kpis"], "series": report["series"],
        "counts": {
            "stores": db.query(Store).count(),
            "employees": db.query(User).filter(User.role.in_(["worker", "floor_manager", "store_manager"]),
                                               User.is_active.is_(True)).count(),
            "customers": db.query(User).filter_by(role="customer").count(),
            "pending_requests": db.query(CredentialRequest).filter_by(status="pending_admin").count(),
            "open_tickets": db.query(SupportTicket).filter(SupportTicket.status != "resolved").count(),
        },
        "store_sales": [{"store_id": st.id, "name": st.name, "net_sales": round(per_store.get(st.id) or 0, 2)}
                        for st in db.query(Store).all()],
    }


# ---- Credential requests -------------------------------------------------------------
@router.get("/credential-requests")
def all_requests(status: str | None = None, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    q = db.query(CredentialRequest)
    if status:
        q = q.filter_by(status=status)
    stores = {s.id: s.name for s in db.query(Store)}
    return [{**cred_dict(r, db), "store_name": stores.get(r.store_id)} for r in q.order_by(CredentialRequest.id.desc())]


@router.post("/credential-requests/{req_id}/review")
def admin_review(req_id: int, data: ReviewIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    r = db.get(CredentialRequest, req_id)
    if not r:
        raise HTTPException(404, "Request not found")
    if r.status != CredentialStatus.PENDING_ADMIN.value:
        raise HTTPException(409, f"Request is {r.status}, not waiting for admin")
    r.admin_note, r.admin_reviewed_at = data.note, utcnow()
    owner_and_manager = [r.requested_by_id] + [u.id for u in db.query(User).filter_by(store_id=r.store_id, role="owner")]
    result: dict = {}
    if data.decision == "approve":
        if db.query(User).filter(User.email == r.email).first():
            raise HTTPException(409, "A user with this email already exists")
        store = db.get(Store, r.store_id)
        temp = generate_temp_password()
        emp = User(full_name=r.full_name, email=r.email, phone=r.phone, role=r.role, store_id=r.store_id,
                   hourly_wage=r.hourly_wage, joined_on=r.joining_date, employee_code=_employee_code(db, store),
                   password_hash=hash_password(temp), must_change_password=True, auth_provider="email")
        db.add(emp)
        db.flush()
        r.status, r.created_user_id = CredentialStatus.APPROVED.value, emp.id
        for uid in owner_and_manager:
            notify(db, uid, "credential", f"Credentials issued for {r.full_name}",
                   f"Employee code {emp.employee_code}. Login details were shared by the admin team.")
        # Credentials are shown once to the admin, who shares them securely with the employee.
        result = {"credentials": {"login": emp.email, "temporary_password": temp,
                                  "employee_code": emp.employee_code}}
    elif data.decision == "send_back":
        r.status, r.sent_back_by = CredentialStatus.CHANGES_REQUESTED.value, "admin"
        for uid in owner_and_manager:
            notify(db, uid, "credential", f"Admin requested changes: {r.full_name}", data.note, link="/team/requests")
    else:
        r.status = CredentialStatus.REJECTED.value
        for uid in owner_and_manager:
            notify(db, uid, "credential", f"Admin rejected request: {r.full_name}", data.note)
    db.commit()
    return {**cred_dict(r, db), **result}


# ---- Stores ----------------------------------------------------------------------------
@router.get("/stores")
def stores(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    out = []
    for s in db.query(Store).order_by(Store.id):
        owner = db.get(User, s.owner_id) if s.owner_id else None
        staff = db.query(User).filter(User.store_id == s.id, User.is_active.is_(True)).all()
        out.append({"id": s.id, "code": s.code, "name": s.name, "city": s.city, "address": s.address,
                    "is_active": s.is_active, "phone": s.phone,
                    "owner": {"id": owner.id, "name": owner.full_name, "email": owner.email,
                              "phone": owner.phone} if owner else None,
                    "employee_count": sum(u.role != "owner" for u in staff),
                    "monthly_wage_bill_estimate": round(sum((u.hourly_wage or 0) * 8 * 26 for u in staff
                                                            if u.role != "owner"), 2)})
    return out


@router.post("/stores", status_code=201)
def create_store(data: StoreCreateIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.query(Store).filter_by(code=data.code.upper()).first():
        raise HTTPException(409, "Store code already used")
    if db.query(User).filter_by(email=data.owner_email.lower()).first():
        raise HTTPException(409, "Owner email already registered")
    fields = data.model_dump(exclude={"owner_name", "owner_email", "owner_phone"})
    store = Store(**{**fields, "code": data.code.upper()})
    db.add(store)
    db.flush()
    temp = generate_temp_password()
    owner = User(full_name=data.owner_name, email=data.owner_email.lower(), phone=data.owner_phone, role="owner",
                 store_id=store.id, password_hash=hash_password(temp), must_change_password=True,
                 employee_code=f"{store.code}-OWNER", joined_on=date.today())
    db.add(owner)
    db.flush()
    store.owner_id = owner.id
    db.add(ExitGate(store_id=store.id, name="Exit Gate 1", api_key=secrets.token_hex(24)))
    db.commit()
    return {"store_id": store.id, "owner_credentials": {"login": owner.email, "temporary_password": temp}}


@router.get("/stores/{store_id}")
def store_detail(store_id: int, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    s = db.get(Store, store_id)
    if not s:
        raise HTTPException(404, "Store not found")
    month = resolve_range("month", None, None)
    owner = db.get(User, s.owner_id) if s.owner_id else None
    employees = db.query(User).filter(User.store_id == store_id).order_by(User.is_active.desc(), User.role).all()
    return {"store": {"id": s.id, "code": s.code, "name": s.name, "address": s.address, "city": s.city,
                      "phone": s.phone, "is_active": s.is_active, "aisles": s.aisle_count, "rows": s.rows_per_aisle},
            "owner": user_brief(owner) if owner else None,
            "employees": [user_brief(u) for u in employees if u.role != "owner"],
            "month_kpis": store_report(db, store_id, *month)["kpis"],
            "tickets": [ticket_dict(t, db) for t in db.query(SupportTicket).filter_by(store_id=store_id)
                        .order_by(SupportTicket.id.desc()).limit(10)]}


@router.post("/stores/{store_id}/toggle")
def toggle_store(store_id: int, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    s = db.get(Store, store_id)
    if not s:
        raise HTTPException(404, "Store not found")
    s.is_active = not s.is_active
    db.commit()
    return {"id": s.id, "is_active": s.is_active}


# ---- Employees -------------------------------------------------------------------------
@router.get("/employees")
def employees(store_id: int | None = None, role: str | None = None, active: bool | None = None, q: str | None = None,
              user: User = Depends(admin_only), db: Session = Depends(get_db)):
    query = db.query(User).filter(User.role.in_([r.value for r in (Role.OWNER, Role.STORE_MANAGER,
                                                                     Role.FLOOR_MANAGER, Role.WORKER)]))
    if store_id:
        query = query.filter(User.store_id == store_id)
    if role:
        query = query.filter(User.role == role)
    if active is not None:
        query = query.filter(User.is_active.is_(active))
    if q:
        query = query.filter(func.lower(User.full_name).like(f"%{q.lower()}%"))
    stores = {s.id: s.name for s in db.query(Store)}
    return [{**user_brief(u), "store_id": u.store_id, "store_name": stores.get(u.store_id), "left_on": u.left_on}
            for u in query.order_by(User.store_id, User.role, User.full_name)]


@router.delete("/employees/{user_id}")
def offboard_employee(user_id: int, reason: str = "left", user: User = Depends(admin_only),
                      db: Session = Depends(get_db)):
    """Remove an employee who left or was fired: login is revoked immediately and personal
    credentials are wiped. Attendance and task history are kept for payroll and audit."""
    emp = db.get(User, user_id)
    if not emp or not emp.is_staff:
        raise HTTPException(404, "Employee not found")
    if emp.role == Role.OWNER.value:
        raise HTTPException(409, "Reassign the store owner before removing them")
    emp.is_active = False
    emp.left_on = date.today()
    emp.password_hash = None
    emp.provider_subject = None
    db.query(Attendance).filter_by(user_id=emp.id, clock_out=None).update({"clock_out": utcnow()})
    db.query(Task).filter(Task.assigned_to_id == emp.id, Task.status.in_(["assigned", "in_progress"])) \
        .update({"status": "assigned", "description": Task.description + f"\n[Reassign: {emp.full_name} {reason}]"},
                synchronize_session=False)
    db.commit()
    hub.publish(f"store:{emp.store_id}", "employee_removed", {"user_id": emp.id, "name": emp.full_name})
    return {"ok": True, "user_id": emp.id, "reason": reason}


@router.post("/employees/{user_id}/reset-password")
def reset_password(user_id: int, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    emp = db.get(User, user_id)
    if not emp or not emp.is_active:
        raise HTTPException(404, "Active employee not found")
    temp = generate_temp_password()
    emp.password_hash, emp.must_change_password = hash_password(temp), True
    db.commit()
    return {"login": emp.email, "temporary_password": temp}


# ---- Support tickets -------------------------------------------------------------------
@router.get("/tickets")
def tickets(status: str | None = None, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    q = db.query(SupportTicket)
    if status:
        q = q.filter_by(status=status)
    stores = {s.id: s.name for s in db.query(Store)}
    return [{**ticket_dict(t, db), "store_name": stores.get(t.store_id)} for t in q.order_by(SupportTicket.id.desc())]


@router.post("/tickets/{ticket_id}")
def respond_ticket(ticket_id: int, data: TicketResponseIn, user: User = Depends(admin_only),
                   db: Session = Depends(get_db)):
    t = db.get(SupportTicket, ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    t.status, t.admin_response = data.status, data.admin_response or t.admin_response
    t.resolved_at = utcnow() if data.status == "resolved" else None
    notify(db, t.raised_by_id, "ticket", f"Ticket #{t.id} {data.status.replace('_', ' ')}", data.admin_response,
           link="/support")
    db.commit()
    return ticket_dict(t, db)
